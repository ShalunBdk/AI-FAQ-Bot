# -*- coding: utf-8 -*-
"""
Создание недостающих таблиц логирования
"""

import sqlite3
from database import DB_FILE

def create_missing_tables():
    """Создать недостающие таблицы"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        print("Создание недостающих таблиц логирования...")

        # Таблица логов ответов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer_logs (
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
        print("OK: Таблица answer_logs")

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
        print("OK: Таблица rating_logs")

        # Индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_timestamp ON query_logs(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_user ON query_logs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_answer_logs_faq ON answer_logs(faq_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_logs_rating ON rating_logs(rating)")
        print("OK: Индексы")

        conn.commit()
        print("\nГотово! Все таблицы логирования созданы.")

    except sqlite3.Error as e:
        print(f"Ошибка: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    create_missing_tables()
