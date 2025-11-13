# migrate_add_logging.py
# -*- coding: utf-8 -*-
"""
Скрипт миграции для добавления таблиц логирования
"""

import sys
import os
import sqlite3

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import DB_FILE


def migrate():
    """Создание таблиц для логирования"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Проверка существования таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='query_logs'")
        if cursor.fetchone():
            print("ВНИМАНИЕ: Таблицы логирования уже существуют. Миграция не требуется.")
            conn.close()
            return

        print("Создание таблиц для логирования...")

        # Таблица логов запросов пользователей
        cursor.execute("""
            CREATE TABLE query_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                query_text TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("OK: Создана таблица query_logs")

        # Таблица логов ответов
        cursor.execute("""
            CREATE TABLE answer_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_log_id INTEGER,
                faq_id TEXT,
                similarity_score REAL,
                answer_shown TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (query_log_id) REFERENCES query_logs(id),
                FOREIGN KEY (faq_id) REFERENCES faq(id)
            )
        """)
        print("OK: Создана таблица answer_logs")

        # Таблица оценок ответов
        cursor.execute("""
            CREATE TABLE rating_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer_log_id INTEGER,
                user_id INTEGER NOT NULL,
                rating TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (answer_log_id) REFERENCES answer_logs(id)
            )
        """)
        print("OK: Создана таблица rating_logs")

        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX idx_query_logs_timestamp ON query_logs(timestamp DESC)")
        cursor.execute("CREATE INDEX idx_query_logs_user ON query_logs(user_id)")
        cursor.execute("CREATE INDEX idx_answer_logs_faq ON answer_logs(faq_id)")
        cursor.execute("CREATE INDEX idx_rating_logs_rating ON rating_logs(rating)")
        print("OK: Созданы индексы для оптимизации")

        conn.commit()
        print("\nOK: Миграция успешно завершена! Таблицы логирования созданы.")

    except sqlite3.Error as e:
        print(f"ОШИБКА при миграции: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Миграция: Добавление таблиц логирования")
    print("=" * 60)
    migrate()
    print("\nГотово! Теперь можно запускать бот с логированием.")
