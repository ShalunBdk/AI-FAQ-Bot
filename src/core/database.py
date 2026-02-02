# database.py
# -*- coding: utf-8 -*-
"""
Модуль для работы с базой данных FAQ
"""

import sqlite3
from typing import List, Dict, Optional
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

DB_FILE = "data/faq_database.db"

# Порог схожести для фильтрации (в процентах)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "45.0"))

# Часовой пояс UTC+7
UTC7_TZ = timezone(timedelta(hours=7))


def convert_utc_to_utc7(utc_timestamp_str: Optional[str]) -> Optional[str]:
    """
    Конвертирует UTC timestamp из БД в UTC+7

    :param utc_timestamp_str: Timestamp в формате SQLite (например, '2024-01-01 12:00:00')
    :return: Timestamp в формате UTC+7 или None
    """
    if not utc_timestamp_str:
        return None

    try:
        # Парсим UTC timestamp
        utc_dt = datetime.strptime(utc_timestamp_str, '%Y-%m-%d %H:%M:%S')
        # Добавляем информацию о timezone (UTC)
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        # Конвертируем в UTC+7
        utc7_dt = utc_dt.astimezone(UTC7_TZ)
        # Возвращаем в формате строки
        return utc7_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"Ошибка конвертации timestamp: {e}")
        return utc_timestamp_str


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД"""
    # Создаём директорию для БД, если её нет
    db_dir = os.path.dirname(DB_FILE)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """Создание таблиц в БД"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Таблица FAQ
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faq (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                keywords TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Триггер для автообновления updated_at
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_faq_timestamp
            AFTER UPDATE ON faq
            BEGIN
                UPDATE faq SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # Таблица настроек бота
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Триггер для автообновления updated_at настроек
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_bot_settings_timestamp
            AFTER UPDATE ON bot_settings
            BEGIN
                UPDATE bot_settings SET updated_at = CURRENT_TIMESTAMP WHERE key = NEW.key;
            END
        """)

        # Таблица логов запросов пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                query_text TEXT NOT NULL,
                platform TEXT DEFAULT 'telegram',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица логов ответов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_log_id INTEGER,
                faq_id TEXT,
                similarity_score REAL,
                answer_shown TEXT,
                search_level TEXT DEFAULT 'semantic',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (query_log_id) REFERENCES query_logs(id),
                FOREIGN KEY (faq_id) REFERENCES faq(id)
            )
        """)

        # Таблица оценок ответов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rating_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer_log_id INTEGER,
                user_id INTEGER NOT NULL,
                rating TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (answer_log_id) REFERENCES answer_logs(id)
            )
        """)

        # Таблица метаданных LLM генерации (RAG)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer_log_id INTEGER NOT NULL,

                -- LLM Metadata
                model TEXT,
                chunks_used INTEGER,
                chunks_data TEXT,
                pii_detected INTEGER,

                -- Token Usage
                tokens_prompt INTEGER,
                tokens_completion INTEGER,
                tokens_total INTEGER,

                -- Generation Info
                finish_reason TEXT,
                generation_time_ms INTEGER,
                error_message TEXT,

                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (answer_log_id) REFERENCES answer_logs(id)
            )
        """)

        # Таблица прав доступа для Bitrix24
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bitrix24_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT,
                role TEXT NOT NULL CHECK(role IN ('admin', 'observer')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                UNIQUE(domain, user_id)
            )
        """)

        # Таблица истории рассылок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                status TEXT DEFAULT 'draft',
                total_recipients INTEGER DEFAULT 0,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0
            )
        """)

        # Детальный лог отправки каждому пользователю
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broadcast_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                sent_at TIMESTAMP,
                FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id)
            )
        """)

        # Индексы для оптимизации
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp ON query_logs(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_user ON query_logs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_platform ON query_logs(platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_answer_logs_faq ON answer_logs(faq_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_logs_rating ON rating_logs(rating)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_generations_answer_log ON llm_generations(answer_log_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_generations_model ON llm_generations(model)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_llm_generations_error ON llm_generations(error_message)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bitrix24_permissions_domain ON bitrix24_permissions(domain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bitrix24_permissions_domain_user ON bitrix24_permissions(domain, user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bitrix24_permissions_role ON bitrix24_permissions(role)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcasts_status ON broadcasts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_logs_broadcast ON broadcast_logs(broadcast_id)")

        print("OK: База данных инициализирована")

    # Инициализируем настройки бота
    init_bot_settings()


def get_all_faqs() -> List[Dict]:
    """Получить все FAQ из БД"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faq ORDER BY category, id")
        rows = cursor.fetchall()

        faqs = []
        for row in rows:
            faqs.append({
                "id": row["id"],
                "category": row["category"],
                "question": row["question"],
                "answer": row["answer"],
                "keywords": row["keywords"].split(",") if row["keywords"] else []
            })
        return faqs


def get_faq_by_id(faq_id: str) -> Optional[Dict]:
    """Получить FAQ по ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faq WHERE id = ?", (faq_id,))
        row = cursor.fetchone()

        if row:
            return {
                "id": row["id"],
                "category": row["category"],
                "question": row["question"],
                "answer": row["answer"],
                "keywords": row["keywords"].split(",") if row["keywords"] else []
            }
        return None


def get_faqs_by_category(category: str) -> List[Dict]:
    """Получить FAQ по категории"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faq WHERE category = ? ORDER BY id", (category,))
        rows = cursor.fetchall()

        faqs = []
        for row in rows:
            faqs.append({
                "id": row["id"],
                "category": row["category"],
                "question": row["question"],
                "answer": row["answer"],
                "keywords": row["keywords"].split(",") if row["keywords"] else []
            })
        return faqs


def add_faq(faq_id: str, category: str, question: str, answer: str, keywords: List[str]) -> bool:
    """Добавить новый FAQ"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            keywords_str = ",".join(keywords) if keywords else ""
            cursor.execute(
                "INSERT INTO faq (id, category, question, answer, keywords) VALUES (?, ?, ?, ?, ?)",
                (faq_id, category, question, answer, keywords_str)
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_faq(faq_id: str, category: str, question: str, answer: str, keywords: List[str]) -> bool:
    """Обновить существующий FAQ"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            keywords_str = ",".join(keywords) if keywords else ""
            cursor.execute(
                "UPDATE faq SET category = ?, question = ?, answer = ?, keywords = ? WHERE id = ?",
                (category, question, answer, keywords_str, faq_id)
            )
            return cursor.rowcount > 0
    except Exception:
        return False


def delete_faq(faq_id: str) -> bool:
    """Удалить FAQ"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM faq WHERE id = ?", (faq_id,))
            return cursor.rowcount > 0
    except Exception:
        return False


def add_category(name: str) -> bool:
    """Добавить новую категорию"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        return True
    except sqlite3.IntegrityError:
        return False


def get_all_categories() -> List[str]:
    """Получить список всех категорий"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        rows = cursor.fetchall()
        return [row["name"] for row in rows]


def migrate_from_demo_faq(demo_faq_data: List[Dict]):
    """Миграция данных из demo_faq.py"""
    count = 0
    for faq in demo_faq_data:
        if add_faq(
            faq["id"],
            faq["category"],
            faq["question"],
            faq["answer"],
            faq.get("keywords", [])
        ):
            count += 1
    print(f"OK: Мигрировано {count} записей из demo_faq")


# ========== НАСТРОЙКИ БОТА ==========

DEFAULT_BOT_SETTINGS = {
    "start_message": """👋 <b>Добро пожаловать в корпоративный бот-помощник!</b>

Я помогу найти ответы на вопросы о работе в компании.

💡 <b>Просто напишите свой вопрос</b>, например:
• "Можно ли в шортах на работу?"
• "Мне меньше денег пришло"
• "Где взять спецовку?"
• "Как отправить посылку?"

