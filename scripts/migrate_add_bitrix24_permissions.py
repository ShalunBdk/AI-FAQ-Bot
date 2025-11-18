# migrate_add_bitrix24_permissions.py
# -*- coding: utf-8 -*-
"""
Скрипт миграции для добавления таблицы прав доступа Битрикс24
"""

import sys
import os
import sqlite3

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import DB_FILE


def migrate():
    """Создание таблицы bitrix24_permissions"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Проверка существования таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bitrix24_permissions'")
        if cursor.fetchone():
            print("ВНИМАНИЕ: Таблица bitrix24_permissions уже существует. Миграция не требуется.")
            conn.close()
            return

        print("Создание таблицы bitrix24_permissions...")

        # Таблица прав доступа для пользователей Битрикс24
        cursor.execute("""
            CREATE TABLE bitrix24_permissions (
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
        print("OK: Создана таблица bitrix24_permissions")

        # Индексы для быстрого поиска
        cursor.execute("CREATE INDEX idx_bitrix24_permissions_domain ON bitrix24_permissions(domain)")
        cursor.execute("CREATE INDEX idx_bitrix24_permissions_domain_user ON bitrix24_permissions(domain, user_id)")
        cursor.execute("CREATE INDEX idx_bitrix24_permissions_role ON bitrix24_permissions(role)")
        print("OK: Созданы индексы для оптимизации")

        conn.commit()
        print("\nOK: Миграция успешно завершена! Таблица прав доступа Битрикс24 создана.")
        print("\nСтруктура таблицы:")
        print("  - id: PRIMARY KEY")
        print("  - domain: домен портала Битрикс24")
        print("  - user_id: ID пользователя в Битрикс24")
        print("  - user_name: ФИО пользователя")
        print("  - role: роль (admin или observer)")
        print("  - created_at: дата добавления прав")
        print("  - created_by: кто выдал права")

    except sqlite3.Error as e:
        print(f"ОШИБКА при миграции: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Миграция: Добавление таблицы bitrix24_permissions")
    print("=" * 60)
    migrate()
    print("\nГотово! Теперь можно использовать систему прав доступа Битрикс24.")
