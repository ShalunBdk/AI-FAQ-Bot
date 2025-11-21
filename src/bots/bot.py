"""
Telegram-бот с ChromaDB + автоперезагрузка после переобучения
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TimedOut, NetworkError, TelegramError, RetryAfter
import httpx
import httpcore
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.utils import embedding_functions
from flask import Flask, request, jsonify
import threading
import sys
import os
import asyncio
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core import database
from src.core import logging_config
from src.core.search import find_answer

# Загружаем переменные окружения из .env
load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False"

# ---------- ЛОГИРОВАНИЕ ----------
logging_config.configure_root_logger(level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ЗАЩИТЫ ОТ ОШИБОК ----------
import time

def put_bot_to_sleep(duration=30):
    """Переводит бота в режим сна на указанное количество секунд"""
    global bot_is_sleeping, sleep_until, timeout_errors_count
    bot_is_sleeping = True
    sleep_until = time.time() + duration
    timeout_errors_count = 0  # Сбрасываем счетчик
    logger.warning(f"🛌 Бот уходит в сон на {duration} секунд из-за проблем с подключением...")

def check_if_bot_awake():
    """Проверяет, не спит ли бот. Возвращает True если бот проснулся"""
    global bot_is_sleeping, sleep_until
    if bot_is_sleeping and time.time() >= sleep_until:
        bot_is_sleeping = False
        sleep_until = None
        logger.info("✅ Бот проснулся и готов к работе!")
        return True
    return not bot_is_sleeping

def record_timeout_error():
    """Записывает ошибку таймаута и проверяет, нужно ли отправить бота спать"""
    global timeout_errors_count, last_error_time

    current_time = time.time()

    # Если прошло больше 5 минут с последней ошибки, сбрасываем счетчик
    if last_error_time and (current_time - last_error_time) > 300:
        timeout_errors_count = 0

    timeout_errors_count += 1
    last_error_time = current_time

    # Если за короткое время произошло 3+ ошибок, отправляем бота спать
    if timeout_errors_count >= 3:
        put_bot_to_sleep(10)
        return True
    return False

async def safe_send_message(func, *args, max_retries=3, user_id=None, **kwargs):
    """
    Обертка для безопасной отправки сообщений с повторными попытками при ошибках

    Args:
        func: async функция отправки сообщения (reply_text, edit_message_text и т.д.)
        max_retries: максимальное количество попыток
        user_id: ID пользователя (для user-level rate limiting)
        *args, **kwargs: аргументы для функции

    Returns:
        Result of func or None if all retries failed
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except RetryAfter as e:
            # Rate limit от Telegram - это проблема конкретного пользователя, не всего бота
            retry_after = e.retry_after
            logger.warning(f"Rate limit от Telegram для пользователя {user_id}: retry_after={retry_after}с")

            # Отправляем пользователя в кулдаун
            if user_id:
                put_user_in_cooldown(user_id, duration=int(retry_after) + 5)

            # Не переповторяем, просто возвращаем None
            return None
        except (httpx.RemoteProtocolError, httpcore.RemoteProtocolError) as e:
            # Сервер разорвал соединение
            if record_timeout_error():
                return None

            wait_time = (attempt + 1) * 2
            logger.warning(f"Сервер разорвал соединение (попытка {attempt + 1}/{max_retries}). Ожидание {wait_time}с...")
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Соединение разорвано после {max_retries} попыток: {e}")
                return None
        except (httpx.ConnectError, httpcore.ConnectError) as e:
            # Ошибка подключения
            if record_timeout_error():
                return None

            wait_time = (attempt + 1) * 2
            logger.warning(f"Ошибка подключения (попытка {attempt + 1}/{max_retries}). Ожидание {wait_time}с...")
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Не удалось подключиться после {max_retries} попыток: {e}")
                return None
        except (httpx.ReadTimeout, httpcore.ReadTimeout, TimedOut) as e:
            # Записываем ошибку таймаута
            if record_timeout_error():
                # Бот ушел в сон, прекращаем попытки
                return None

            wait_time = (attempt + 1) * 2  # Экспоненциальная задержка: 2, 4, 6 секунд
            logger.warning(f"Timeout при отправке сообщения (попытка {attempt + 1}/{max_retries}). Ожидание {wait_time}с...")
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Не удалось отправить сообщение после {max_retries} попыток: {e}")
                return None
        except NetworkError as e:
            # Записываем сетевую ошибку как таймаут
            if record_timeout_error():
                # Бот ушел в сон, прекращаем попытки
                return None

            wait_time = (attempt + 1) * 2
            logger.warning(f"Сетевая ошибка (попытка {attempt + 1}/{max_retries}). Ожидание {wait_time}с...")
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Сетевая ошибка после {max_retries} попыток: {e}")
                return None
        except TelegramError as e:
            # Другие ошибки Telegram API (не повторяем попытки для них)
            logger.error(f"Telegram API ошибка: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке сообщения: {e}", exc_info=True)
            return None
    return None