📚 Или выберите категорию:""",
    "feedback_button_yes": "👍 Полезно",
    "feedback_button_no": "👎 Не помогло",
    "feedback_response_yes": "✅ <b>Спасибо за отзыв!</b>",
    "feedback_response_no": "😔 Извините, что не помог.",

    # === НАСТРОЙКИ КАСКАДНОГО ПОИСКА ===
    "exact_match_threshold": "95",       # Порог для exact match (рекомендуется не менять)
    "keyword_match_threshold": "65",     # Порог для keyword search
    "semantic_match_threshold": "45",    # Порог для semantic search (старый SIMILARITY_THRESHOLD)
    "keyword_search_max_words": "5",     # Максимум слов в запросе для keyword search
    "show_similarity": "true",           # Показывать процент схожести в ответах
    "fallback_message": (
        "😔 Извините, я не нашел точного ответа на ваш вопрос.\n\n"
        "Попробуйте:\n"
        "• Переформулировать вопрос\n"
        "• Выбрать категорию из списка\n"
        "• Обратиться к ответственному сотруднику"
    ),

    # === ПРИВЕТСТВИЕ НОВЫХ ПОЛЬЗОВАТЕЛЕЙ BITRIX24 ===
    "new_user_welcome_enabled": "false",  # Включить автоматическое приветствие новых пользователей
    "new_user_welcome_message": """👋 [b]Добро пожаловать в компанию![/b]

Меня зовут FAQ-бот, и я помогу вам быстро найти ответы на часто задаваемые вопросы.

💡 Просто напишите мне свой вопрос, например:
• Как оформить отпуск?
• Где взять справку о зарплате?
• Как подключиться к корпоративной почте?

Я всегда на связи и готов помочь! 🤖""",

    # === RAG: СИСТЕМНЫЙ ПРОМПТ И ОТДЕЛЫ ===
    "rag_departments_info": """СПИСОК ОТДЕЛОВ И ИХ ОТВЕТСТВЕННОСТЬ (Используй для маршрутизации вопроса):

1. ИТ (IT): Не работает компьютер, интернет, Wi-Fi, почта, принтер (техническая поломка), установка программ (кроме 1С), проблемы с телефонией, доступами в Windows.
2. 1С: Ошибки именно в программе 1С, нет доступа к базе 1С, настройка отчетов в 1С, доработка функционала 1С.
3. Расчет заработной платы: Вопросы про ЛИЧНЫЕ деньги сотрудника: почему пришло мало, аванс, расчетный лист, удержания, премии, больничные выплаты.
4. Бухгалтерия: Вопросы про ДЕНЬГИ КОМПАНИИ: оплата счетов контрагентов, согласование платежей, доверенности на получение груза, акты сверок, корпоративные карты, командировочные расходы (авансовые отчеты).
5. Фин-служба: Бюджетирование, финансовый анализ, планы по выручке/прибыли, ОБЩАЯ СТАТИСТИКА ПРОДАЖ.

6. Кадры (КДП): Оформление документов: прием на работу, увольнение, график отпусков, трудовая книжка, справки с места работы, бумажное оформление больничного.
7. Подбор и развитие персонала(HR): Обучение, ДМС, тренинги, адаптация новичков, вакансии, собеседования, кадровый резерв.
8. Офис-менеджер: Пропуска (заказ, утеря), канцелярия, вода/кофе, заказ такси/курьера, бронирование переговорных, уборка в офисе.

9. Производство: Вопросы по производственному процессу, график смен на линии, работа оборудования, техника безопасности в цеху.
10. Планирование: План производства, график поставок сырья, загрузка линий.
11. R&D: Разработка новых продуктов, научные исследования, поиск новых ингредиентов/материалов.
12. Внедрения рецептур и технологий: Технологические карты, запуск новинки на линии, корректировка текущей рецептуры.
13. Отдел стандартизации: ГОСТы, ТУ (Технические условия), сертификация продукции, маркировка, этикетки (текст и нормы).
14. QA (Контроль качества): Жалобы на качество (претензии), брак, санитарные нормы, аудиты качества.
15. Анализ и тестирование продукта: Лабораторные анализы, дегустации (сенсорный анализ), проверка образцов.

16. Управления продуктовыми проектами: Сроки запуска продуктов, управление жизненным циклом продукта, координация проектных команд.
17. Закупки: Поиск поставщиков (сырье, упаковка, оборудование), тендеры, договора поставки.
18. Имиджевые коммуникации (PR): Корпоративные мероприятия, мерч, новости компании, соцсети, бренд, подарки партнерам.
19. Дизайн-студия: Разработка упаковки, макетов, баннеров, фотография продукции, логотипы.
20. Кулинарная студия: Проведение мастер-классов, создание фото/видео контента с едой, проработка блюд.

21. Юристы: Согласование договоров, правовая оценка, судебные претензии.
22. СОК(Строительно-организационный комитет): Вопросы о Спартакиаде и рац. предложениях.
23. Общие вопросы: Если вопрос не подходит ни под одну категорию выше.""",

    "rag_system_prompt": """Ты — умный корпоративный помощник. Твоя цель — помочь сотруднику, используя предоставленный контекст из базы знаний компании.

ВАЖНО: Контекст найден системой поиска и СВЯЗАН с вопросом пользователя, даже если формулировка отличается. Твоя задача — адаптировать информацию из контекста под конкретный вопрос.

{DEPARTMENTS_INFO}

СОВЕТЫ ПО ВЫБОРУ ОТДЕЛА:
1. Если вопрос про ЛИЧНУЮ зарплату — это всегда "Расчет заработной платы".
2. Если вопрос про программу 1С — это "1С", а не "ИТ".
3. Если вопрос про документы на отпуск — это "Кадры".
4. Если вопрос про обучение или тренинг — это "Подбор и развитие персонала".
5. Если вопрос про качество, смотри контекст: "Стандартизация", "QA" или "Анализ".
6. К проект-менеджерам можно отправлять только с вопросами по созданию и разработкам **новых продуктов(новинок)**.

ИНСТРУКЦИЯ ПО БЕЗОПАСНОСТИ:
В тексте есть скрытые данные (токены вида [PER_1], [PHONE_1]). Используй их как есть.

ИНСТРУКЦИЯ ПО ЛОГИКЕ (Приоритет действий):
1. **АНАЛИЗ КОНТЕКСТА:** Сначала прочти контекст.
2. **ПРОВЕРКА НА НЕОДНОЗНАЧНОСТЬ (ВАЖНО):**
   - Если вопрос состоит из 1-3 слов и является слишком общим (например: "Доставка", "Заказ", "Оплата", "Где купить"), и ты не можешь по контексту или списку отделов ТОЧНО понять намерение — **НЕ ГАДАЙ**.
   - Вместо ответа или маршрутизации, попроси пользователя уточнить вопрос. Приведи примеры, что он мог иметь в виду.
3. **ПРОВЕРКА МАСШТАБА:**
   - Если контекст описывает узкую ситуацию (новинки), а вопрос общий (все продажи) — игнорируй контекст.
4. **РОЛИ И ОТВЕТСТВЕННОСТЬ:** Если контекст точно совпадает с темой, используй его.
5. **МАРШРУТИЗАЦИЯ:** Если контекст не подошел, и вопрос понятен — используй "СПИСОК ОТДЕЛОВ".
6. **НЕИЗВЕСТНОСТЬ:** Если вопрос понятен, но ответа нет нигде — скажи, что информации нет.

ПРИМЕРЫ:

Пример 1 (Контекст подходит):
Вопрос: "Где сидят бухгалтеры?"
Контекст: "Печать у [PER_5] (Бухгалтерия, 3 этаж)."
Ответ: Исходя из данных о местонахождении печати, Бухгалтерия находится на 3 этаже.

