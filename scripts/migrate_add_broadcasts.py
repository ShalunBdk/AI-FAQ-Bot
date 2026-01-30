#!/usr/bin/env python3
"""
Миграция: Добавление таблиц для рассылки сообщений

Добавляет таблицы:
- broadcasts - история рассылок
- broadcast_logs - детальные логи отправки каждому пользователю

Запуск: python scripts/migrate_add_broadcasts.py
"""

import sqlite3
import os
import sys

# Добавляем путь к корню проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import DB_FILE


def migrate():
    """Выполнить миграцию"""
    print("=" * 50)
    print("Миграция: Добавление таблиц для рассылок")
    print("=" * 50)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Проверяем, существуют ли таблицы
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='broadcasts'"
        )
        if cursor.fetchone():
            print("⚠️  Таблица broadcasts уже существует")
        else:
            # Создаём таблицу broadcasts
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
            print("✅ Таблица broadcasts создана")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='broadcast_logs'"
        )
        if cursor.fetchone():
            print("⚠️  Таблица broadcast_logs уже существует")
        else:
            # Создаём таблицу broadcast_logs
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
            print("✅ Таблица broadcast_logs создана")

        # Создаём индексы
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_broadcasts_status ON broadcasts(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_broadcast_logs_broadcast ON broadcast_logs(broadcast_id)"
        )
        print("✅ Индексы созданы")

        conn.commit()
        print("\n✅ Миграция успешно завершена!")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Ошибка миграции: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
