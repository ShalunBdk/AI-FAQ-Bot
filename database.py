# database.py
# -*- coding: utf-8 -*-
"""
Модуль для работы с базой данных FAQ
"""

import sqlite3
from typing import List, Dict, Optional
from contextlib import contextmanager

DB_FILE = "faq_database.db"


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД"""
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
    "feedback_response_no": "😔 Извините, что не помог."
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
