# migrate_data.py
# -*- coding: utf-8 -*-
"""
Скрипт для миграции данных из demo_faq.py в базу данных
"""

import sys
import os

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import init_database, migrate_from_demo_faq, get_all_faqs
from scripts.demo_faq import DEMO_FAQ


def main():
    print("==> Начинаем миграцию данных...")

    # Инициализируем БД
    init_database()

    # Проверяем, есть ли уже данные
    existing_faqs = get_all_faqs()
    if existing_faqs:
        print(f"ВНИМАНИЕ: В базе уже есть {len(existing_faqs)} записей")
        answer = input("Хотите продолжить миграцию? Существующие записи с такими же ID будут пропущены (y/n): ")
        if answer.lower() != 'y':
            print("Миграция отменена")
            return

    # Мигрируем данные
    migrate_from_demo_faq(DEMO_FAQ)

    # Проверяем результат
    all_faqs = get_all_faqs()
    print(f"\nМиграция завершена! Всего записей в БД: {len(all_faqs)}")

    # Выводим статистику по категориям
    from collections import Counter
    categories = Counter([faq["category"] for faq in all_faqs])
    print("\nСтатистика по категориям:")
    for category, count in categories.items():
        print(f"  * {category}: {count} записей")


if __name__ == "__main__":
    main()