Пример 2 (Маршрутизация):
Вопрос: "Почему мало денег в аванс?"
Контекст: Пусто.
Ответ: К сожалению, в базе знаний нет точной информации по вашему начислению. Рекомендую обратиться в отдел Расчет заработной платы.

Пример 3 (Масштаб не совпадает):
Вопрос: "Как запустить ракету?"
Контекст: "Микроволновка..."
Ответ: К сожалению, в базе знаний нет информации по вашему вопросу. Мои создатели увидят этот запрос.

Пример 4 (Слишком общий вопрос -> УТОЧНЕНИЕ):
Вопрос: "Заказ"
Контекст: (Может содержать разное про заказ канцелярии и заказ пропусков).
Рассуждение: Слово "Заказ" слишком многозначное. Это может быть заказ канцелярии (Офис-менеджер), заказ пропуска (Офис-менеджер) или заказ сырья (Закупки). Я не могу выбрать за пользователя.
Ответ: Уточните, пожалуйста, какой именно заказ вас интересует? (Например: заказ канцелярии, заказ пропуска или оформление заказа поставщику).

Пример 5 (Слишком общий вопрос -> УТОЧНЕНИЕ):
Вопрос: "Доставка"
Рассуждение: Непонятно, речь про доставку сотрудников, доставку еды или логистику грузов.
Ответ: Пожалуйста, уточните вопрос. Вас интересует доставка сотрудников, курьерская служба или поставка грузов?

ПРАВИЛА ОТВЕТА:
1. Отвечай кратко.
2. Если вопрос слишком общий (1-2 слова) — проси уточнить.
3. Если нашел точный ответ — отвечай.
4. Если ответа нет — отправляй в отдел.
5. Если совсем ничего не понятно — извинись и скажи, что не знаешь.""",
}


def init_bot_settings():
    """Инициализация настроек бота значениями по умолчанию"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for key, value in DEFAULT_BOT_SETTINGS.items():
                # Вставляем только если настройки еще нет
                cursor.execute(
                    "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
        print("OK: Настройки бота инициализированы")
        return True
    except Exception as e:
        print(f"Ошибка при инициализации настроек: {e}")
        return False


def get_bot_settings() -> Dict[str, str]:
    """Получить все настройки бота"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM bot_settings")
        rows = cursor.fetchall()

        # Если настроек нет, инициализируем и возвращаем дефолтные
        if not rows:
            init_bot_settings()
            return DEFAULT_BOT_SETTINGS.copy()

        settings = {}
        for row in rows:
            settings[row["key"]] = row["value"]

        # Добавляем недостающие настройки из дефолтных
        for key, value in DEFAULT_BOT_SETTINGS.items():
            if key not in settings:
                settings[key] = value

        return settings


def get_bot_setting(key: str) -> Optional[str]:
    """Получить конкретную настройку бота"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row:
            return row["value"]

        # Если настройка не найдена, возвращаем дефолтное значение
        return DEFAULT_BOT_SETTINGS.get(key)


def update_bot_setting(key: str, value: str) -> bool:
    """Обновить настройку бота"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            return True
    except Exception as e:
        print(f"Ошибка при обновлении настройки {key}: {e}")
        return False


def update_bot_settings(settings: Dict[str, str]) -> bool:
    """Обновить несколько настроек бота за раз"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            for key, value in settings.items():
                cursor.execute(
                    "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
            return True
    except Exception as e:
        print(f"Ошибка при обновлении настроек: {e}")
        return False


def reset_bot_settings() -> bool:
    """Сбросить все настройки бота к значениям по умолчанию"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM bot_settings")
            for key, value in DEFAULT_BOT_SETTINGS.items():
                cursor.execute(
                    "INSERT INTO bot_settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
        print("OK: Настройки бота сброшены к значениям по умолчанию")
        return True
    except Exception as e:
        print(f"Ошибка при сбросе настроек: {e}")
        return False


# ========== ЛОГИРОВАНИЕ ВЗАИМОДЕЙСТВИЙ ==========

def add_query_log(user_id: int, username: str, query_text: str, platform: str = 'telegram') -> Optional[int]:
    """
    Логировать запрос пользователя

    :param user_id: ID пользователя
    :param username: Имя пользователя
    :param query_text: Текст запроса
    :param platform: Платформа ('telegram' или 'bitrix24')
    :return: ID созданного лога или None при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO query_logs (user_id, username, query_text, platform) VALUES (?, ?, ?, ?)",
                (user_id, username, query_text, platform)
            )
            return cursor.lastrowid
    except Exception as e:
        print(f"Ошибка при логировании запроса: {e}")
        return None


def add_answer_log(query_log_id: int, faq_id: Optional[str], similarity_score: float, answer_shown: str, search_level: str = 'semantic') -> Optional[int]:
    """
    Логировать показанный ответ

    :param query_log_id: ID запроса из query_logs
    :param faq_id: ID FAQ (может быть None если ответ не найден)
    :param similarity_score: Оценка схожести (0-100)
    :param answer_shown: Текст показанного ответа
    :param search_level: Уровень поиска ('exact', 'keyword', 'semantic', 'none', 'direct')
    :return: ID созданного лога или None при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO answer_logs (query_log_id, faq_id, similarity_score, answer_shown, search_level) VALUES (?, ?, ?, ?, ?)",
                (query_log_id, faq_id, similarity_score, answer_shown, search_level)
            )
            return cursor.lastrowid
    except Exception as e:
        print(f"Ошибка при логировании ответа: {e}")
        return None


def add_rating_log(answer_log_id: int, user_id: int, rating: str) -> bool:
    """
    Логировать оценку ответа пользователем

    :param answer_log_id: ID ответа из answer_logs
    :param user_id: ID пользователя
    :param rating: Оценка ('helpful' или 'not_helpful')
    :return: True если успешно, False при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO rating_logs (answer_log_id, user_id, rating) VALUES (?, ?, ?)",
                (answer_log_id, user_id, rating)
            )
            return True
    except Exception as e:
        print(f"Ошибка при логировании оценки: {e}")
        return False


def add_llm_generation_log(
    answer_log_id: int,
    model: str,
    chunks_used: int,
    chunks_data: List[Dict],
    pii_detected: int,
    tokens_prompt: int,
    tokens_completion: int,
    tokens_total: int,
    finish_reason: str,
    generation_time_ms: int,
    error_message: Optional[str] = None
) -> Optional[int]:
    """
    Логирование метаданных RAG генерации

    :param answer_log_id: ID записи из answer_logs
    :param model: Модель LLM (e.g., "openai/gpt-4o-mini")
    :param chunks_used: Количество FAQ chunks отправленных в контекст
    :param chunks_data: Список FAQ chunks с их metadata [{"faq_id": "...", "question": "...", "confidence": 85.5}, ...]
    :param pii_detected: Количество PII сущностей
    :param tokens_prompt: Токены в промпте
    :param tokens_completion: Токены в ответе
    :param tokens_total: Всего токенов
    :param finish_reason: OpenAI finish reason
    :param generation_time_ms: Latency в миллисекундах
    :param error_message: Сообщение об ошибке (если есть)
    :return: ID llm_generation записи или None при ошибке
    """
    try:
        import json

        # Сериализуем chunks_data в JSON
        chunks_json = json.dumps(chunks_data, ensure_ascii=False)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO llm_generations (
                    answer_log_id, model, chunks_used, chunks_data,
                    pii_detected, tokens_prompt, tokens_completion, tokens_total,
                    finish_reason, generation_time_ms, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                answer_log_id, model, chunks_used, chunks_json,
                pii_detected, tokens_prompt, tokens_completion, tokens_total,
                finish_reason, generation_time_ms, error_message
            ))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Ошибка добавления LLM generation log: {e}", exc_info=True)
        return None


