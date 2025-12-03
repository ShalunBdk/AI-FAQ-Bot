#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция: добавление поля search_level в answer_logs

Добавляет новое поле для отслеживания уровня поиска:
- 'exact' - точное совпадение
- 'keyword' - поиск по ключевым словам
- 'semantic' - семантический поиск
- 'none' - не найдено
- 'direct' - прямой просмотр FAQ
"""

import sqlite3
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_FILE = "data/faq_database.db"


def migrate():
    """Добавить поле search_level в answer_logs"""
    print("=" * 60)
    print("Начало миграции: добавление поля search_level в answer_logs")
    print("=" * 60)

    if not os.path.exists(DB_FILE):
        print(f"[ERROR] Файл базы данных не найден: {DB_FILE}")
        print("   Убедитесь, что вы запускаете скрипт из корневой директории проекта")
        return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Проверяем, существует ли таблица answer_logs
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='answer_logs'")
        if not cursor.fetchone():
            print("[ERROR] Таблица answer_logs не существует!")
            print("   Запустите сначала основные миграции: python scripts/migrate_data.py")
            return False

        # Проверяем, существует ли уже поле
        cursor.execute("PRAGMA table_info(answer_logs)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'search_level' in columns:
            print("[WARNING] Поле search_level уже существует в answer_logs")
            print("   Миграция уже была применена ранее")

            # Показываем статистику
            cursor.execute("SELECT COUNT(*) FROM answer_logs WHERE search_level IS NOT NULL")
            count = cursor.fetchone()[0]
            print(f"   Записей с заполненным search_level: {count}")

            return True

        print("Добавление поля search_level в таблицу answer_logs...")

        # Добавляем поле
        cursor.execute("""
            ALTER TABLE answer_logs
            ADD COLUMN search_level TEXT DEFAULT 'semantic'
        """)

        conn.commit()
        print("[OK] Поле search_level успешно добавлено")
        print("   Значение по умолчанию: 'semantic' (для обратной совместимости)")

        # Обновляем старые записи где faq_id IS NULL
        print("\nОбновление старых записей...")
        cursor.execute("""
            UPDATE answer_logs
            SET search_level = 'none'
            WHERE faq_id IS NULL
        """)

        conn.commit()
        updated = cursor.rowcount
        print(f"[OK] Обновлено {updated} записей с faq_id IS NULL -> search_level = 'none'")

        # Статистика
        print("\nСтатистика после миграции:")
        cursor.execute("SELECT COUNT(*) FROM answer_logs")
        total = cursor.fetchone()[0]
        print(f"   Всего записей в answer_logs: {total}")

        cursor.execute("SELECT search_level, COUNT(*) FROM answer_logs GROUP BY search_level")
        for row in cursor.fetchall():
            level = row[0] if row[0] else "NULL"
            count = row[1]
            print(f"   - {level}: {count}")

        print("\n" + "=" * 60)
        print("[OK] Миграция завершена успешно!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n[ERROR] Ошибка миграции: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
