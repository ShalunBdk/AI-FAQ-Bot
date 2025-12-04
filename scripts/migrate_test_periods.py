# migrate_test_periods.py
# -*- coding: utf-8 -*-
"""
Миграция: добавление системы тестовых периодов и архивации логов
"""

import sqlite3
import sys
import os

# Добавляем путь к модулям проекта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import DB_FILE, get_db_connection


def migrate():
    """Выполнить миграцию"""
    print("Начинаем миграцию: добавление системы тестовых периодов...")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Создаём таблицу тестовых периодов
        print("Создание таблицы test_periods...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_periods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT NOT NULL CHECK(status IN ('active', 'completed')) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Добавляем поле period_id к существующим таблицам логов
        print("Добавление поля period_id к таблице query_logs...")
        try:
            cursor.execute("ALTER TABLE query_logs ADD COLUMN period_id INTEGER REFERENCES test_periods(id)")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  Поле period_id уже существует в query_logs")
            else:
                raise

        print("Добавление поля period_id к таблице answer_logs...")
        try:
            cursor.execute("ALTER TABLE answer_logs ADD COLUMN period_id INTEGER REFERENCES test_periods(id)")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  Поле period_id уже существует в answer_logs")
            else:
                raise

        print("Добавление поля period_id к таблице rating_logs...")
        try:
            cursor.execute("ALTER TABLE rating_logs ADD COLUMN period_id INTEGER REFERENCES test_periods(id)")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  Поле period_id уже существует в rating_logs")
            else:
                raise

        # Создаём индексы для оптимизации
        print("Создание индексов...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_period ON query_logs(period_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_answer_logs_period ON answer_logs(period_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_logs_period ON rating_logs(period_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_periods_status ON test_periods(status)")

        print("OK: Миграция успешно завершена!")


if __name__ == "__main__":
    migrate()