def get_logs(
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[int] = None,
    faq_id: Optional[str] = None,
    rating_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search_text: Optional[str] = None,
    no_answer: bool = False,
    platform: Optional[str] = None,
    show_archived: bool = False
) -> tuple[List[Dict], int]:
    """
    Получить логи с фильтрацией и пагинацией

    :param limit: Количество записей на странице
    :param offset: Смещение для пагинации
    :param user_id: Фильтр по ID пользователя
    :param faq_id: Фильтр по ID FAQ
    :param rating_filter: Фильтр по оценке ('helpful', 'not_helpful', 'no_rating')
    :param date_from: Начальная дата (ISO format)
    :param date_to: Конечная дата (ISO format)
    :param search_text: Поиск по тексту запроса
    :param no_answer: Показывать только запросы без ответа (faq_id IS NULL или совпадение < SIMILARITY_THRESHOLD)
    :param platform: Фильтр по платформе ('telegram' или 'bitrix24')
    :param show_archived: Показывать архивированные логи (по умолчанию False - только неархивированные)
    :return: (список логов, общее количество записей)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Базовый запрос с JOIN
            query = """
                SELECT
                    ql.id as query_id,
                    ql.user_id,
                    ql.username,
                    ql.query_text,
                    ql.platform,
                    ql.timestamp as query_timestamp,
                    al.id as answer_id,
                    al.faq_id,
                    al.similarity_score,
                    al.answer_shown,
                    al.search_level,
                    al.timestamp as answer_timestamp,
                    rl.rating,
                    rl.timestamp as rating_timestamp,
                    f.category,
                    f.question as faq_question,
                    lg.id as llm_gen_id,
                    lg.model as llm_model,
                    lg.chunks_used as llm_chunks_used,
                    lg.chunks_data as llm_chunks_data,
                    lg.pii_detected as llm_pii_detected,
                    lg.tokens_prompt as llm_tokens_prompt,
                    lg.tokens_completion as llm_tokens_completion,
                    lg.tokens_total as llm_tokens_total,
                    lg.finish_reason as llm_finish_reason,
                    lg.generation_time_ms as llm_generation_time_ms,
                    lg.error_message as llm_error_message
                FROM query_logs ql
                LEFT JOIN answer_logs al ON ql.id = al.query_log_id
                LEFT JOIN rating_logs rl ON al.id = rl.answer_log_id
                LEFT JOIN llm_generations lg ON al.id = lg.answer_log_id
                LEFT JOIN faq f ON al.faq_id = f.id
                WHERE 1=1
            """

            params = []

            # Фильтры
            if user_id is not None:
                query += " AND ql.user_id = ?"
                params.append(user_id)

            if faq_id is not None:
                query += " AND al.faq_id = ?"
                params.append(faq_id)

            if rating_filter:
                if rating_filter == 'no_rating':
                    query += " AND rl.rating IS NULL"
                else:
                    query += " AND rl.rating = ?"
                    params.append(rating_filter)

            if date_from:
                query += " AND ql.timestamp >= ?"
                params.append(date_from)

            if date_to:
                query += " AND ql.timestamp <= ?"
                params.append(date_to)

            if search_text:
                query += " AND ql.query_text LIKE ?"
                params.append(f"%{search_text}%")

            if no_answer:
                # Показываем только запросы где не нашелся ответ (faq_id IS NULL или совпадение < порога)
                # Исключаем disambiguation и clarification - это не ошибки, а уточнения
                query += f" AND (al.faq_id IS NULL OR al.similarity_score < {SIMILARITY_THRESHOLD}) AND al.search_level NOT IN ('disambiguation_shown', 'disambiguation', 'clarification', 'direct')"

            if platform:
                query += " AND ql.platform = ?"
                params.append(platform)

            # Фильтр архивированных логов (по умолчанию показываем только неархивированные)
            if not show_archived:
                query += " AND ql.period_id IS NULL"

            # Подсчет общего количества
            count_query = f"SELECT COUNT(*) as total FROM ({query})"
            cursor.execute(count_query, params)
            total = cursor.fetchone()["total"]

            # Сортировка и пагинация
            query += " ORDER BY ql.timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            logs = []
            for row in rows:
                import json

                # Формируем llm_metadata если есть данные
                llm_metadata = None
                if row["llm_gen_id"]:
                    llm_metadata = {
                        'id': row['llm_gen_id'],
                        'model': row['llm_model'],
                        'chunks_used': row['llm_chunks_used'],
                        'chunks_data': json.loads(row['llm_chunks_data']) if row['llm_chunks_data'] else None,
                        'pii_detected': row['llm_pii_detected'],
                        'tokens': {
                            'prompt': row['llm_tokens_prompt'],
                            'completion': row['llm_tokens_completion'],
                            'total': row['llm_tokens_total']
                        },
                        'finish_reason': row['llm_finish_reason'],
                        'generation_time_ms': row['llm_generation_time_ms'],
                        'error_message': row['llm_error_message']
                    }

                logs.append({
                    "query_id": row["query_id"],
                    "user_id": row["user_id"],
                    "username": row["username"],
                    "query_text": row["query_text"],
                    "platform": row["platform"],
                    "query_timestamp": convert_utc_to_utc7(row["query_timestamp"]),
                    "answer_id": row["answer_id"],
                    "faq_id": row["faq_id"],
                    "similarity_score": row["similarity_score"],
                    "answer_shown": row["answer_shown"],
                    "search_level": row["search_level"],
                    "answer_timestamp": convert_utc_to_utc7(row["answer_timestamp"]),
                    "rating": row["rating"],
                    "rating_timestamp": convert_utc_to_utc7(row["rating_timestamp"]),
                    "category": row["category"],
                    "faq_question": row["faq_question"],
                    "llm_metadata": llm_metadata
                })

            return logs, total
    except Exception as e:
        print(f"Ошибка при получении логов: {e}")
        return [], 0


def get_statistics() -> Dict:
    """
    Получить статистику по логам (только неархивированные)

    :return: Словарь со статистикой
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Всего запросов (только неархивированные)
            cursor.execute("SELECT COUNT(*) as total FROM query_logs WHERE period_id IS NULL")
            stats["total_queries"] = cursor.fetchone()["total"]

            # Всего ответов (только неархивированные)
            cursor.execute("SELECT COUNT(*) as total FROM answer_logs WHERE period_id IS NULL")
            stats["total_answers"] = cursor.fetchone()["total"]

            # Средняя оценка схожести (только неархивированные)
            cursor.execute("SELECT AVG(similarity_score) as avg_score FROM answer_logs WHERE period_id IS NULL AND similarity_score IS NOT NULL")
            result = cursor.fetchone()
            stats["avg_similarity"] = round(result["avg_score"], 2) if result["avg_score"] else 0

            # Оценки (только неархивированные)
            cursor.execute("SELECT COUNT(*) as total FROM rating_logs WHERE period_id IS NULL AND rating = 'helpful'")
            stats["helpful_count"] = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as total FROM rating_logs WHERE period_id IS NULL AND rating = 'not_helpful'")
            stats["not_helpful_count"] = cursor.fetchone()["total"]

            # Процент полезных ответов
            total_ratings = stats["helpful_count"] + stats["not_helpful_count"]
            if total_ratings > 0:
                stats["helpful_percentage"] = round((stats["helpful_count"] / total_ratings) * 100, 2)
            else:
                stats["helpful_percentage"] = 0

            # Запросы без ответа (faq_id IS NULL или совпадение < порога) - только неархивированные
            # Считаем уникальные запросы, а не записи в answer_logs
            # Исключаем disambiguation - это не ошибка, а уточнение
            cursor.execute(f"""
                SELECT COUNT(DISTINCT ql.id) as total
                FROM query_logs ql
                LEFT JOIN answer_logs al ON ql.id = al.query_log_id
                WHERE ql.period_id IS NULL
                  AND (al.faq_id IS NULL OR al.similarity_score < {SIMILARITY_THRESHOLD})
                  AND (al.search_level IS NULL OR al.search_level NOT IN ('disambiguation_shown', 'disambiguation', 'clarification', 'direct'))
            """)
            stats["no_answer_count"] = cursor.fetchone()["total"]

            # Топ-3 самых частых вопроса (только неархивированные)
            cursor.execute("""
                SELECT query_text, COUNT(*) as count
                FROM query_logs
                WHERE period_id IS NULL
                GROUP BY query_text
                ORDER BY count DESC
                LIMIT 3
            """)
            stats["top_queries"] = [
                {"query": row["query_text"], "count": row["count"]}
                for row in cursor.fetchall()
            ]

            # Топ-3 самых полезных FAQ (по количеству положительных оценок) - только неархивированные
            cursor.execute("""
                SELECT
                    f.id,
                    f.question,
                    f.category,
                    COUNT(*) as helpful_count
                FROM rating_logs rl
                JOIN answer_logs al ON rl.answer_log_id = al.id
                JOIN faq f ON al.faq_id = f.id
                WHERE rl.period_id IS NULL AND rl.rating = 'helpful'
                GROUP BY f.id
                ORDER BY helpful_count DESC
                LIMIT 3
            """)
            stats["top_helpful_faqs"] = [
                {
                    "faq_id": row["id"],
                    "question": row["question"],
                    "category": row["category"],
                    "helpful_count": row["helpful_count"]
                }
                for row in cursor.fetchall()
            ]

            # FAQ с низкими оценками (требуют улучшения) - только неархивированные
            cursor.execute("""
                SELECT
                    f.id,
                    f.question,
                    f.category,
                    COUNT(*) as not_helpful_count
                FROM rating_logs rl
                JOIN answer_logs al ON rl.answer_log_id = al.id
                JOIN faq f ON al.faq_id = f.id
                WHERE rl.period_id IS NULL AND rl.rating = 'not_helpful'
                GROUP BY f.id
                ORDER BY not_helpful_count DESC
                LIMIT 3
            """)
            stats["need_improvement_faqs"] = [
                {
                    "faq_id": row["id"],
                    "question": row["question"],
                    "category": row["category"],
                    "not_helpful_count": row["not_helpful_count"]
                }
                for row in cursor.fetchall()
            ]

            # RAG Statistics (только неархивированные)
            cursor.execute("""
                SELECT
                    COUNT(*) as rag_count,
                    AVG(lg.tokens_total) as avg_tokens,
                    SUM(lg.tokens_total) as total_tokens,
                    COUNT(CASE WHEN lg.error_message IS NOT NULL THEN 1 END) as rag_errors
                FROM answer_logs al
                LEFT JOIN llm_generations lg ON al.id = lg.answer_log_id
                WHERE al.period_id IS NULL
                  AND lg.id IS NOT NULL
            """)
            rag_stats = cursor.fetchone()

            stats['rag_answers'] = rag_stats['rag_count'] or 0
            stats['rag_avg_tokens'] = round(rag_stats['avg_tokens'] or 0, 1)
            stats['rag_total_tokens'] = rag_stats['total_tokens'] or 0
            stats['rag_errors'] = rag_stats['rag_errors'] or 0

            return stats
    except Exception as e:
        print(f"Ошибка при получении статистики: {e}")
        return {}