# ---------- КОНФИГ ----------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден в .env файле! Создайте .env и укажите токен бота.")

MODEL_NAME = os.getenv("MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
RELOAD_SERVER_PORT = 5001

# Порог схожести для показа ответа (в процентах, 0-100)
# Если не указан в .env, используется 45%
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "45.0"))

# ---------- МОДЕЛЬ ----------
print("Загрузка модели эмбеддингов...")
model = SentenceTransformer(MODEL_NAME)
print("Модель загружена!")
print(f"⚙️  Порог схожести для показа ответа: {SIMILARITY_THRESHOLD}%")

# ---------- Chroma ----------
CHROMA_PATH = os.getenv('CHROMA_PATH', './data/chroma_db')
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)

# Глобальные переменные
collection = None
bot_settings_cache = {}
bot_is_sleeping = False
sleep_until = None
timeout_errors_count = 0
last_error_time = None

# User-level rate limiting
user_last_action = {}  # {user_id: timestamp}
user_cooldown = {}  # {user_id: cooldown_until_timestamp}
user_last_callback = {}  # {user_id: (callback_data, timestamp)} для debouncing

def check_user_rate_limit(user_id: int, min_interval: float = 0.5) -> bool:
    """
    Проверяет, не слишком ли часто пользователь отправляет запросы.

    Args:
        user_id: ID пользователя
        min_interval: минимальный интервал между действиями в секундах

    Returns:
        True если можно обработать запрос, False если пользователь спамит
    """
    current_time = time.time()

    # Проверяем, не в кулдауне ли пользователь
    if user_id in user_cooldown:
        if current_time < user_cooldown[user_id]:
            remaining = int(user_cooldown[user_id] - current_time)
            logger.warning(f"Пользователь {user_id} в кулдауне. Осталось {remaining}с")
            return False
        else:
            # Кулдаун истек
            del user_cooldown[user_id]

    # Проверяем частоту запросов
    if user_id in user_last_action:
        time_since_last = current_time - user_last_action[user_id]
        if time_since_last < min_interval:
            logger.info(f"Пользователь {user_id} слишком быстро отправляет запросы ({time_since_last:.2f}с)")
            return False

    user_last_action[user_id] = current_time
    return True

def put_user_in_cooldown(user_id: int, duration: int = 10):
    """Отправляет конкретного пользователя в кулдаун"""
    user_cooldown[user_id] = time.time() + duration
    logger.warning(f"⏱️ Пользователь {user_id} отправлен в кулдаун на {duration}с из-за спама")

def check_callback_debounce(user_id: int, callback_data: str, debounce_time: float = 1.0) -> bool:
    """
    Проверяет, не является ли это повторным нажатием той же кнопки.

    Args:
        user_id: ID пользователя
        callback_data: данные callback кнопки
        debounce_time: время в секундах для игнорирования повторных нажатий

    Returns:
        True если это новое действие, False если это дубликат
    """
    current_time = time.time()

    if user_id in user_last_callback:
        last_data, last_time = user_last_callback[user_id]
        if last_data == callback_data and (current_time - last_time) < debounce_time:
            logger.info(f"Игнорируем повторное нажатие кнопки '{callback_data}' от пользователя {user_id}")
            return False

    user_last_callback[user_id] = (callback_data, current_time)
    return True

