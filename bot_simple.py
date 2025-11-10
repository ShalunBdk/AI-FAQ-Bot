"""
Telegram-бот с простым векторным поиском (без ChromaDB)
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from simple_vector_search import SimpleVectorSearch
import database

# ---------- ЛОГИРОВАНИЕ ----------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- КОНФИГ ----------
TELEGRAM_TOKEN = "8006988265:AAFNahJH7opZ7BBe8ysriod5iGyMkJ363gM"

# ---------- Векторный поиск ----------
vector_search = SimpleVectorSearch()

# ---------- ИНИЦИАЛИЗАЦИЯ ДАННЫХ ----------
def init_vector_search():
    """Инициализация векторного поиска из БД"""
    try:
        # Пробуем загрузить из кэша
        if vector_search.load_cache():
            return

        print("Добавление данных из БД в векторный поиск...")

        # Получаем все FAQ из базы данных
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

        # Добавляем в векторный поиск
        vector_search.add_documents(documents, metadatas, ids)
        print(f"✅ Добавлено {len(all_faqs)} записей в векторный поиск")

    except Exception as e:
        print(f"❌ Ошибка при инициализации данных: {e}")

# ---------- ПОИСК ----------
def find_best_match(query_text: str, n_results: int = 3):
    """
    Поиск: возвращает (best_metadata, best_score_percent, results_struct)
    """
    try:
        results = vector_search.query(query_text, n_results=n_results)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return None, 0.0, None

    # Проверки на пустой результат
    if not results or "documents" not in results or not results["documents"] or not results["documents"][0]:
        logger.info("Ничего не найдено")
        return None, 0.0, results

    # Берём лучший (первый) результат
    try:
        best_meta = results["metadatas"][0][0]
        best_distance = results["distances"][0][0]
    except Exception as e:
        logger.error(f"Ошибка при разборе результатов: {e}")
        return None, 0.0, results

    # Преобразуем distance -> similarity%
    similarity = max(0.0, 1.0 - best_distance) * 100.0

    logger.info(f"Найдено результатов: {len(results['documents'][0])}, лучший score: {similarity:.1f}%")
    return best_meta, similarity, results

# ---------- БОТ: хендлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = """👋 **Добро пожаловать в корпоративный бот-помощник!**

Я помогу найти ответы на вопросы о работе в компании.

💡 **Просто напишите свой вопрос**, например:
• "Можно ли в шортах на работу?"
• "Мне меньше денег пришло"
• "Где взять спецовку?"
• "Как отправить посылку?"

📚 Или выберите категорию:"""

    keyboard = [
        [InlineKeyboardButton("👔 HR", callback_data="cat_HR"),
         InlineKeyboardButton("💰 Бухгалтерия", callback_data="cat_Бухгалтерия")],
        [InlineKeyboardButton("🏭 Производство", callback_data="cat_Производство"),
         InlineKeyboardButton("💻 ИТ", callback_data="cat_ИТ")],
        [InlineKeyboardButton("🗂 Офис-менеджер", callback_data="cat_Офис-менеджер"),
         InlineKeyboardButton("⚖️ Юристы", callback_data="cat_Юристы")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

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

        # Порог можно настроить
        if score < 50.0:
            await update.message.reply_text(
                f"🤔 Не уверен, что правильно понял вопрос (совпадение {score:.0f}%).\n\n"
                "Попробуйте переформулировать или выберите категорию:",
                reply_markup=get_categories_keyboard()
            )
            return

        # Формируем ответ
        response = f"**{best_meta['question']}**\n\n{best_meta['answer']}\n\n_Совпадение: {score:.0f}%_"

        # Опционально: предложить похожие вопросы из raw_results
        reply_markup = get_feedback_keyboard()
        # Пример добавления похожих вопросов в клавиатуру (если есть)
        try:
            related_keyboard = []
            # raw_results содержит документы/metadatas/distances по порядку
            for i in range(1, min(3, len(raw_results["documents"][0]))):
                dist = raw_results["distances"][0][i]
                sim = max(0.0, 1.0 - dist) * 100.0
                if sim > 30:
                    q = raw_results["metadatas"][0][i]["question"]
                    id_ = raw_results["ids"][0][i] if "ids" in raw_results else None
                    if id_:
                        related_keyboard.append([InlineKeyboardButton(f"📄 {q[:40]}... ({sim:.0f}%)", callback_data=f"show_{id_}")])
            if related_keyboard:
                related_keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])
                reply_markup = InlineKeyboardMarkup(related_keyboard)
        except Exception:
            # Игнорируем если нет related
            pass

        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при поиске. Попробуйте ещё раз.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        # Фильтрация по категории из БД
        category_faqs = database.get_faqs_by_category(category)

        response = f"📁 **Категория: {category}**\n\nПопулярные вопросы:\n\n"
        keyboard = []
        for faq in category_faqs:
            response += f"• {faq['question']}\n"
            keyboard.append([InlineKeyboardButton(faq['question'][:60], callback_data=f"show_{faq['id']}")])

        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_cats")])
        await query.edit_message_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data.startswith("show_"):
        faq_id = data.replace("show_", "")
        # Используем vector_search.get
        try:
            result = vector_search.get(ids=[faq_id])
            if result and result.get("metadatas"):
                metadata = result["metadatas"][0]
                response = f"**{metadata['question']}**\n\n{metadata['answer']}"
                await query.edit_message_text(response, reply_markup=get_feedback_keyboard(), parse_mode='Markdown')
            else:
                await query.edit_message_text("❌ Не удалось получить запись.", parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка при получении FAQ: {e}")
            await query.edit_message_text("❌ Ошибка при получении записи.", parse_mode='Markdown')

    elif data == "back_to_cats":
        await query.edit_message_text("📚 **Выберите категорию:**", reply_markup=get_categories_keyboard(), parse_mode='Markdown')

    elif data == "helpful_yes":
        await query.edit_message_text(f"{query.message.text}\n\n✅ **Спасибо за отзыв!**")
    elif data == "helpful_no":
        await query.edit_message_text(f"{query.message.text}\n\n😔 Извините, что не помог.\n\n📞 Обратитесь в HR: доб. 101")

# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------
def get_categories_keyboard():
    keyboard = [
        [InlineKeyboardButton("👔 HR", callback_data="cat_HR"),
         InlineKeyboardButton("💰 Бухгалтерия", callback_data="cat_Бухгалтерия")],
        [InlineKeyboardButton("🏭 Производство", callback_data="cat_Производство"),
         InlineKeyboardButton("💻 ИТ", callback_data="cat_ИТ")],
        [InlineKeyboardButton("🗂 Офис-менеджер", callback_data="cat_Офис-менеджер"),
         InlineKeyboardButton("⚖️ Юристы", callback_data="cat_Юристы")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_feedback_keyboard():
    keyboard = [
        [InlineKeyboardButton("👍 Полезно", callback_data="helpful_yes"),
         InlineKeyboardButton("👎 Не помогло", callback_data="helpful_no")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------- MAIN ----------
def main():
    # Инициализируем БД
    database.init_database()
    init_vector_search()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_faq))

    print("🤖 Бот запущен! Нажмите Ctrl+C для остановки")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