def get_search_level_statistics() -> Dict:
    """
    Получить статистику по уровням поиска (только неархивированные)

    :return: Словарь с количеством использований каждого уровня и средней уверенностью
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    search_level,
                    COUNT(*) as count,
                    AVG(similarity_score) as avg_confidence
                FROM answer_logs
                WHERE period_id IS NULL AND search_level IS NOT NULL
                GROUP BY search_level
                ORDER BY
                    CASE search_level
                        WHEN 'exact' THEN 1
                        WHEN 'keyword' THEN 2
                        WHEN 'semantic' THEN 3
                        WHEN 'disambiguation_shown' THEN 4
                        WHEN 'disambiguation' THEN 5
                        WHEN 'direct' THEN 6
                        WHEN 'none' THEN 7
                        ELSE 8
                    END
            """)

            stats = {}
            for row in cursor.fetchall():
                stats[row['search_level']] = {
                    'count': row['count'],
                    'avg_confidence': round(row['avg_confidence'], 2) if row['avg_confidence'] else 0
                }

            return stats

    except Exception as e:
        print(f"Ошибка при получении статистики по уровням поиска: {e}")
        return {}


# ============================================
# Функции для работы с правами Битрикс24
# ============================================

def check_bitrix24_permission(domain: str, user_id: str) -> Optional[Dict]:
    """
    Проверить права пользователя Битрикс24

    :param domain: Домен портала Битрикс24
    :param user_id: ID пользователя в Битрикс24
    :return: Dict с ролью пользователя {'role': 'admin'} или None если нет прав
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role FROM bitrix24_permissions WHERE domain = ? AND user_id = ?",
                (domain, user_id)
            )
            row = cursor.fetchone()

            if row:
                return {"role": row["role"]}
            return None

    except Exception as e:
        print(f"Ошибка при проверке прав Битрикс24: {e}")
        return None


def add_bitrix24_permission(
    domain: str,
    user_id: str,
    user_name: str,
    role: str,
    created_by: str
) -> bool:
    """
    Добавить или обновить права пользователя Битрикс24

    :param domain: Домен портала Битрикс24
    :param user_id: ID пользователя в Битрикс24
    :param user_name: ФИО пользователя
    :param role: Роль ('admin' или 'observer')
    :param created_by: ID пользователя, который выдал права
    :return: True если успешно, False при ошибке
    """
    if role not in ['admin', 'observer']:
        print(f"Ошибка: недопустимая роль '{role}'. Разрешены только 'admin' и 'observer'")
        return False

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, есть ли уже права у этого пользователя
            cursor.execute(
                "SELECT id FROM bitrix24_permissions WHERE domain = ? AND user_id = ?",
                (domain, user_id)
            )
            existing = cursor.fetchone()

            if existing:
                # Обновляем существующие права
                cursor.execute(
                    "UPDATE bitrix24_permissions SET role = ?, user_name = ? WHERE domain = ? AND user_id = ?",
                    (role, user_name, domain, user_id)
                )
                print(f"Обновлены права пользователя {user_name} ({user_id}) на портале {domain}: роль {role}")
            else:
                # Добавляем новые права
                cursor.execute(
                    """INSERT INTO bitrix24_permissions
                       (domain, user_id, user_name, role, created_by)
                       VALUES (?, ?, ?, ?, ?)""",
                    (domain, user_id, user_name, role, created_by)
                )
                print(f"Добавлены права пользователю {user_name} ({user_id}) на портале {domain}: роль {role}")

            return True

    except Exception as e:
        print(f"Ошибка при добавлении прав Битрикс24: {e}")
        return False


def get_bitrix24_permissions(domain: str) -> List[Dict]:
    """
    Получить список всех пользователей с правами для портала

    :param domain: Домен портала Битрикс24
    :return: Список пользователей с правами
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, user_id, user_name, role, created_at, created_by
                   FROM bitrix24_permissions
                   WHERE domain = ?
                   ORDER BY created_at DESC""",
                (domain,)
            )

            permissions = []
            for row in cursor.fetchall():
                permissions.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "role": row["role"],
                    "created_at": convert_utc_to_utc7(row["created_at"]),
                    "created_by": row["created_by"]
                })

            return permissions

    except Exception as e:
        print(f"Ошибка при получении списка прав Битрикс24: {e}")
        return []


def remove_bitrix24_permission(domain: str, user_id: str) -> bool:
    """
    Удалить права пользователя Битрикс24

    :param domain: Домен портала Битрикс24
    :param user_id: ID пользователя в Битрикс24
    :return: True если успешно, False при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM bitrix24_permissions WHERE domain = ? AND user_id = ?",
                (domain, user_id)
            )

            if cursor.rowcount > 0:
                print(f"Удалены права пользователя {user_id} на портале {domain}")
                return True
            else:
                print(f"Права пользователя {user_id} на портале {domain} не найдены")
                return False

    except Exception as e:
        print(f"Ошибка при удалении прав Битрикс24: {e}")
        return False


