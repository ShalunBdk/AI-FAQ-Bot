# -*- coding: utf-8 -*-
"""
Flask веб-приложение для управления FAQ и переобучения ChromaDB
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import uuid
import database
from chromadb.utils import embedding_functions
import logging
import os
import signal
import requests

os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.utils import embedding_functions

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

logging.basicConfig(level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Конфигурация
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BOT_RELOAD_URL = "http://127.0.0.1:5001/reload"  # Эндпоинт бота для перезагрузки коллекции
BOT_RELOAD_SETTINGS_URL = "http://127.0.0.1:5001/reload-settings"  # Эндпоинт бота для перезагрузки настроек

# Инициализация ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)


def retrain_chromadb():
    """
    Переобучение ChromaDB на основе данных из базы
    """
    try:
        # Удаляем старую коллекцию
        try:
            chroma_client.delete_collection(name="faq_collection")
            logger.info("Старая коллекция удалена")
        except Exception as e:
            logger.info(f"Коллекции не было или ошибка удаления: {e}")

        # Создаем новую коллекцию
        collection = chroma_client.create_collection(
            name="faq_collection",
            embedding_function=embedding_func,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("Создана новая коллекция")

        # Получаем все FAQ из базы
        all_faqs = database.get_all_faqs()
        if not all_faqs:
            logger.warning("В базе нет данных для обучения")
            return {"success": False, "message": "В базе нет данных"}

        # Подготавливаем данные для ChromaDB
        documents, metadatas, ids = [], [], []
        for faq in all_faqs:
            text = f"{faq['question']} {' '.join(faq.get('keywords', []))}"
            documents.append(text)
            metadatas.append({
                "category": faq["category"],
                "question": faq["question"],
                "answer": faq["answer"]
            })
            ids.append(faq["id"])

        # Добавляем в ChromaDB
        collection.add(documents=documents, metadatas=metadatas, ids=ids)

        logger.info(f"✅ ChromaDB переобучена: {len(all_faqs)} записей")
        
        # Уведомляем бота о необходимости перезагрузки
        notify_bot_reload()
        
        return {"success": True, "message": f"Переобучено {len(all_faqs)} записей", "count": len(all_faqs)}

    except Exception as e:
        logger.error(f"❌ Ошибка при переобучении: {e}")
        return {"success": False, "message": str(e)}


def notify_bot_reload():
    """
    Отправляет запрос боту на перезагрузку коллекции
    """
    try:
        response = requests.post(BOT_RELOAD_URL, timeout=2)
        if response.status_code == 200:
            logger.info("✅ Бот уведомлен о перезагрузке коллекции")
        else:
            logger.warning(f"⚠️ Бот ответил с кодом {response.status_code}")
    except requests.exceptions.ConnectionError:
        logger.warning("⚠️ Не удалось связаться с ботом (возможно, он не запущен)")
    except Exception as e:
        logger.error(f"❌ Ошибка при уведомлении бота: {e}")


def notify_bot_reload_settings():
    """
    Отправляет запрос боту на перезагрузку настроек
    """
    try:
        response = requests.post(BOT_RELOAD_SETTINGS_URL, timeout=2)
        if response.status_code == 200:
            logger.info("✅ Бот уведомлен о перезагрузке настроек")
        else:
            logger.warning(f"⚠️ Бот ответил с кодом {response.status_code}")
    except requests.exceptions.ConnectionError:
        logger.warning("⚠️ Не удалось связаться с ботом (возможно, он не запущен)")
    except Exception as e:
        logger.error(f"❌ Ошибка при уведомлении бота: {e}")


# ========== WEB ROUTES ==========

@app.route('/')
def index():
    """Главная страница - список всех FAQ"""
    categories = database.get_all_categories()
    return render_template('index.html', categories=categories)


@app.route('/faq/list')
def list_faqs():
    """Получить список FAQ (опционально по категории)"""
    category = request.args.get('category')
    if category:
        faqs = database.get_faqs_by_category(category)
    else:
        faqs = database.get_all_faqs()
    return jsonify(faqs)


@app.route('/faq/<faq_id>')
def get_faq(faq_id):
    """Получить конкретный FAQ"""
    faq = database.get_faq_by_id(faq_id)
    if faq:
        return jsonify(faq)
    return jsonify({"error": "FAQ не найден"}), 404


@app.route('/faq/add', methods=['POST'])
def add_faq():
    """Добавить новый FAQ"""
    data = request.json
    category = data.get('category')
    question = data.get('question')
    answer = data.get('answer')
    keywords = data.get('keywords', [])

    if not all([category, question, answer]):
        return jsonify({"success": False, "message": "Не все обязательные поля заполнены"}), 400

    faq_id = data.get('id') or f"faq_{uuid.uuid4().hex[:8]}"

    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(',') if k.strip()]

    success = database.add_faq(faq_id, category, question, answer, keywords)
    if success:
        return jsonify({"success": True, "message": "FAQ добавлен"})
    return jsonify({"success": False, "message": "FAQ с таким ID уже существует"}), 400


@app.route('/faq/update/<faq_id>', methods=['PUT'])
def update_faq(faq_id):
    """Обновить существующий FAQ"""
    data = request.json
    category = data.get('category')
    question = data.get('question')
    answer = data.get('answer')
    keywords = data.get('keywords', [])

    if not all([category, question, answer]):
        return jsonify({"success": False, "message": "Не все обязательные поля заполнены"}), 400

    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(',') if k.strip()]

    success = database.update_faq(faq_id, category, question, answer, keywords)
    if success:
        return jsonify({"success": True, "message": "FAQ обновлён"})
    return jsonify({"success": False, "message": "FAQ не найден"}), 404


@app.route('/faq/delete/<faq_id>', methods=['DELETE'])
def delete_faq(faq_id):
    """Удалить FAQ"""
    success = database.delete_faq(faq_id)
    if success:
        return jsonify({"success": True, "message": "FAQ удалён"})
    return jsonify({"success": False, "message": "FAQ не найден"}), 404


@app.route('/categories')
def get_categories():
    """Получить список всех категорий"""
    categories = database.get_all_categories()
    return jsonify(categories)


@app.route('/categories', methods=['POST'])
def add_category_route():
    """Добавить новую категорию"""
    data = request.get_json()
    category_name = data.get("name")

    if not category_name:
        return jsonify({"error": "Не указано имя категории"}), 400

    if database.add_category(category_name):
        return jsonify({"message": "Категория добавлена"}), 201
    else:
        return jsonify({"error": "Такая категория уже существует"}), 409


@app.route('/retrain', methods=['POST'])
def retrain():
    """Переобучить ChromaDB"""
    result = retrain_chromadb()
    if result["success"]:
        return jsonify(result)
    return jsonify(result), 500


@app.route('/search', methods=['GET'])
def search_faqs():
    """
    Поиск FAQ по тексту (в вопросах, ответах и ключевых словах)
    Параметры: ?q=текст_поиска&category=категория (опционально)
    """
    query = request.args.get('q', '').strip().lower()
    category = request.args.get('category')
    
    if not query:
        return jsonify({"success": False, "message": "Не указан поисковый запрос"}), 400
    
    try:
        # Получаем все FAQ или по категории
        if category:
            all_faqs = database.get_faqs_by_category(category)
        else:
            all_faqs = database.get_all_faqs()
        
        # Фильтруем по поисковому запросу
        results = []
        for faq in all_faqs:
            # Ищем в вопросе, ответе и ключевых словах
            question_lower = faq['question'].lower()
            answer_lower = faq['answer'].lower()
            keywords_lower = ' '.join(faq.get('keywords', [])).lower()
            
            # Проверяем совпадение
            if (query in question_lower or 
                query in answer_lower or 
                query in keywords_lower):
                
                # Добавляем информацию о том, где найдено
                match_info = []
                if query in question_lower:
                    match_info.append('вопросе')
                if query in answer_lower:
                    match_info.append('ответе')
                if query in keywords_lower:
                    match_info.append('ключевых словах')
                
                faq_copy = faq.copy()
                faq_copy['match_location'] = match_info
                results.append(faq_copy)
        
        return jsonify({
            "success": True,
            "query": query,
            "count": len(results),
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/search/semantic', methods=['POST'])
def semantic_search():
    """
    Семантический поиск через ChromaDB
    Body: {"query": "текст запроса", "n_results": 5}
    """
    data = request.json
    query = data.get('query', '').strip()
    n_results = data.get('n_results', 5)
    
    if not query:
        return jsonify({"success": False, "message": "Не указан поисковый запрос"}), 400
    
    try:
        # Получаем коллекцию
        try:
            collection = chroma_client.get_collection(name="faq_collection")
        except Exception:
            return jsonify({
                "success": False, 
                "message": "База знаний не инициализирована. Выполните переобучение."
            }), 404
        
        # Выполняем семантический поиск
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        if not results or not results["documents"] or not results["documents"][0]:
            return jsonify({
                "success": True,
                "query": query,
                "count": 0,
                "results": []
            })
        
        # Формируем результаты
        search_results = []
        for i, metadata in enumerate(results["metadatas"][0]):
            distance = results["distances"][0][i]
            similarity = max(0.0, 1.0 - distance) * 100.0
            faq_id = results["ids"][0][i] if "ids" in results and results["ids"] else None
            
            search_results.append({
                "id": faq_id,
                "question": metadata["question"],
                "answer": metadata["answer"],
                "category": metadata["category"],
                "similarity": round(similarity, 1),
                "distance": round(distance, 4)
            })
        
        return jsonify({
            "success": True,
            "query": query,
            "count": len(search_results),
            "results": search_results
        })
        
    except Exception as e:
        logger.error(f"Ошибка при семантическом поиске: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ========== НАСТРОЙКИ БОТА ==========

@app.route('/settings')
def settings_page():
    """Страница настроек бота"""
    return render_template('settings.html')


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Получить текущие настройки бота"""
    try:
        settings = database.get_bot_settings()
        return jsonify({
            "success": True,
            "settings": settings
        })
    except Exception as e:
        logger.error(f"Ошибка при получении настроек: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Сохранить настройки бота"""
    try:
        data = request.json
        settings = data.get('settings', {})

        if not settings:
            return jsonify({"success": False, "message": "Настройки не переданы"}), 400

        # Сохраняем настройки в БД
        success = database.update_bot_settings(settings)

        if success:
            # Уведомляем бота о перезагрузке настроек
            notify_bot_reload_settings()

            return jsonify({
                "success": True,
                "message": "Настройки сохранены"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Ошибка при сохранении настроек"
            }), 500

    except Exception as e:
        logger.error(f"Ошибка при сохранении настроек: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/settings/reset', methods=['POST'])
def reset_settings():
    """Сбросить настройки бота к значениям по умолчанию"""
    try:
        success = database.reset_bot_settings()

        if success:
            # Уведомляем бота о перезагрузке настроек
            notify_bot_reload_settings()

            return jsonify({
                "success": True,
                "message": "Настройки сброшены к значениям по умолчанию"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Ошибка при сбросе настроек"
            }), 500

    except Exception as e:
        logger.error(f"Ошибка при сбросе настроек: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ========== ЛОГИРОВАНИЕ ==========

@app.route('/logs')
def logs_page():
    """Страница просмотра логов"""
    categories = database.get_all_categories()
    return render_template('logs.html', categories=categories)


@app.route('/api/logs/list', methods=['GET'])
def get_logs():
    """
    Получить список логов с фильтрацией и пагинацией
    Параметры:
    - page: номер страницы (по умолчанию 1)
    - per_page: количество записей на странице (по умолчанию 50)
    - user_id: фильтр по ID пользователя
    - faq_id: фильтр по ID FAQ
    - rating: фильтр по оценке (helpful, not_helpful, no_rating)
    - date_from: начальная дата (ISO format)
    - date_to: конечная дата (ISO format)
    - search: поиск по тексту запроса
    """
    try:
        # Параметры пагинации
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page

        # Параметры фильтрации
        user_id = request.args.get('user_id')
        if user_id:
            user_id = int(user_id)

        faq_id = request.args.get('faq_id')
        rating = request.args.get('rating')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        search_text = request.args.get('search')

        # Получаем логи
        logs, total = database.get_logs(
            limit=per_page,
            offset=offset,
            user_id=user_id,
            faq_id=faq_id,
            rating_filter=rating,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text
        )

        # Вычисляем метаданные пагинации
        total_pages = (total + per_page - 1) // per_page

        return jsonify({
            "success": True,
            "logs": logs,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages
            }
        })

    except Exception as e:
        logger.error(f"Ошибка при получении логов: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/logs/statistics', methods=['GET'])
def get_logs_statistics():
    """Получить статистику по логам"""
    try:
        stats = database.get_statistics()
        return jsonify({
            "success": True,
            "statistics": stats
        })
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/logs/export', methods=['GET'])
def export_logs():
    """
    Экспорт логов в CSV
    Параметры: такие же как в /api/logs/list
    """
    try:
        import csv
        from io import StringIO
        from flask import make_response

        # Параметры фильтрации (те же что и для get_logs)
        user_id = request.args.get('user_id')
        if user_id:
            user_id = int(user_id)

        faq_id = request.args.get('faq_id')
        rating = request.args.get('rating')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        search_text = request.args.get('search')

        # Получаем все логи (без пагинации)
        logs, total = database.get_logs(
            limit=10000,  # Максимум для экспорта
            offset=0,
            user_id=user_id,
            faq_id=faq_id,
            rating_filter=rating,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text
        )

        # Создаем CSV
        si = StringIO()
        writer = csv.writer(si, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Заголовки
        writer.writerow([
            'Дата/Время запроса',
            'ID пользователя',
            'Имя пользователя',
            'Текст запроса',
            'Категория FAQ',
            'Вопрос FAQ',
            'Оценка схожести (%)',
            'Рейтинг',
            'Дата/Время рейтинга'
        ])

        # Данные
        for log in logs:
            writer.writerow([
                log.get('query_timestamp', ''),
                log.get('user_id', ''),
                log.get('username', ''),
                log.get('query_text', ''),
                log.get('category', ''),
                log.get('faq_question', ''),
                round(log.get('similarity_score', 0), 1) if log.get('similarity_score') else '',
                log.get('rating', ''),
                log.get('rating_timestamp', '')
            ])

        # Формируем ответ
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=logs_export.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8-sig"  # utf-8-sig для Excel

        return output

    except Exception as e:
        logger.error(f"Ошибка при экспорте логов: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ========== MAIN ==========

if __name__ == '__main__':
    database.init_database()
    print("🌐 Веб-интерфейс запущен на http://127.0.0.1:5000")
    print("📝 Используйте этот интерфейс для управления FAQ")
    app.run(debug=False, host='0.0.0.0', port=5000)