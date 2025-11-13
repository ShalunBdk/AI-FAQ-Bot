"""
FAQ Бот для Bitrix24
Использует ChromaDB для семантического поиска ответов
"""

import logging
import os
import sys
import json
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import chromadb
from chromadb.utils import embedding_functions

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core import database
from src.core import logging_config
from src.api.b24_api import Bitrix24API, Bitrix24Event

# Загрузка конфигурации
load_dotenv()
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Настройка логирования (DEBUG для детальной диагностики)
logging_config.configure_root_logger(level=logging.DEBUG)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ ==========

BITRIX24_WEBHOOK = os.getenv("BITRIX24_WEBHOOK")
BITRIX24_BOT_ID = os.getenv("BITRIX24_BOT_ID")  # Числовой BOT_ID для регистрации команд
BITRIX24_CLIENT_ID = os.getenv("BITRIX24_CLIENT_ID")  # Строковый CLIENT_ID для API запросов
BITRIX24_HANDLER_URL = os.getenv("BITRIX24_HANDLER_URL", "https://your-server.com/webhook/bitrix24")
MODEL_NAME = os.getenv("MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "45.0"))

if not BITRIX24_WEBHOOK:
    logger.warning("⚠️ BITRIX24_WEBHOOK не настроен в .env")

# ========== ИНИЦИАЛИЗАЦИЯ ==========

# ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=MODEL_NAME
)
collection = None  # Загрузится при старте

# Bitrix24 API
b24_api = None  # Инициализируется при получении webhook

# Flask app для приема вебхуков
app = Flask(__name__)


# ========== ФУНКЦИИ ПОИСКА ==========

def find_best_match(query_text: str, n_results: int = 3) -> Tuple[Optional[Dict], float, Dict]:
    """
    Поиск наиболее подходящего ответа в ChromaDB

    Args:
        query_text: Текст вопроса пользователя
        n_results: Количество результатов для возврата

    Returns:
        (best_match_metadata, similarity_percent, all_results)
    """
    global collection

    if collection is None:
        logger.error("ChromaDB collection не инициализирована")
        return None, 0.0, {}

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        if not results or not results['ids'] or not results['ids'][0]:
            logger.info("Ничего не найдено в ChromaDB")
            return None, 0.0, {}

        # Конвертируем distance в similarity (0-100%)
        best_distance = results['distances'][0][0]
        similarity = max(0.0, 1.0 - best_distance) * 100.0
        best_metadata = results['metadatas'][0][0]

        logger.info(f"Найдено результатов: {len(results['documents'][0])}, лучший score: {similarity:.1f}%")

        return best_metadata, similarity, results

    except Exception as e:
        logger.error(f"Ошибка поиска в ChromaDB: {e}", exc_info=True)
        return None, 0.0, {}


def init_chromadb():
    """Инициализация ChromaDB из существующих FAQ"""
    global collection

    try:
        collection = chroma_client.get_collection(
            name="faq_collection",
            embedding_function=embedding_func
        )
        logger.info(f"✅ ChromaDB загружена: {collection.count()} записей")
    except Exception as e:
        logger.warning(f"ChromaDB коллекция не найдена, создаем новую: {e}")
        # Создадим коллекцию если её нет
        try:
            collection = chroma_client.create_collection(
                name="faq_collection",
                embedding_function=embedding_func
            )
            logger.info("✅ Создана новая ChromaDB коллекция")

            # Попробуем загрузить данные из БД
            init_demo_data()
        except Exception as create_error:
            logger.error(f"❌ Ошибка создания коллекции: {create_error}")


def init_demo_data():
    """Инициализация данных в ChromaDB из БД (если пусто)"""
    try:
        if collection.count() > 0:
            logger.info(f"В ChromaDB уже есть {collection.count()} записей")
            return

        logger.info("Добавление данных из БД в ChromaDB...")

        all_faqs = database.get_all_faqs()

        if not all_faqs:
            logger.warning("⚠️ В базе данных нет FAQ. Запустите migrate_data.py для миграции данных.")
            return

        documents, metadatas, ids = [], [], []

        for faq in all_faqs:
            text = f"{faq['question']} {' '.join(faq.get('keywords', []))}"
            documents.append(text)
            metadatas.append({
                "id": faq["id"],
                "category": faq["category"],
                "question": faq["question"],
                "answer": faq["answer"]
            })
            ids.append(faq["id"])

        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        logger.info(f"✅ Добавлено {len(all_faqs)} записей в ChromaDB")

    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации данных: {e}", exc_info=True)