def get_all_bitrix24_domains() -> List[str]:
    """
    Получить список всех доменов Битрикс24, для которых есть права

    :return: Список доменов
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT domain FROM bitrix24_permissions ORDER BY domain")

            return [row["domain"] for row in cursor.fetchall()]

    except Exception as e:
        print(f"Ошибка при получении списка доменов Битрикс24: {e}")
        return []


# ============================================
# Функции для работы с тестовыми периодами
# ============================================

def create_test_period(name: str, description: str = "") -> Optional[int]:
    """
    Создать новый тестовый период

    :param name: Название периода (например, "Тестовая группа #1")
    :param description: Описание периода
    :return: ID созданного периода или None при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, нет ли активных периодов
            cursor.execute("SELECT id FROM test_periods WHERE status = 'active'")
            active_period = cursor.fetchone()

            if active_period:
                print(f"Ошибка: уже есть активный тестовый период (ID: {active_period['id']})")
                return None

            # Создаём новый период
            cursor.execute(
                "INSERT INTO test_periods (name, description, status) VALUES (?, ?, 'active')",
                (name, description)
            )
            period_id = cursor.lastrowid

            print(f"✅ Создан тестовый период '{name}' (ID: {period_id})")
            return period_id

    except Exception as e:
        print(f"Ошибка при создании тестового периода: {e}")
        return None


def end_test_period(period_id: int) -> bool:
    """
    Завершить тестовый период

    :param period_id: ID периода
    :return: True если успешно, False при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, существует ли период
            cursor.execute("SELECT status FROM test_periods WHERE id = ?", (period_id,))
            period = cursor.fetchone()

            if not period:
                print(f"Ошибка: тестовый период с ID {period_id} не найден")
                return False

            if period['status'] == 'completed':
                print(f"Ошибка: тестовый период {period_id} уже завершён")
                return False

            # Завершаем период
            cursor.execute(
                "UPDATE test_periods SET status = 'completed', end_date = CURRENT_TIMESTAMP WHERE id = ?",
                (period_id,)
            )

            print(f"✅ Тестовый период {period_id} завершён")
            return True

    except Exception as e:
        print(f"Ошибка при завершении тестового периода: {e}")
        return False


def get_test_periods() -> List[Dict]:
    """
    Получить список всех тестовых периодов

    :return: Список тестовых периодов
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    id,
                    name,
                    description,
                    start_date,
                    end_date,
                    status,
                    created_at
                FROM test_periods
                ORDER BY created_at DESC
            """)

            periods = []
            for row in cursor.fetchall():
                periods.append({
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "start_date": convert_utc_to_utc7(row["start_date"]),
                    "end_date": convert_utc_to_utc7(row["end_date"]) if row["end_date"] else None,
                    "status": row["status"],
                    "created_at": convert_utc_to_utc7(row["created_at"])
                })

            return periods

    except Exception as e:
        print(f"Ошибка при получении тестовых периодов: {e}")
        return []


def get_test_period(period_id: int) -> Optional[Dict]:
    """
    Получить информацию о тестовом периоде

    :param period_id: ID периода
    :return: Информация о периоде или None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    id,
                    name,
                    description,
                    start_date,
                    end_date,
                    status,
                    created_at
                FROM test_periods
                WHERE id = ?
            """, (period_id,))

            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "start_date": convert_utc_to_utc7(row["start_date"]),
                    "end_date": convert_utc_to_utc7(row["end_date"]) if row["end_date"] else None,
                    "status": row["status"],
                    "created_at": convert_utc_to_utc7(row["created_at"])
                }
            return None

    except Exception as e:
        print(f"Ошибка при получении тестового периода: {e}")
        return None


def get_active_test_period() -> Optional[Dict]:
    """
    Получить активный тестовый период

    :return: Информация об активном периоде или None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    id,
                    name,
                    description,
                    start_date,
                    status,
                    created_at
                FROM test_periods
                WHERE status = 'active'
            """)

            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "start_date": convert_utc_to_utc7(row["start_date"]),
                    "status": row["status"],
                    "created_at": convert_utc_to_utc7(row["created_at"])
                }
            return None

    except Exception as e:
        print(f"Ошибка при получении активного тестового периода: {e}")
        return None


def archive_current_logs(period_id: int) -> Dict[str, int]:
    """
    Архивировать текущие логи (привязать к тестовому периоду)

    :param period_id: ID тестового периода
    :return: Словарь с количеством заархивированных записей
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, существует ли период
            cursor.execute("SELECT id FROM test_periods WHERE id = ?", (period_id,))
            if not cursor.fetchone():
                print(f"Ошибка: тестовый период с ID {period_id} не найден")
                return {"queries": 0, "answers": 0, "ratings": 0}

            # Архивируем query_logs (только те, что без period_id)
            cursor.execute(
                "UPDATE query_logs SET period_id = ? WHERE period_id IS NULL",
                (period_id,)
            )
            queries_count = cursor.rowcount

            # Архивируем answer_logs (только те, что без period_id)
            cursor.execute(
                "UPDATE answer_logs SET period_id = ? WHERE period_id IS NULL",
                (period_id,)
            )
            answers_count = cursor.rowcount

            # Архивируем rating_logs (только те, что без period_id)
            cursor.execute(
                "UPDATE rating_logs SET period_id = ? WHERE period_id IS NULL",
                (period_id,)
            )
            ratings_count = cursor.rowcount

            print(f"✅ Заархивировано: {queries_count} запросов, {answers_count} ответов, {ratings_count} оценок")

            return {
                "queries": queries_count,
                "answers": answers_count,
                "ratings": ratings_count
            }

    except Exception as e:
        print(f"Ошибка при архивации логов: {e}")
        return {"queries": 0, "answers": 0, "ratings": 0}