def reload_bot_settings():
    """Перезагружает настройки бота из БД"""
    global bot_settings_cache
    try:
        bot_settings_cache = database.get_bot_settings()
        logger.info(f"✅ Настройки бота загружены: {len(bot_settings_cache)} параметров")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке настроек бота: {e}")
        # Используем дефолтные настройки в случае ошибки
        bot_settings_cache = database.DEFAULT_BOT_SETTINGS.copy()
        return False

def reload_collection():
    """Перезагружает коллекцию ChromaDB"""
    global collection
    try:
        collection = chroma_client.get_collection(name="faq_collection")
        logger.info(f"✅ Коллекция перезагружена! Записей: {collection.count()}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при перезагрузке коллекции: {e}")
        try:
            collection = chroma_client.create_collection(
                name="faq_collection",
                embedding_function=embedding_func,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Создана новая пустая коллекция")
            return True
        except Exception as e2:
            logger.error(f"❌ Не удалось создать коллекцию: {e2}")
            return False

# Инициализация коллекции и настроек при старте
reload_collection()
reload_bot_settings()

# ---------- FLASK СЕРВЕР ДЛЯ ПРИЁМА КОМАНД ----------
flask_app = Flask(__name__)

@flask_app.route('/reload', methods=['POST'])
def handle_reload():
    """Эндпоинт для перезагрузки коллекции"""
    logger.info("📡 Получен запрос на перезагрузку коллекции")
    success = reload_collection()
    if success:
        return jsonify({"status": "ok", "message": "Коллекция перезагружена"}), 200
    else:
        return jsonify({"status": "error", "message": "Ошибка перезагрузки"}), 500

@flask_app.route('/reload-settings', methods=['POST'])
def handle_reload_settings():
    """Эндпоинт для перезагрузки настроек бота"""
    logger.info("📡 Получен запрос на перезагрузку настроек бота")
    success = reload_bot_settings()
    if success:
        return jsonify({"status": "ok", "message": "Настройки бота перезагружены"}), 200
    else:
        return jsonify({"status": "error", "message": "Ошибка перезагрузки настроек"}), 500

@flask_app.route('/health', methods=['GET'])
def health_check():
    """Проверка работоспособности"""
    return jsonify({
        "status": "ok",
        "collection_count": collection.count() if collection else 0
    }), 200

def run_flask():
    """Запуск Flask-сервера в отдельном потоке"""
    flask_app.run(host='127.0.0.1', port=RELOAD_SERVER_PORT, debug=False, use_reloader=False)

# ---------- ИНИЦИАЛИЗАЦИЯ ДАННЫХ ----------
def init_demo_data():
    """Инициализация данных в Chroma из БД (если пусто)"""
    try:
        if collection.count() > 0:
            print(f"В базе уже есть {collection.count()} записей")
            return

        print("Добавление данных из БД в векторную БД...")

        all_faqs = database.get_all_faqs()

        if not all_faqs:
            print("⚠️ В базе данных нет FAQ. Запустите migrate_data.py для миграции данных.")
            return

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

        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        print(f"✅ Добавлено {len(all_faqs)} записей в базу знаний")

    except Exception as e:
        print(f"❌ Ошибка при инициализации данных: {e}")

# ---------- ПОИСК ----------
def find_best_match(query_text: str, n_results: int = 3):
    """
    Поиск в Chroma: возвращает (best_metadata, best_score_percent, results_struct)
    """
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"Chroma query error: {e}")
        return None, 0.0, None

    if not results or "documents" not in results or not results["documents"] or not results["documents"][0]:
        logger.info("Ничего не найдено в Chroma")
        return None, 0.0, results

    try:
        best_meta = results["metadatas"][0][0]
        best_distance = results["distances"][0][0]
    except Exception as e:
        logger.error(f"Ошибка при разборе результатов Chroma: {e}")
        return None, 0.0, results

    similarity = max(0.0, 1.0 - best_distance) * 100.0

    logger.info(f"Найдено результатов: {len(results['documents'][0])}, лучший score: {similarity:.1f}%")
    return best_meta, similarity, results