def reload_chromadb():
    """Перезагрузка ChromaDB (для горячего обновления)"""
    global collection
    try:
        collection = chroma_client.get_collection(
            name="faq_collection",
            embedding_function=embedding_func
        )
        logger.info(f"🔄 ChromaDB перезагружена: {collection.count()} записей")
        return True
    except Exception as e:
        logger.error(f"Ошибка перезагрузки ChromaDB: {e}")
        return False


def register_bot_commands(api: Bitrix24API):
    """Регистрация команд для кнопок"""
    try:
        if not BITRIX24_HANDLER_URL or BITRIX24_HANDLER_URL == "https://your-server.com/webhook/bitrix24":
            logger.warning("⚠️ BITRIX24_HANDLER_URL не настроен в .env - команды не будут зарегистрированы")
            logger.warning("⚠️ Добавьте BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24 в .env")
            logger.warning("⚠️ Или запустите: python register_bot.py для регистрации бота")
            return

        # Регистрируем команды для обратной связи и похожих вопросов
        # Используем шаблоны без ID - Bitrix24 будет принимать любые суффиксы
        commands = [
            ('helpful_yes', 'Полезно'),
            ('helpful_no', 'Не помогло'),
            ('cat', 'Выбор категории'),
            ('similar_question', 'Похожий вопрос'),
        ]

        for command, title in commands:
            result = api.register_command(command, title, BITRIX24_HANDLER_URL, hidden=True)
            if result.get('success') == False:
                error_msg = result.get('error', '')
                if 'Bot not found' in error_msg or 'BOT_ID_ERROR' in error_msg:
                    logger.error(f"❌ Бот не зарегистрирован в Bitrix24!")
                    logger.error(f"❌ Запустите: python register_bot.py для регистрации бота")
                    return  # Прерываем попытки регистрации команд
                else:
                    logger.warning(f"⚠️ Не удалось зарегистрировать команду '{command}': {error_msg}")
            elif 'result' in result:
                logger.info(f"✅ Команда '{command}' зарегистрирована")

    except Exception as e:
        logger.error(f"❌ Ошибка регистрации команд: {e}", exc_info=True)


# ========== ОБРАБОТЧИКИ КОМАНД ==========

def handle_start(event: Bitrix24Event, api: Bitrix24API):
    """Обработка команды /start или /помощь"""
    logger.info(f"📩 Обработка команды /start от пользователя ID: {event.user_id}, Dialog ID: {event.dialog_id}")

    message = (
        "👋 Привет! Я FAQ Помощник.\n\n"
        "Задавайте мне вопросы, и я постараюсь на них ответить на основе базы знаний.\n\n"
        "📋 Команды:\n"
        "категории - показать все категории вопросов\n"
        "помощь - показать эту справку"
    )

    logger.debug(f"📤 Отправка приветственного сообщения. Dialog ID: {event.dialog_id}, длина текста: {len(message)} символов")
    result = api.send_message(event.dialog_id, message)

    if result.get('success') == False:
        logger.error(f"❌ Ошибка отправки приветствия: {result.get('error')}")
    elif 'result' in result:
        logger.info(f"✅ Приветствие успешно отправлено пользователю {event.user_id}, Message ID: {result.get('result')}")
    else:
        logger.warning(f"⚠️ Неизвестный ответ от Bitrix24 API: {result}")


def handle_categories(event: Bitrix24Event, api: Bitrix24API):
    """Показать список категорий"""
    categories = database.get_all_categories()

    if not categories:
        api.send_message(event.dialog_id, "❌ Категории не найдены")
        return

    # Создаем кнопки для категорий (максимум 2 в ряд)
    buttons = []
    current_row = []

    for i, category in enumerate(categories):
        current_row.append({
            'text': f"📂 {category}",
            'action': 'cat',
            'params': category
        })

        # Каждые 2 кнопки - новый ряд
        if len(current_row) == 2 or i == len(categories) - 1:
            buttons.append(current_row)
            current_row = []

    keyboard = api.create_keyboard(buttons)

    api.send_message(
        event.dialog_id,
        "📂 Выберите категорию:",
        keyboard=keyboard
    )
    logger.info(f"Отправлены категории пользователю {event.user_id}")


