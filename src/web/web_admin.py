# -*- coding: utf-8 -*-
"""
Flask веб-приложение для управления FAQ и переобучения ChromaDB
"""

from flask import Flask, Blueprint, render_template, request, jsonify, redirect, url_for, make_response
import uuid
import sys
import logging
import os
import signal
import requests
from io import BytesIO, TextIOWrapper
import csv
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core import database
from src.core import logging_config

# Загружаем переменные окружения
load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.utils import embedding_functions

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

logging_config.configure_root_logger(level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Конфигурация
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Эндпоинты для уведомления ботов
TELEGRAM_BOT_RELOAD_URL = "http://127.0.0.1:5001/reload"  # Telegram бот
TELEGRAM_BOT_RELOAD_SETTINGS_URL = "http://127.0.0.1:5001/reload-settings"

BITRIX24_BOT_RELOAD_URL = "http://127.0.0.1:5002/api/reload-chromadb"  # Bitrix24 бот

# Список всех ботов для уведомления
ALL_BOT_RELOAD_URLS = [TELEGRAM_BOT_RELOAD_URL, BITRIX24_BOT_RELOAD_URL]
ALL_BOT_RELOAD_SETTINGS_URLS = [TELEGRAM_BOT_RELOAD_SETTINGS_URL]

# Инициализация ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)

# Создаем Blueprint для админ-панели
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


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
    Отправляет запрос всем ботам на перезагрузку коллекции
    """
    for url in ALL_BOT_RELOAD_URLS:
        try:
            response = requests.post(url, timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ Бот ({url}) уведомлен о перезагрузке коллекции")
            else:
                logger.warning(f"⚠️ Бот ({url}) ответил с кодом {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ Не удалось связаться с ботом ({url}) (возможно, он не запущен)")
        except Exception as e:
            logger.error(f"❌ Ошибка при уведомлении бота ({url}): {e}")


def notify_bot_reload_settings():
    """
    Отправляет запрос всем ботам на перезагрузку настроек
    """
    for url in ALL_BOT_RELOAD_SETTINGS_URLS:
        try:
            response = requests.post(url, timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ Бот ({url}) уведомлен о перезагрузке настроек")
            else:
                logger.warning(f"⚠️ Бот ({url}) ответил с кодом {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ Не удалось связаться с ботом ({url}) (возможно, он не запущен)")
        except Exception as e:
            logger.error(f"❌ Ошибка при уведомлении бота ({url}): {e}")


# ========== ADMIN ROUTES ==========

@admin_bp.route('/')
def index():
    """Главная страница админки - список всех FAQ"""
    categories = database.get_all_categories()
    return render_template('admin/index.html', categories=categories)


@admin_bp.route('/faq/list')
def list_faqs():
    """Получить список FAQ (опционально по категории)"""
    category = request.args.get('category')
    if category:
        faqs = database.get_faqs_by_category(category)
    else:
        faqs = database.get_all_faqs()
    return jsonify(faqs)


@admin_bp.route('/faq/<faq_id>')
def get_faq(faq_id):
    """Получить конкретный FAQ"""
    faq = database.get_faq_by_id(faq_id)
    if faq:
        return jsonify(faq)
    return jsonify({"error": "FAQ не найден"}), 404


@admin_bp.route('/faq/add', methods=['POST'])
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


@admin_bp.route('/faq/update/<faq_id>', methods=['PUT'])
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


@admin_bp.route('/faq/delete/<faq_id>', methods=['DELETE'])
def delete_faq(faq_id):
    """Удалить FAQ"""
    success = database.delete_faq(faq_id)
    if success:
        return jsonify({"success": True, "message": "FAQ удалён"})
    return jsonify({"success": False, "message": "FAQ не найден"}), 404


@admin_bp.route('/categories')
def get_categories():
    """Получить список всех категорий"""
    categories = database.get_all_categories()
    return jsonify(categories)


@admin_bp.route('/categories', methods=['POST'])
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


@admin_bp.route('/retrain', methods=['POST'])
def retrain():
    """Переобучить ChromaDB"""
    result = retrain_chromadb()
    if result["success"]:
        return jsonify(result)
    return jsonify(result), 500


@admin_bp.route('/search', methods=['GET'])
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


@admin_bp.route('/search/semantic', methods=['POST'])
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

@admin_bp.route('/settings')
def settings_page():
    """Страница настроек бота"""
    return render_template('admin/settings.html')


@admin_bp.route('/api/settings', methods=['GET'])
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


@admin_bp.route('/api/settings', methods=['POST'])
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


@admin_bp.route('/api/settings/reset', methods=['POST'])
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

@admin_bp.route('/logs')
def logs_page():
    """Страница просмотра логов"""
    categories = database.get_all_categories()
    return render_template('admin/logs.html', categories=categories)


@admin_bp.route('/api/logs/list', methods=['GET'])
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
    - no_answer: показывать только запросы без ответа (true/false)
    - platform: фильтр по платформе (telegram, bitrix24)
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
        no_answer = request.args.get('no_answer', 'false').lower() == 'true'
        platform = request.args.get('platform')

        # Получаем логи
        logs, total = database.get_logs(
            limit=per_page,
            offset=offset,
            user_id=user_id,
            faq_id=faq_id,
            rating_filter=rating,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            no_answer=no_answer,
            platform=platform
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


@admin_bp.route('/api/logs/statistics', methods=['GET'])
def get_logs_statistics():
    """Получить статистику по логам"""
    try:
        stats = database.get_statistics()
        # Добавляем текущий порог схожести
        stats["similarity_threshold"] = database.SIMILARITY_THRESHOLD
        return jsonify({
            "success": True,
            "statistics": stats
        })
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@admin_bp.route('/api/logs/export', methods=['GET'])
def export_logs():
    """
    Экспорт логов в CSV
    Параметры: такие же как в /api/logs/list
    """
    try:

        # Параметры фильтрации (те же что и для get_logs)
        user_id = request.args.get('user_id')
        if user_id:
            user_id = int(user_id)

        faq_id = request.args.get('faq_id')
        rating = request.args.get('rating')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        search_text = request.args.get('search')
        no_answer = request.args.get('no_answer', 'false').lower() == 'true'

        # Получаем все логи
        logs, total = database.get_logs(
            limit=10000,
            offset=0,
            user_id=user_id,
            faq_id=faq_id,
            rating_filter=rating,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            no_answer=no_answer
        )

        # Создаем CSV в памяти
        output = BytesIO()
        wrapper = TextIOWrapper(output, encoding='utf-8-sig', newline='')

        writer = csv.writer(wrapper, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

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
            # Время уже конвертировано в UTC+7 функцией database.get_logs()
            query_timestamp = log.get('query_timestamp', '')
            if query_timestamp:
                query_timestamp = query_timestamp + ' UTC+7'

            rating_timestamp = log.get('rating_timestamp', '')
            if rating_timestamp:
                rating_timestamp = rating_timestamp + ' UTC+7'

            user_id_val = log.get('user_id')
            similarity = round(log.get('similarity_score', 0), 1) if log.get('similarity_score') is not None else ''
            rating_val = log.get('rating', '')

            writer.writerow([
                query_timestamp,
                int(user_id_val) if user_id_val is not None else '',
                log.get('username', ''),
                log.get('query_text', ''),
                log.get('category', ''),
                log.get('faq_question', ''),
                similarity,
                rating_val,
                rating_timestamp
            ])

        # Flush TextIOWrapper, чтобы данные попали в BytesIO
        wrapper.flush()

        # Теперь можно безопасно получить байты
        resp = make_response(output.getvalue())
        resp.headers["Content-Disposition"] = "attachment; filename=logs_export.csv"
        resp.headers["Content-Type"] = "text/csv; charset=utf-8"

        return resp

    except Exception as e:
        logger.error(f"Ошибка при экспорте логов: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ========== PUBLIC ROUTES (временные заглушки) ==========

@app.route('/')
def public_search():
    """Публичная страница поиска"""
    return render_template('search.html')


@app.route('/api/search', methods=['POST'])
def public_api_search():
    """API для публичного семантического поиска"""
    data = request.json
    query = data.get('query', '').strip()
    user_id = data.get('user_id', 0)  # Для веба используем 0 или сессионный ID

    if not query:
        return jsonify({"success": False, "message": "Не указан поисковый запрос"}), 400

    try:
        # Логируем запрос пользователя
        query_log_id = database.add_query_log(
            user_id=user_id,
            username='web_user',
            query_text=query,
            platform='web'
        )

        # Получаем коллекцию
        try:
            collection = chroma_client.get_collection(name="faq_collection")
        except Exception:
            return jsonify({
                "success": False,
                "message": "База знаний не инициализирована."
            }), 404

        # Выполняем семантический поиск
        results = collection.query(
            query_texts=[query],
            n_results=5,
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

            # Применяем порог схожести
            if similarity >= database.SIMILARITY_THRESHOLD:
                # Логируем показанный ответ
                answer_log_id = database.add_answer_log(
                    query_log_id=query_log_id,
                    faq_id=faq_id,
                    similarity_score=similarity,
                    answer_shown=metadata["answer"]
                )

                search_results.append({
                    "id": faq_id,
                    "answer_log_id": answer_log_id,  # Добавляем для обратной связи
                    "question": metadata["question"],
                    "answer": metadata["answer"],
                    "category": metadata["category"],
                    "similarity": round(similarity, 1)
                })

        return jsonify({
            "success": True,
            "query": query,
            "count": len(search_results),
            "results": search_results
        })

    except Exception as e:
        logger.error(f"Ошибка при публичном поиске: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/feedback', methods=['POST'])
def public_feedback():
    """API для сохранения обратной связи от пользователей"""
    data = request.json
    answer_log_id = data.get('answer_log_id')
    rating = data.get('rating')  # 'helpful' или 'not_helpful'
    user_id = data.get('user_id', 0)  # Для веб-версии можем использовать 0 или генерировать

    if not answer_log_id or not rating:
        return jsonify({"success": False, "message": "Не все поля заполнены"}), 400

    try:
        database.add_rating_log(answer_log_id, user_id, rating)
        return jsonify({"success": True, "message": "Спасибо за обратную связь!"})
    except Exception as e:
        logger.error(f"Ошибка при сохранении обратной связи: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# Регистрируем Blueprint админки
app.register_blueprint(admin_bp)


# ========== MAIN ==========

if __name__ == '__main__':
    database.init_database()
    print("🌐 Веб-интерфейс запущен на http://127.0.0.1:5000")
    print("📝 Используйте этот интерфейс для управления FAQ")
    app.run(debug=False, host='0.0.0.0', port=5000)