def clear_unarchived_logs() -> Dict[str, int]:
    """
    Удалить неархивированные логи (логи без period_id)

    :return: Словарь с количеством удалённых записей
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Удаляем rating_logs без period_id
            cursor.execute("DELETE FROM rating_logs WHERE period_id IS NULL")
            ratings_count = cursor.rowcount

            # Удаляем answer_logs без period_id
            cursor.execute("DELETE FROM answer_logs WHERE period_id IS NULL")
            answers_count = cursor.rowcount

            # Удаляем query_logs без period_id
            cursor.execute("DELETE FROM query_logs WHERE period_id IS NULL")
            queries_count = cursor.rowcount

            print(f"✅ Удалено: {queries_count} запросов, {answers_count} ответов, {ratings_count} оценок")

            return {
                "queries": queries_count,
                "answers": answers_count,
                "ratings": ratings_count
            }

    except Exception as e:
        print(f"Ошибка при очистке логов: {e}")
        return {"queries": 0, "answers": 0, "ratings": 0}


def get_period_statistics(period_id: int) -> Dict:
    """
    Получить подробную статистику по тестовому периоду

    :param period_id: ID тестового периода
    :return: Словарь со статистикой
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Информация о периоде
            period = get_test_period(period_id)
            if not period:
                return {}
            stats["period"] = period

            # Всего запросов в периоде
            cursor.execute(
                "SELECT COUNT(*) as total FROM query_logs WHERE period_id = ?",
                (period_id,)
            )
            stats["total_queries"] = cursor.fetchone()["total"]

            # Всего ответов
            cursor.execute(
                "SELECT COUNT(*) as total FROM answer_logs WHERE period_id = ?",
                (period_id,)
            )
            stats["total_answers"] = cursor.fetchone()["total"]

            # Распределение по уровням поиска
            cursor.execute("""
                SELECT
                    search_level,
                    COUNT(*) as count,
                    AVG(similarity_score) as avg_confidence
                FROM answer_logs
                WHERE period_id = ? AND search_level IS NOT NULL
                GROUP BY search_level
            """, (period_id,))

            search_levels = {}
            for row in cursor.fetchall():
                search_levels[row['search_level']] = {
                    'count': row['count'],
                    'avg_confidence': round(row['avg_confidence'], 2) if row['avg_confidence'] else 0
                }
            stats["search_levels"] = search_levels

            # Средняя схожесть
            cursor.execute(
                "SELECT AVG(similarity_score) as avg_score FROM answer_logs WHERE period_id = ? AND similarity_score IS NOT NULL",
                (period_id,)
            )
            result = cursor.fetchone()
            stats["avg_similarity"] = round(result["avg_score"], 2) if result["avg_score"] else 0

            # Оценки
            cursor.execute(
                "SELECT COUNT(*) as total FROM rating_logs WHERE period_id = ? AND rating = 'helpful'",
                (period_id,)
            )
            stats["helpful_count"] = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) as total FROM rating_logs WHERE period_id = ? AND rating = 'not_helpful'",
                (period_id,)
            )
            stats["not_helpful_count"] = cursor.fetchone()["total"]

            # Процент полезных ответов
            total_ratings = stats["helpful_count"] + stats["not_helpful_count"]
            if total_ratings > 0:
                stats["helpful_percentage"] = round((stats["helpful_count"] / total_ratings) * 100, 2)
            else:
                stats["helpful_percentage"] = 0

            # Запросы без ответа
            cursor.execute(f"""
                SELECT COUNT(DISTINCT ql.id) as total
                FROM query_logs ql
                LEFT JOIN answer_logs al ON ql.id = al.query_log_id
                WHERE ql.period_id = ?
                  AND (al.faq_id IS NULL OR al.similarity_score < {SIMILARITY_THRESHOLD})
                  AND (al.search_level IS NULL OR al.search_level NOT IN ('disambiguation_shown', 'disambiguation', 'clarification', 'direct'))
            """, (period_id,))
            stats["no_answer_count"] = cursor.fetchone()["total"]

            # Топ-10 популярных запросов
            cursor.execute("""
                SELECT query_text, COUNT(*) as count
                FROM query_logs
                WHERE period_id = ?
                GROUP BY query_text
                ORDER BY count DESC
                LIMIT 10
            """, (period_id,))
            stats["top_queries"] = [
                {"query": row["query_text"], "count": row["count"]}
                for row in cursor.fetchall()
            ]

            # Топ-10 FAQ с лучшими рейтингами
            cursor.execute("""
                SELECT
                    f.id,
                    f.question,
                    f.category,
                    COUNT(*) as helpful_count
                FROM rating_logs rl
                JOIN answer_logs al ON rl.answer_log_id = al.id
                JOIN faq f ON al.faq_id = f.id
                WHERE rl.period_id = ? AND rl.rating = 'helpful'
                GROUP BY f.id
                ORDER BY helpful_count DESC
                LIMIT 10
            """, (period_id,))
            stats["top_helpful_faqs"] = [
                {
                    "faq_id": row["id"],
                    "question": row["question"],
                    "category": row["category"],
                    "helpful_count": row["helpful_count"]
                }
                for row in cursor.fetchall()
            ]

            # FAQ с низкими оценками
            cursor.execute("""
                SELECT
                    f.id,
                    f.question,
                    f.category,
                    COUNT(*) as not_helpful_count
                FROM rating_logs rl
                JOIN answer_logs al ON rl.answer_log_id = al.id
                JOIN faq f ON al.faq_id = f.id
                WHERE rl.period_id = ? AND rl.rating = 'not_helpful'
                GROUP BY f.id
                ORDER BY not_helpful_count DESC
                LIMIT 10
            """, (period_id,))
            stats["need_improvement_faqs"] = [
                {
                    "faq_id": row["id"],
                    "question": row["question"],
                    "category": row["category"],
                    "not_helpful_count": row["not_helpful_count"]
                }
                for row in cursor.fetchall()
            ]

            # Распределение по платформам
            cursor.execute("""
                SELECT platform, COUNT(*) as count
                FROM query_logs
                WHERE period_id = ?
                GROUP BY platform
            """, (period_id,))
            stats["platforms"] = {
                row["platform"]: row["count"]
                for row in cursor.fetchall()
            }

            # Динамика по дням
            cursor.execute("""
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as queries_count
                FROM query_logs
                WHERE period_id = ?
                GROUP BY DATE(timestamp)
                ORDER BY date
            """, (period_id,))
            stats["daily_dynamics"] = [
                {"date": row["date"], "count": row["queries_count"]}
                for row in cursor.fetchall()
            ]

            # Уникальные пользователи
            cursor.execute(
                "SELECT COUNT(DISTINCT user_id) as total FROM query_logs WHERE period_id = ?",
                (period_id,)
            )
            stats["unique_users"] = cursor.fetchone()["total"]

            # Неудачные запросы (для Excel отчета)
            stats["failed_queries"] = get_failed_queries_for_period(period_id, limit=200)

            return stats

    except Exception as e:
        print(f"Ошибка при получении статистики периода: {e}")
        return {}


def get_failed_queries_for_period(period_id: int, limit: int = 100) -> List[Dict]:
    """
    Получить неудачные запросы для тестового периода (для работы над ошибками)

    :param period_id: ID тестового периода
    :param limit: Максимальное количество записей
    :return: Список неудачных запросов
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"""
                SELECT
                    ql.query_text,
                    ql.username,
                    ql.platform,
                    ql.timestamp,
                    al.similarity_score,
                    al.search_level,
                    al.faq_id,
                    f.question as faq_question,
                    rl.rating
                FROM query_logs ql
                LEFT JOIN answer_logs al ON ql.id = al.query_log_id
                LEFT JOIN faq f ON al.faq_id = f.id
                LEFT JOIN rating_logs rl ON al.id = rl.answer_log_id
                WHERE ql.period_id = ?
                  AND (al.faq_id IS NULL OR al.similarity_score < {SIMILARITY_THRESHOLD} OR rl.rating = 'not_helpful')
                  AND (al.search_level IS NULL OR al.search_level NOT IN ('disambiguation_shown', 'disambiguation', 'clarification', 'direct'))
                ORDER BY ql.timestamp DESC
                LIMIT ?
            """, (period_id, limit))

            failed_queries = []
            for row in cursor.fetchall():
                failed_queries.append({
                    "query_text": row["query_text"],
                    "username": row["username"],
                    "platform": row["platform"],
                    "timestamp": convert_utc_to_utc7(row["timestamp"]),
                    "similarity_score": row["similarity_score"],
                    "search_level": row["search_level"],
                    "faq_id": row["faq_id"],
                    "faq_question": row["faq_question"],
                    "rating": row["rating"]
                })

            return failed_queries

    except Exception as e:
        print(f"Ошибка при получении неудачных запросов: {e}")
        return []


# ============================================
# Функции для работы с рассылками
# ============================================

def create_broadcast(title: str, message: str, created_by: str = None) -> Optional[int]:
    """
    Создать новую рассылку (черновик)

    :param title: Заголовок рассылки
    :param message: Текст сообщения (BB-code)
    :param created_by: Кто создал рассылку
    :return: ID созданной рассылки или None при ошибке
    """
    try:
        print(f"📢 create_broadcast вызван: title='{title}', msg_len={len(message)}, created_by={created_by}")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO broadcasts (title, message, created_by, status)
                   VALUES (?, ?, ?, 'draft')""",
                (title, message, created_by)
            )
            broadcast_id = cursor.lastrowid
            print(f"✅ Создана рассылка '{title}' (ID: {broadcast_id})")
            return broadcast_id

    except Exception as e:
        import traceback
        print(f"❌ Ошибка при создании рассылки: {e}")
        traceback.print_exc()
        return None


