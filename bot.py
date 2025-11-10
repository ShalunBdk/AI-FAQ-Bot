"""
Telegram-бот с ChromaDB + автоперезагрузка после переобучения
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.utils import embedding_functions
from flask import Flask, request, jsonify
import threading
import database
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# ---------- ЛОГИРОВАНИЕ ----------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ---------- КОНФИГ ----------
TELEGRAM_TOKEN = "8006988265:AAFNahJH7opZ7BBe8ysriod5iGyMkJ363gM"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
RELOAD_SERVER_PORT = 5001

# ---------- МОДЕЛЬ ----------
print("Загрузка модели эмбеддингов...")
model = SentenceTransformer(MODEL_NAME)
print("Модель загружена!")

# ---------- Chroma ----------
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)

# Глобальные переменные
collection = None
bot_settings_cache = {}

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
    # Получаем текст приветствия из настроек
    welcome_text = bot_settings_cache.get("start_message", database.DEFAULT_BOT_SETTINGS["start_message"])

    reply_markup = get_categories_keyboard()

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def search_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    user = update.message.from_user
    logger.info(f"Запрос от {user.first_name} ({user.id}): {query}")
    await update.message.reply_text("🔍 Ищу ответ...")

    try:
        best_meta, score, raw_results = find_best_match(query, n_results=3)

        if not best_meta:
            await update.message.reply_text(
                "😔 К сожалению, я не нашёл ответа на ваш вопрос.\n\n"
                "Попробуйте переформулировать или выберите категорию:",
                reply_markup=get_categories_keyboard()
            )
            return

        if score < 50.0:
            # Показываем лучший результат даже если совпадение низкое
            response = f"🤔 <b>Не уверен, что правильно понял вопрос</b> (совпадение {score:.0f}%)\n\n"
            response += f"<b>{best_meta['question']}</b>\n\n{best_meta['answer']}\n\n"
            response += "❓ <i>Это то, что вы искали?</i>"

            # Добавляем кнопки обратной связи и альтернативные варианты
            keyboard = []

            # Кнопки обратной связи
            yes_text = bot_settings_cache.get("feedback_button_yes", database.DEFAULT_BOT_SETTINGS["feedback_button_yes"])
            no_text = bot_settings_cache.get("feedback_button_no", database.DEFAULT_BOT_SETTINGS["feedback_button_no"])
            keyboard.append([
                InlineKeyboardButton(yes_text, callback_data="helpful_yes"),
                InlineKeyboardButton(no_text, callback_data="helpful_no")
            ])

            # Похожие вопросы
            try:
                for i in range(1, min(3, len(raw_results["documents"][0]))):
                    dist = raw_results["distances"][0][i]
                    sim = max(0.0, 1.0 - dist) * 100.0
                    if sim > 30:
                        q = raw_results["metadatas"][0][i]["question"]
                        id_ = raw_results["ids"][0][i] if "ids" in raw_results else None
                        if id_:
                            keyboard.append([InlineKeyboardButton(f"📄 {q[:40]}... ({sim:.0f}%)", callback_data=f"show_{id_}")])
            except Exception:
                pass

            # Кнопка к категориям
            keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])

            await update.message.reply_text(response, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
            return

        response = f"<b>{best_meta['question']}</b>\n\n{best_meta['answer']}\n\n<i>Совпадение: {score:.0f}%</i>"

        # Формируем клавиатуру с кнопками обратной связи
        keyboard = []

        # Кнопки обратной связи всегда добавляем
        yes_text = bot_settings_cache.get("feedback_button_yes", database.DEFAULT_BOT_SETTINGS["feedback_button_yes"])
        no_text = bot_settings_cache.get("feedback_button_no", database.DEFAULT_BOT_SETTINGS["feedback_button_no"])
        keyboard.append([
            InlineKeyboardButton(yes_text, callback_data="helpful_yes"),
            InlineKeyboardButton(no_text, callback_data="helpful_no")
        ])

        # Добавляем похожие вопросы если есть
        try:
            for i in range(1, min(3, len(raw_results["documents"][0]))):
                dist = raw_results["distances"][0][i]
                sim = max(0.0, 1.0 - dist) * 100.0
                if sim > 30:
                    q = raw_results["metadatas"][0][i]["question"]
                    id_ = raw_results["ids"][0][i] if "ids" in raw_results else None
                    if id_:
                        keyboard.append([InlineKeyboardButton(f"📄 {q[:40]}... ({sim:.0f}%)", callback_data=f"show_{id_}")])
        except Exception:
            pass

        # Кнопка назад к категориям
        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])

        await update.message.reply_text(response, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при поиске. Попробуйте ещё раз.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        category_faqs = database.get_faqs_by_category(category)

        response = f"📁 <b>Категория: {category}</b>\n\nПопулярные вопросы:\n\n"
        keyboard = []
        for faq in category_faqs:
            response += f"• {faq['question']}\n"
            keyboard.append([InlineKeyboardButton(faq['question'][:60], callback_data=f"show_{faq['id']}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])
        await query.edit_message_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith("show_"):
        faq_id = data.replace("show_", "")
        try:
            result = collection.get(ids=[faq_id], include=["metadatas", "documents"])
            if result and result.get("metadatas"):
                metadata = result["metadatas"][0]
                response = f"<b>{metadata['question']}</b>\n\n{metadata['answer']}"

                # Формируем клавиатуру с кнопками обратной связи и навигацией
                keyboard = []

                # Кнопки обратной связи
                yes_text = bot_settings_cache.get("feedback_button_yes", database.DEFAULT_BOT_SETTINGS["feedback_button_yes"])
                no_text = bot_settings_cache.get("feedback_button_no", database.DEFAULT_BOT_SETTINGS["feedback_button_no"])
                keyboard.append([
                    InlineKeyboardButton(yes_text, callback_data="helpful_yes"),
                    InlineKeyboardButton(no_text, callback_data="helpful_no")
                ])

                # Кнопка назад к категориям
                keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])

                await query.edit_message_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            else:
                await query.edit_message_text("❌ Не удалось получить запись.", parse_mode='HTML')
        except Exception as e:
            logger.error(f"Ошибка при collection.get: {e}")
            await query.edit_message_text("❌ Ошибка при получении записи.", parse_mode='HTML')

    elif data == "back_to_cats":
        await query.edit_message_text("📚 <b>Выберите категорию:</b>", reply_markup=get_categories_keyboard(), parse_mode='HTML')

    elif data == "helpful_yes":
        # Удаляем кнопки из исходного сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Получаем ответ из настроек и отправляем новое сообщение
        response_yes = bot_settings_cache.get("feedback_response_yes", database.DEFAULT_BOT_SETTINGS["feedback_response_yes"])
        await query.message.reply_text(response_yes, parse_mode='HTML')

    elif data == "helpful_no":
        # Удаляем кнопки из исходного сообщения
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

        # Получаем ответ из настроек и отправляем новое сообщение
        response_no = bot_settings_cache.get("feedback_response_no", database.DEFAULT_BOT_SETTINGS["feedback_response_no"])
        await query.message.reply_text(response_no, parse_mode='HTML')

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
    
    # Запускаем бота
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_faq))

    print("🤖 Бот запущен! Нажмите Ctrl+C для остановки")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()