def handle_category_select(event: Bitrix24Event, api: Bitrix24API, category: str):
    """Показать FAQ из выбранной категории"""
    faqs = database.get_faqs_by_category(category)

    if not faqs:
        api.send_message(event.dialog_id, f"❌ В категории '{category}' нет вопросов")
        return

    # Формируем список вопросов как вложения
    attach_items = [{'type': 'message', 'text': f'📂 Категория: {category}'}]

    for i, faq in enumerate(faqs[:10]):  # Максимум 10 вопросов
        attach_items.append({
            'type': 'link',
            'name': faq['question'],
            'url': '#'
        })
        if i < len(faqs[:10]) - 1:  # Разделитель между вопросами
            attach_items.append({'type': 'delimiter'})

    attach = api.create_attach(attach_items)

    message = f"Найдено вопросов: {len(faqs)}"
    if len(faqs) > 10:
        message += f"\nПоказаны первые 10 из {len(faqs)}"

    api.send_message(
        event.dialog_id,
        message,
        attach=attach
    )
    logger.info(f"Отправлена категория '{category}' пользователю {event.user_id}")


def handle_search_faq(event: Bitrix24Event, api: Bitrix24API, is_faq_view: bool = False):
    """
    Поиск ответа на вопрос пользователя

    Args:
        event: Событие от Bitrix24
        api: API клиент
        is_faq_view: True если это просмотр FAQ через кнопку (добавляет префикс в логи)
    """
    query_text = event.message_text
    user_id = event.user_id

    # Показываем индикатор печатания
    api.send_typing(event.dialog_id)

    # Текст для логирования (с префиксом если это просмотр FAQ)
    log_query_text = f"[Просмотр FAQ] {query_text}" if is_faq_view else query_text

    # Логирование запроса
    query_log_id = database.add_query_log(
        user_id=user_id,
        username=event.username,  # Используем полное имя пользователя (Фамилия Имя)
        query_text=log_query_text,
        platform='bitrix24'
    )

    # Поиск в ChromaDB (по оригинальному тексту без префикса)
    best_match, similarity, all_results = find_best_match(query_text, n_results=3)


    # Получаем текущий порог из настроек или используем дефолтный
    threshold = SIMILARITY_THRESHOLD
    try:
        settings = database.get_bot_settings()
        threshold = float(settings.get('similarity_threshold', SIMILARITY_THRESHOLD))
    except Exception as e:
        logger.warning(f"Не удалось получить настройки, используем дефолтный порог: {e}")

    if similarity >= threshold and best_match:
        # Нашли ответ!
        # Логируем показанный ответ
        send_answer(event, api, best_match, similarity, all_results, query_log_id)
    else:
        # Ответ не найден
        send_no_answer(event, api, similarity, all_results)
        database.add_answer_log(
            query_log_id=query_log_id,
            faq_id=None,
            similarity_score=similarity,
            answer_shown="Ответ не найден"
        )


def send_answer(event: Bitrix24Event, api: Bitrix24API, match: Dict,
                similarity: float, all_results: Dict, query_log_id: int):
    """Отправка найденного ответа с кнопками обратной связи"""

    # Получаем ID FAQ из результатов
    faq_id = all_results["ids"][0][0] if all_results and "ids" in all_results and all_results["ids"] else None

    # Логирование ответа
    answer_log_id = database.add_answer_log(
        query_log_id=query_log_id,
        faq_id=faq_id,
        similarity_score=similarity,
        answer_shown=match['answer']
    )

    # Формируем сообщение
    message = f"✅ {match['question']}\n\n{match['answer']}\n\n💡 Схожесть: {similarity:.1f}%"

    # Кнопки обратной связи
    feedback_buttons = [[
        {
            'text': '👍 Полезно',
            'action': 'helpful_yes',
            'params': str(answer_log_id)
        },
        {
            'text': '👎 Не помогло',
            'action': 'helpful_no',
            'params': str(answer_log_id)
        }
    ]]

    # Похожие вопросы (если есть) - добавляем как кнопки
    similar_questions_buttons = []
    if all_results and len(all_results.get('metadatas', [[]])[0]) > 1:
        for i in range(1, min(4, len(all_results['metadatas'][0]))):
            sim = (1.0 - all_results['distances'][0][i]) * 100.0
            if sim >= 30:  # Показываем только если similarity > 30%
                meta = all_results['metadatas'][0][i]
                question_text = meta['question']
                # Обрезаем текст кнопки если слишком длинный
                button_text = question_text if len(question_text) <= 60 else question_text[:57] + "..."
                similar_questions_buttons.append([{
                    'text': f"❓ {button_text}",
                    'action': 'similar_question',
                    'params': question_text  # Полный текст вопроса в параметрах
                }])

    # Объединяем кнопки: сначала feedback, потом похожие вопросы
    all_buttons = feedback_buttons
    if similar_questions_buttons:
        all_buttons.extend(similar_questions_buttons)
        message += "\n\n📌 Возможно, вас также интересует:"

    keyboard = api.create_keyboard(all_buttons)
    attach = None  # Пока не используем attach

    # Отправка
    api.send_message(event.dialog_id, message, keyboard=keyboard, attach=attach)
    logger.info(f"Отправлен ответ пользователю {event.user_id}, similarity={similarity:.1f}%")


