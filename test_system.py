# test_system.py
# -*- coding: utf-8 -*-
"""
Быстрый тест системы
"""

import database

print("Тестирование базы данных...")

# Получаем все FAQ
all_faqs = database.get_all_faqs()
print(f"\nВсего FAQ в базе: {len(all_faqs)}")

# Получаем категории
categories = database.get_all_categories()
print(f"Категории: {', '.join(categories)}")

# Тестируем получение по категории
hr_faqs = database.get_faqs_by_category("HR")
print(f"\nFAQ в категории HR: {len(hr_faqs)}")
for faq in hr_faqs:
    print(f"  - {faq['question']}")

print("\n=== Тест успешен! ===")
print("\nТеперь можно запустить:")
print("1. python web_admin.py  - для веб-интерфейса (http://127.0.0.1:5000)")
print("2. python bot.py        - для Telegram бота")