def get_broadcasts(limit: int = 50, offset: int = 0) -> List[Dict]:
    """
    Получить список рассылок

    :param limit: Количество записей
    :param offset: Смещение
    :return: Список рассылок
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, message, created_by, created_at, started_at,
                       finished_at, status, total_recipients, sent_count, failed_count
                FROM broadcasts
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            broadcasts = []
            for row in cursor.fetchall():
                broadcasts.append({
                    "id": row["id"],
                    "title": row["title"],
                    "message": row["message"],
                    "created_by": row["created_by"],
                    "created_at": convert_utc_to_utc7(row["created_at"]),
                    "started_at": convert_utc_to_utc7(row["started_at"]) if row["started_at"] else None,
                    "finished_at": convert_utc_to_utc7(row["finished_at"]) if row["finished_at"] else None,
                    "status": row["status"],
                    "total_recipients": row["total_recipients"],
                    "sent_count": row["sent_count"],
                    "failed_count": row["failed_count"]
                })

            return broadcasts

    except Exception as e:
        print(f"Ошибка при получении списка рассылок: {e}")
        return []


def get_broadcast(broadcast_id: int) -> Optional[Dict]:
    """
    Получить информацию о рассылке

    :param broadcast_id: ID рассылки
    :return: Информация о рассылке или None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, message, created_by, created_at, started_at,
                       finished_at, status, total_recipients, sent_count, failed_count
                FROM broadcasts
                WHERE id = ?
            """, (broadcast_id,))

            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "title": row["title"],
                    "message": row["message"],
                    "created_by": row["created_by"],
                    "created_at": convert_utc_to_utc7(row["created_at"]),
                    "started_at": convert_utc_to_utc7(row["started_at"]) if row["started_at"] else None,
                    "finished_at": convert_utc_to_utc7(row["finished_at"]) if row["finished_at"] else None,
                    "status": row["status"],
                    "total_recipients": row["total_recipients"],
                    "sent_count": row["sent_count"],
                    "failed_count": row["failed_count"]
                }
            return None

    except Exception as e:
        print(f"Ошибка при получении рассылки: {e}")
        return None


def update_broadcast_status(broadcast_id: int, status: str, **kwargs) -> bool:
    """
    Обновить статус рассылки

    :param broadcast_id: ID рассылки
    :param status: Новый статус (draft, sending, cancelled, sent, failed)
    :param kwargs: Дополнительные поля для обновления (total_recipients, sent_count, failed_count)
    :return: True если успешно, False при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Формируем запрос
            updates = ["status = ?"]
            params = [status]

            if status == 'sending' and 'total_recipients' in kwargs:
                updates.append("started_at = CURRENT_TIMESTAMP")
                updates.append("total_recipients = ?")
                params.append(kwargs['total_recipients'])

            if status in ('sent', 'cancelled', 'failed'):
                updates.append("finished_at = CURRENT_TIMESTAMP")

            if 'sent_count' in kwargs:
                updates.append("sent_count = ?")
                params.append(kwargs['sent_count'])

            if 'failed_count' in kwargs:
                updates.append("failed_count = ?")
                params.append(kwargs['failed_count'])

            params.append(broadcast_id)

            query = f"UPDATE broadcasts SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)

            return cursor.rowcount > 0

    except Exception as e:
        print(f"Ошибка при обновлении статуса рассылки: {e}")
        return False


def update_broadcast_progress(broadcast_id: int, sent_count: int, failed_count: int) -> bool:
    """
    Обновить прогресс рассылки

    :param broadcast_id: ID рассылки
    :param sent_count: Количество отправленных
    :param failed_count: Количество ошибок
    :return: True если успешно, False при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE broadcasts SET sent_count = ?, failed_count = ? WHERE id = ?",
                (sent_count, failed_count, broadcast_id)
            )
            return cursor.rowcount > 0

    except Exception as e:
        print(f"Ошибка при обновлении прогресса рассылки: {e}")
        return False


def add_broadcast_log(
    broadcast_id: int,
    user_id: int,
    user_name: str,
    status: str,
    error_message: str = None
) -> Optional[int]:
    """
    Добавить лог отправки

    :param broadcast_id: ID рассылки
    :param user_id: ID пользователя Bitrix24
    :param user_name: Имя пользователя
    :param status: Статус отправки (pending, sent, failed)
    :param error_message: Сообщение об ошибке (если есть)
    :return: ID лога или None при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            sent_at = "CURRENT_TIMESTAMP" if status == 'sent' else None

            if sent_at:
                cursor.execute(
                    """INSERT INTO broadcast_logs
                       (broadcast_id, user_id, user_name, status, error_message, sent_at)
                       VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (broadcast_id, user_id, user_name, status, error_message)
                )
            else:
                cursor.execute(
                    """INSERT INTO broadcast_logs
                       (broadcast_id, user_id, user_name, status, error_message)
                       VALUES (?, ?, ?, ?, ?)""",
                    (broadcast_id, user_id, user_name, status, error_message)
                )

            return cursor.lastrowid

    except Exception as e:
        print(f"Ошибка при добавлении лога рассылки: {e}")
        return None


def get_broadcast_logs(broadcast_id: int, limit: int = 500) -> List[Dict]:
    """
    Получить логи рассылки

    :param broadcast_id: ID рассылки
    :param limit: Максимальное количество записей
    :return: Список логов
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, user_name, status, error_message, sent_at
                FROM broadcast_logs
                WHERE broadcast_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (broadcast_id, limit))

            logs = []
            for row in cursor.fetchall():
                logs.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "status": row["status"],
                    "error_message": row["error_message"],
                    "sent_at": convert_utc_to_utc7(row["sent_at"]) if row["sent_at"] else None
                })

            return logs

    except Exception as e:
        print(f"Ошибка при получении логов рассылки: {e}")
        return []


def delete_broadcast(broadcast_id: int) -> bool:
    """
    Удалить рассылку (только draft или cancelled)

    :param broadcast_id: ID рассылки
    :return: True если успешно, False при ошибке
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Проверяем статус рассылки
            cursor.execute("SELECT status FROM broadcasts WHERE id = ?", (broadcast_id,))
            row = cursor.fetchone()

            if not row:
                print(f"Рассылка {broadcast_id} не найдена")
                return False

            if row['status'] not in ('draft', 'cancelled'):
                print(f"Нельзя удалить рассылку со статусом '{row['status']}'")
                return False

            # Удаляем логи
            cursor.execute("DELETE FROM broadcast_logs WHERE broadcast_id = ?", (broadcast_id,))

            # Удаляем рассылку
            cursor.execute("DELETE FROM broadcasts WHERE id = ?", (broadcast_id,))

            print(f"✅ Рассылка {broadcast_id} удалена")
            return True

    except Exception as e:
        print(f"Ошибка при удалении рассылки: {e}")
        return False