def send_no_answer(event: Bitrix24Event, api: Bitrix24API,
                   similarity: float, all_results: Dict):
    """Отправка сообщения когда ответ не найден"""
    message = (
        f"😔 Извините, я не нашел точного ответа на ваш вопрос "
        f"(лучшая схожесть: {similarity:.1f}%).\n\n"
        f"Попробуйте:\n"
        f"• Переформулировать вопрос\n"
        f"• Написать 'категории' для просмотра всех тем"
    )

    # Показываем похожие вопросы как кнопки
    similar_questions_buttons = []
    if all_results and all_results.get('metadatas') and all_results['metadatas'][0]:
        for i in range(min(3, len(all_results['metadatas'][0]))):
            sim = (1.0 - all_results['distances'][0][i]) * 100.0
            meta = all_results['metadatas'][0][i]
            question_text = meta['question']
            # Обрезаем текст кнопки если слишком длинный
            button_text = question_text if len(question_text) <= 60 else question_text[:57] + "..."
            similar_questions_buttons.append([{
                'text': f"❓ {button_text}",
                'action': 'similar_question',
                'params': question_text  # Полный текст вопроса в параметрах
            }])

    if similar_questions_buttons:
        message += "\n\n💡 Возможно, вам помогут эти вопросы:"
        keyboard = api.create_keyboard(similar_questions_buttons)
        api.send_message(event.dialog_id, message, keyboard=keyboard)
    else:
        api.send_message(event.dialog_id, message)

    logger.info(f"Отправлено 'не найдено' пользователю {event.user_id}, similarity={similarity:.1f}%")


def handle_rating(event: Bitrix24Event, api: Bitrix24API,
                  answer_log_id: int, is_helpful: bool,
                  command_id: int = None, message_id: int = None):
    """Обработка оценки ответа"""
    rating = 'helpful' if is_helpful else 'not_helpful'

    success = database.add_rating_log(
        answer_log_id=answer_log_id,
        user_id=event.user_id,
        rating=rating
    )

    if success:
        if is_helpful:
            message = "👍 Спасибо за отзыв! Рад, что смог помочь."
        else:
            message = "👎 Спасибо за отзыв. Попробуйте переформулировать вопрос или обратитесь к коллегам."
    else:
        message = "❌ Ошибка сохранения отзыва"

    # Если вызвано из команды (кнопки), используем answer_command и обновляем сообщение
    if command_id and message_id:
        # Отправляем ответ на команду
        api.answer_command(command_id, message_id, message)

        # Удаляем кнопки из исходного сообщения
        logger.debug(f"🔄 Удаление кнопок из сообщения {message_id}")
        api.update_message(message_id, remove_keyboard=True)
    else:
        api.send_message(event.dialog_id, message)

    logger.info(f"Получена оценка от пользователя {event.user_id}: {rating}")


# ========== WEBHOOK ENDPOINT ==========