# ---------- БОТ: хендлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, не спит ли бот
    if not check_if_bot_awake():
        remaining_time = int(sleep_until - time.time())
        logger.info(f"Бот спит. Осталось {remaining_time} секунд")
        try:
            await update.message.reply_text(
                f"⚠️ Извините, сейчас возникли технические проблемы с подключением к Telegram.\n"
                f"Бот автоматически возобновит работу через {remaining_time} сек.\n\n"
                f"Пожалуйста, повторите ваш запрос через несколько секунд."
            )
        except Exception:
            pass
        return

    # Получаем текст приветствия из настроек
    welcome_text = bot_settings_cache.get("start_message", database.DEFAULT_BOT_SETTINGS["start_message"])

    reply_markup = get_categories_keyboard()

    result = await safe_send_message(
        update.message.reply_text,
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    if result is None:
        logger.error("Не удалось отправить приветственное сообщение пользователю")

async def search_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск ответа на вопрос пользователя через каскадную систему"""
    # Проверяем, не спит ли бот
    if not check_if_bot_awake():
        remaining_time = int(sleep_until - time.time())
        logger.info(f"Бот спит. Осталось {remaining_time} секунд")
        try:
            await update.message.reply_text(
                f"⚠️ Извините, сейчас возникли технические проблемы с подключением к Telegram.\n"
                f"Бот автоматически возобновит работу через {remaining_time} сек.\n\n"
                f"Пожалуйста, повторите ваш запрос через несколько секунд."
            )
        except Exception:
            pass
        return

    query = update.message.text
    user = update.message.from_user
    logger.info(f"Запрос от {user.first_name} ({user.id}): {query}")
    await safe_send_message(update.message.reply_text, "🔍 Ищу ответ...")

    # Логирование запроса
    query_log_id = database.add_query_log(
        user_id=user.id,
        username=user.username or user.first_name,
        query_text=query,
        platform='telegram'
    )

    try:
        # === КАСКАДНЫЙ ПОИСК ===
        result = find_answer(query, collection)

        if result.found:
            # Нашли ответ!
            logger.info(f"✅ Ответ найден через {result.search_level} (confidence: {result.confidence:.1f}%)")

            # Логируем показанный ответ
            answer_log_id = None
            if query_log_id:
                answer_log_id = database.add_answer_log(
                    query_log_id=query_log_id,
                    faq_id=result.faq_id,
                    similarity_score=result.confidence,
                    answer_shown=result.answer,
                    search_level=result.search_level
                )

            # Формируем ответ
            response = f"<b>{result.question}</b>\n\n{result.answer}"

            # Добавляем процент схожести если включено в настройках
            show_similarity = bot_settings_cache.get("show_similarity", "true") == "true"
            if show_similarity:
                search_level_icons = {
                    'exact': '🎯',
                    'keyword': '🔑',
                    'semantic': '🧠',
                }
                icon = search_level_icons.get(result.search_level, '🔍')
                response += f"\n\n<i>{icon} Совпадение: {result.confidence:.0f}%</i>"

            # Формируем клавиатуру с кнопками обратной связи
            keyboard = []

            # Кнопки обратной связи
            yes_text = bot_settings_cache.get("feedback_button_yes", database.DEFAULT_BOT_SETTINGS["feedback_button_yes"])
            no_text = bot_settings_cache.get("feedback_button_no", database.DEFAULT_BOT_SETTINGS["feedback_button_no"])
            keyboard.append([
                InlineKeyboardButton(yes_text, callback_data=f"helpful_yes_{answer_log_id or 0}"),
                InlineKeyboardButton(no_text, callback_data=f"helpful_no_{answer_log_id or 0}")
            ])

            # Похожие вопросы (только для semantic search)
            if result.search_level == 'semantic' and result.all_results:
                try:
                    semantic_threshold = float(bot_settings_cache.get('semantic_match_threshold', 45))
                    for i in range(1, min(3, len(result.all_results["documents"][0]))):
                        dist = result.all_results["distances"][0][i]
                        sim = max(0.0, 1.0 - dist) * 100.0
                        if sim > semantic_threshold:
                            q = result.all_results["metadatas"][0][i]["question"]
                            id_ = result.all_results["ids"][0][i]
                            if id_:
                                keyboard.append([InlineKeyboardButton(
                                    f"📄 {q[:40]}... ({sim:.0f}%)",
                                    callback_data=f"show_{id_}"
                                )])
                except Exception:
                    pass

            # Кнопка назад к категориям
            keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])

            await safe_send_message(
                update.message.reply_text,
                response,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        else:
            # Ответ не найден - используем fallback
            logger.warning(f"❌ Ответ не найден для запроса: '{query}' от пользователя {user.id}")

            # Логируем отсутствие ответа
            if query_log_id:
                database.add_answer_log(
                    query_log_id=query_log_id,
                    faq_id=None,
                    similarity_score=0.0,
                    answer_shown=result.message or "Ответ не найден",
                    search_level='none'
                )

            await safe_send_message(
                update.message.reply_text,
                result.message,
                reply_markup=get_categories_keyboard()
            )

    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await safe_send_message(
            update.message.reply_text,
            "⚠️ Произошла ошибка при поиске. Попробуйте ещё раз."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    # Проверяем, не спит ли бот
    if not check_if_bot_awake():
        remaining_time = int(sleep_until - time.time())
        logger.info(f"Бот спит. Осталось {remaining_time} секунд")
        try:
            await query.answer(
                f"⚠️ Технические проблемы с подключением.\nБот возобновит работу через {remaining_time}с",
                show_alert=True
            )
        except Exception:
            pass
        return

    # Проверка debouncing - игнорируем повторные клики по той же кнопке
    if not check_callback_debounce(user.id, data, debounce_time=1.0):
        # Просто отвечаем на callback без обработки
        try:
            await query.answer(cache_time=2)
        except Exception:
            pass
        return

    # Проверка user-level rate limiting
    if not check_user_rate_limit(user.id, min_interval=0.3):
        try:
            # Если пользователь в кулдауне, показываем предупреждение
            if user.id in user_cooldown:
                remaining = int(user_cooldown[user.id] - time.time())
                await query.answer(
                    f"⏱️ Слишком много запросов. Подождите {remaining}с",
                    show_alert=True,
                    cache_time=5
                )
            else:
                # Просто игнорируем слишком быстрые клики
                await query.answer(cache_time=1)
        except Exception:
            pass
        return

    # Стандартный ответ на callback
    try:
        await query.answer()
    except RetryAfter as e:
        # Rate limit от Telegram
        put_user_in_cooldown(user.id, duration=int(e.retry_after) + 5)
        logger.warning(f"Rate limit для пользователя {user.id} в button_callback")
        return
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback query: {e}")

    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        category_faqs = database.get_faqs_by_category(category)

        response = f"📁 <b>Категория: {category}</b>\n\nПопулярные вопросы:\n\n"
        keyboard = []
        for faq in category_faqs:
            response += f"• {faq['question']}\n"
            keyboard.append([InlineKeyboardButton(faq['question'][:60], callback_data=f"show_{faq['id']}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])
        await safe_send_message(
            query.edit_message_text,
            response,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',
            user_id=user.id
        )

    elif data.startswith("show_"):
        faq_id = data.replace("show_", "")
        try:
            result = collection.get(ids=[faq_id], include=["metadatas", "documents"])
            if result and result.get("metadatas"):
                metadata = result["metadatas"][0]
                response = f"<b>{metadata['question']}</b>\n\n{metadata['answer']}"

                # Логируем просмотр FAQ через кнопку
                query_log_id = database.add_query_log(
                    user_id=user.id,
                    username=user.username or user.first_name,
                    query_text=f"[Просмотр FAQ] {metadata['question']}",
                    platform='telegram'
                )

                answer_log_id = None
                if query_log_id:
                    answer_log_id = database.add_answer_log(
                        query_log_id=query_log_id,
                        faq_id=faq_id,
                        similarity_score=100.0,  # Прямой просмотр = 100%
                        answer_shown=metadata['answer'],
                        search_level='direct'  # Прямой просмотр через кнопку
                    )

                # Формируем клавиатуру с кнопками обратной связи и навигацией
                keyboard = []

                # Кнопки обратной связи
                yes_text = bot_settings_cache.get("feedback_button_yes", database.DEFAULT_BOT_SETTINGS["feedback_button_yes"])
                no_text = bot_settings_cache.get("feedback_button_no", database.DEFAULT_BOT_SETTINGS["feedback_button_no"])
                keyboard.append([
                    InlineKeyboardButton(yes_text, callback_data=f"helpful_yes_{answer_log_id or 0}"),
                    InlineKeyboardButton(no_text, callback_data=f"helpful_no_{answer_log_id or 0}")
                ])

                # Кнопка назад к категориям
                keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])

                await safe_send_message(
                    query.edit_message_text,
                    response,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='HTML',
                    user_id=user.id
                )
            else:
                await safe_send_message(
                    query.edit_message_text,
                    "❌ Не удалось получить запись.",
                    parse_mode='HTML',
                    user_id=user.id
                )
        except Exception as e:
            logger.error(f"Ошибка при collection.get: {e}")
            await safe_send_message(
                query.edit_message_text,
                "❌ Ошибка при получении записи.",
                parse_mode='HTML',
                user_id=user.id
            )

    elif data == "back_to_cats":
        # Удаляем кнопки из исходного сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Отправляем новое сообщение с категориями
        await safe_send_message(
            query.message.reply_text,
            "📚 <b>Выберите категорию:</b>",
            reply_markup=get_categories_keyboard(),
            parse_mode='HTML',
            user_id=user.id
        )

    elif data.startswith("helpful_yes_"):
        answer_log_id = int(data.replace("helpful_yes_", ""))
        user = query.from_user

        # Логируем положительную оценку
        if answer_log_id > 0:
            database.add_rating_log(
                answer_log_id=answer_log_id,
                user_id=user.id,
                rating="helpful"
            )

        # Удаляем кнопки из исходного сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Получаем ответ из настроек и отправляем новое сообщение
        response_yes = bot_settings_cache.get("feedback_response_yes", database.DEFAULT_BOT_SETTINGS["feedback_response_yes"])
        await safe_send_message(
            query.message.reply_text,
            response_yes,
            parse_mode='HTML',
            user_id=user.id
        )

    elif data.startswith("helpful_no_"):
        answer_log_id = int(data.replace("helpful_no_", ""))

        # Логируем отрицательную оценку
        if answer_log_id > 0:
            database.add_rating_log(
                answer_log_id=answer_log_id,
                user_id=user.id,
                rating="not_helpful"
            )

        # Удаляем кнопки из исходного сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Получаем ответ из настроек и отправляем новое сообщение
        response_no = bot_settings_cache.get("feedback_response_no", database.DEFAULT_BOT_SETTINGS["feedback_response_no"])
        await safe_send_message(
            query.message.reply_text,
            response_no,
            parse_mode='HTML',
            user_id=user.id
        )

# ---------- ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ----------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок для бота"""
    error = context.error

    # Проверяем тип ошибки для более детального логирования
    if isinstance(error, RetryAfter):
        # Rate limit от Telegram - обрабатываем на уровне пользователя
        retry_after = error.retry_after
        if isinstance(update, Update) and update.effective_user:
            user_id = update.effective_user.id
            put_user_in_cooldown(user_id, duration=int(retry_after) + 5)
            logger.warning(f"⏱️ Rate limit для пользователя {user_id}: retry_after={retry_after}с")
        else:
            logger.warning(f"⏱️ Rate limit (глобальный): retry_after={retry_after}с")
        return

    # Обработка ошибок подключения (RemoteProtocolError, ConnectionError и т.д.)
    if isinstance(error, (httpx.RemoteProtocolError, httpcore.RemoteProtocolError)):
        logger.warning(f"⚠️ Сервер Telegram разорвал соединение: {error}")
        if record_timeout_error():
            logger.warning("🛌 Бот переведен в режим сна из-за проблем с соединением")
        return

    if isinstance(error, (httpx.ConnectError, httpcore.ConnectError)):
        logger.warning(f"⚠️ Не удалось подключиться к серверу Telegram: {error}")
        if record_timeout_error():
            logger.warning("🛌 Бот переведен в режим сна из-за проблем с подключением")
        return

    if isinstance(error, (httpx.ReadTimeout, httpcore.ReadTimeout)):
        logger.warning(f"⚠️ Таймаут чтения от сервера Telegram: {error}")
        if record_timeout_error():
            logger.warning("🛌 Бот переведен в режим сна из-за таймаутов")
        return

    # Если это ошибка таймаута или общая сетевая ошибка
    if isinstance(error, TimedOut):
        logger.warning(f"⏰ Таймаут при обращении к Telegram API: {error}")
        if record_timeout_error():
            logger.warning("🛌 Бот переведен в режим сна из-за множественных таймаутов")
        return

    if isinstance(error, NetworkError):
        logger.warning(f"🌐 Сетевая ошибка при обращении к Telegram API: {error}")
        if record_timeout_error():
            logger.warning("🛌 Бот переведен в режим сна из-за сетевых проблем")
        return

    # Другие ошибки Telegram API
    if isinstance(error, TelegramError):
        logger.error(f"❌ Telegram API ошибка: {error}", exc_info=error)
        # Не отправляем бота в сон для других ошибок API
    else:
        # Неожиданная ошибка - логируем с полным стектрейсом
        logger.error("❌ Неожиданное исключение при обработке обновления:", exc_info=error)

    # Пытаемся уведомить пользователя об ошибке (только если это не сетевая проблема)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже."
            )
        except Exception:
            # Если не удалось отправить сообщение, просто игнорируем
            pass

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------
def get_categories_keyboard():
    categories = database.get_all_categories()

    keyboard = []
    row = []
    for i, cat in enumerate(categories, start=1):
        row.append(InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)

# ---------- MAIN ----------
def main():
    # Инициализируем БД
    database.init_database()
    init_demo_data()
    
    # Запускаем Flask-сервер в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"🔄 Сервер перезагрузки запущен на http://127.0.0.1:{RELOAD_SERVER_PORT}")
    
    # Запускаем бота с увеличенными таймаутами и улучшенной обработкой ошибок
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .connect_timeout(30.0)      # Таймаут подключения: 30 секунд
        .read_timeout(60.0)         # Таймаут чтения: 60 секунд (для long polling)
        .write_timeout(30.0)        # Таймаут записи: 30 секунд
        .pool_timeout(30.0)         # Таймаут pool: 30 секунд
        .get_updates_connect_timeout(60.0)  # Таймаут для getUpdates (long polling)
        .get_updates_read_timeout(60.0)     # Таймаут чтения для getUpdates
        .get_updates_write_timeout(30.0)    # Таймаут записи для getUpdates
        .get_updates_pool_timeout(30.0)     # Таймаут pool для getUpdates
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_faq))

    # Регистрируем глобальный обработчик ошибок
    app.add_error_handler(error_handler)

    print("🤖 Бот запущен! Нажмите Ctrl+C для остановки")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()