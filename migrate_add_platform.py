# migrate_add_platform.py
# -*- coding: utf-8 -*-
"""
Скрипт миграции для добавления поддержки платформы (telegram/bitrix24)
"""

import sqlite3
from database import DB_FILE


def migrate():
    """Добавление колонки platform в query_logs"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Проверяем существование колонки platform
        cursor.execute("PRAGMA table_info(query_logs)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'platform' in columns:
            print("ВНИМАНИЕ: Колонка 'platform' уже существует в таблице query_logs. Миграция не требуется.")
            conn.close()
            return

        print("Добавление колонки 'platform' в таблицу query_logs...")

        # Добавляем колонку platform
        cursor.execute("""
            ALTER TABLE query_logs
            ADD COLUMN platform TEXT DEFAULT 'telegram'
        """)
        print("OK: Добавлена колонка 'platform' с дефолтным значением 'telegram'")

        # Создаем индекс для быстрой фильтрации по платформе
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_platform ON query_logs(platform)")
        print("OK: Создан индекс для платформы")

        conn.commit()
        print("\nOK: Миграция успешно завершена! Теперь можно логировать запросы с разных платформ.")

    except sqlite3.Error as e:
        print(f"ОШИБКА при миграции: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Миграция: Добавление поддержки платформы")
    print("=" * 60)
    migrate()
    print("\nГотово! Теперь можно использовать platform='bitrix24' в add_query_log().")