@app.route('/', methods=['POST'])
@app.route('/webhook/bitrix24', methods=['POST'])
def webhook_handler():
    """Обработчик вебхуков от Bitrix24"""
    try:
        logger.info(f"📥 Получен POST запрос на {request.path}")

        # Получаем данные от Bitrix24
        if request.is_json:
            event_data = request.get_json()
        else:
            event_data = request.form.to_dict()

        logger.info(f"📩 Получено событие от Bitrix24: {event_data.get('event')}")
        logger.debug(f"🔍 Полные данные события: {json.dumps(event_data, ensure_ascii=False, indent=2)}")

        # Парсим событие
        event = Bitrix24Event(event_data)

        logger.debug(f"🔧 Распарсенные данные:")
        logger.debug(f"   User ID: {event.user_id}")
        logger.debug(f"   Dialog ID: {event.dialog_id}")
        logger.debug(f"   Domain: {event.domain}")
        logger.debug(f"   Message: '{event.message_text}'")

        # Инициализируем API с вебхуком из .env
        global b24_api
        if not b24_api and BITRIX24_WEBHOOK:
            logger.debug(f"🔧 Инициализация Bitrix24 API с вебхуком: {BITRIX24_WEBHOOK[:50]}...")
            logger.debug(f"🔧 CLIENT_ID: {BITRIX24_CLIENT_ID}")
            logger.debug(f"🔧 BOT_ID: {BITRIX24_BOT_ID}")

            # Преобразуем BOT_ID в число
            bot_id = None
            if BITRIX24_BOT_ID:
                try:
                    bot_id = int(BITRIX24_BOT_ID)
                except ValueError:
                    logger.warning(f"⚠️ BITRIX24_BOT_ID '{BITRIX24_BOT_ID}' не является числом")

            # Используем CLIENT_ID для API запросов
            b24_api = Bitrix24API(BITRIX24_WEBHOOK, BITRIX24_CLIENT_ID, bot_id)

            # Регистрируем команды для кнопок (один раз при старте)
            logger.info("📝 Регистрация команд для кнопок...")
            register_bot_commands(b24_api)

        if not b24_api:
            logger.error("❌ Bitrix24 API не инициализирован - проверьте BITRIX24_WEBHOOK в .env")
            return jsonify({'success': False, 'error': 'API not initialized'}), 500

        # Роутинг событий
        if event.is_message:
            logger.debug(f"➡️ Роутинг: обработка сообщения")
            handle_message_event(event, b24_api)
        elif event.is_command:
            logger.debug(f"➡️ Роутинг: обработка команды")
            handle_command_event(event, b24_api)
        elif event.is_join_chat:
            logger.debug(f"➡️ Роутинг: обработка присоединения к чату")
            handle_start(event, b24_api)
        elif event.is_bot_delete:
            logger.info(f"🗑️ Бот удален из портала {event.domain}")
        elif event.is_app_install:
            logger.info(f"📦 Приложение установлено на портал {event.domain}")
        else:
            logger.warning(f"⚠️ Неизвестный тип события: {event_data.get('event')}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def handle_message_event(event: Bitrix24Event, api: Bitrix24API):
    """Обработка события нового сообщения"""
    message = event.message_text

    logger.info(f"💬 Получено сообщение от User ID {event.user_id}: '{message}'")

    if not message:
        logger.warning("⚠️ Получено пустое сообщение")
        return

    # Обработка команд
    message_lower = message.lower().strip()
    logger.debug(f"🔍 Обработка команды: '{message_lower}'")

    # Команды помощи
    if message_lower in ['/start', '/помощь', 'помощь', 'help', 'старт']:
        logger.debug(f"✅ Распознана команда: help/start")
        handle_start(event, api)
    # Команда категории
    elif message_lower in ['/категории', 'категории', 'категория']:
        logger.debug(f"✅ Распознана команда: категории")
        handle_categories(event, api)
    # Обработка текстовых команд от кнопок (fallback если команды не зарегистрированы)
    elif message_lower.startswith('helpful_yes_') or message_lower.startswith('👍'):
        try:
            # Пытаемся извлечь ID из сообщения
            if '_' in message_lower:
                answer_log_id = int(message_lower.split('_')[-1])
                handle_rating(event, api, answer_log_id, is_helpful=True)
            else:
                logger.debug("⚠️ Не удалось извлечь answer_log_id из сообщения")
        except (ValueError, IndexError):
            logger.error(f"Ошибка парсинга answer_log_id из {message_lower}")
    elif message_lower.startswith('helpful_no_') or message_lower.startswith('👎'):
        try:
            if '_' in message_lower:
                answer_log_id = int(message_lower.split('_')[-1])
                handle_rating(event, api, answer_log_id, is_helpful=False)
            else:
                logger.debug("⚠️ Не удалось извлечь answer_log_id из сообщения")
        except (ValueError, IndexError):
            logger.error(f"Ошибка парсинга answer_log_id из {message_lower}")
    # Обычный поиск по FAQ
    else:
        handle_search_faq(event, api)


def handle_command_event(event: Bitrix24Event, api: Bitrix24API):
    """Обработка события команды (нажатие на кнопку)"""
    command = event.command_name
    params = event.command_params
    command_id = event.command_data.get('COMMAND_ID')
    message_id = event.command_data.get('MESSAGE_ID')

    logger.info(f"🔘 Получена команда от User ID {event.user_id}: '{command}' (params: '{params}')")
    logger.debug(f"   Command ID: {command_id}, Message ID: {message_id}")
    logger.debug(f"   Context: {event.command_context}")

    if not command:
        logger.warning("⚠️ Получена команда без названия")
        return

    command_lower = command.lower().strip()

    # Обработка выбора категории из кнопки
    if command_lower.startswith('cat'):
        # Если есть params, это ID категории, иначе берем из самой команды
        if params:
            category = params
        else:
            category = command_lower[4:] if command_lower.startswith('cat_') else ''
        if category:
            handle_category_select(event, api, category)
    # Положительная оценка
    elif command_lower == 'helpful_yes':
        try:
            answer_log_id = int(params) if params else 0
            if answer_log_id > 0:
                handle_rating(event, api, answer_log_id, is_helpful=True,
                             command_id=command_id, message_id=message_id)
            else:
                logger.error(f"⚠️ Нет answer_log_id в параметрах команды")
        except (ValueError, TypeError):
            logger.error(f"Ошибка парсинга answer_log_id из params: {params}")
    # Отрицательная оценка
    elif command_lower == 'helpful_no':
        try:
            answer_log_id = int(params) if params else 0
            if answer_log_id > 0:
                handle_rating(event, api, answer_log_id, is_helpful=False,
                             command_id=command_id, message_id=message_id)
            else:
                logger.error(f"⚠️ Нет answer_log_id в параметрах команды")
        except (ValueError, TypeError):
            logger.error(f"Ошибка парсинга answer_log_id из params: {params}")
    # Нажатие на похожий вопрос
    elif command_lower == 'similar_question':
        if params:
            # Создаем новый event с текстом вопроса и вызываем поиск
            logger.info(f"🔍 Поиск по похожему вопросу: {params}")
            event.message_text = params  # Подменяем текст сообщения на вопрос из кнопки
            # Передаем is_faq_view=True для добавления префикса в логи
            handle_search_faq(event, api, is_faq_view=True)
            # answer_command не нужен - ответ уже отправлен через handle_search_faq
        else:
            logger.error(f"⚠️ Нет текста вопроса в параметрах команды similar_question")
    else:
        logger.warning(f"⚠️ Неизвестная команда: {command_lower}")


# ========== УПРАВЛЕНИЕ (для web_admin.py) ==========

@app.route('/api/reload-chromadb', methods=['POST'])
def reload_chromadb_endpoint():
    """Endpoint для перезагрузки ChromaDB (вызывается из web_admin.py)"""
    success = reload_chromadb()
    return jsonify({'success': success})


@app.route('/', methods=['GET'])
def index():
    """Информация о боте (для GET запросов)"""
    return jsonify({
        'bot': 'FAQ Bot for Bitrix24',
        'status': 'running',
        'webhook_path': '/ или /webhook/bitrix24',
        'health_check': '/health',
        'chromadb_records': collection.count() if collection else 0
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'chromadb_records': collection.count() if collection else 0,
        'webhook_configured': bool(BITRIX24_WEBHOOK)
    })


# ========== ЗАПУСК ==========

if __name__ == '__main__':
    logger.info("🚀 Запуск FAQ Бота для Bitrix24...")

    # Инициализация БД
    try:
        database.init_database()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

    # Инициализация ChromaDB
    init_chromadb()

    # Проверка конфигурации
    if not BITRIX24_WEBHOOK:
        logger.warning("⚠️ BITRIX24_WEBHOOK не настроен в .env!")
        logger.warning("⚠️ Бот не сможет отправлять сообщения в Bitrix24")
        logger.warning("⚠️ Добавьте BITRIX24_WEBHOOK=https://your-domain.bitrix24.ru/rest/1/webhook_key/ в .env")

    # Запуск Flask сервера
    port = int(os.getenv('BITRIX24_PORT', 5002))
    host = os.getenv('BITRIX24_HOST', '0.0.0.0')

    logger.info(f"📡 Сервер запускается на {host}:{port}")
    logger.info(f"📍 Webhook URL: http://your-server.com:{port}/webhook/bitrix24")
    logger.info(f"📊 Health check: http://your-server.com:{port}/health")
    logger.info("=" * 60)

    app.run(host=host, port=port, debug=False)
