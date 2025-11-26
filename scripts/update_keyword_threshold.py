#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Обновление порога keyword_match_threshold с 70% до 65%
"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.database import get_db_connection, get_bot_setting

def update_keyword_threshold():
    """Обновить keyword_match_threshold на 65%"""

    # Проверяем текущее значение
    current_value = get_bot_setting("keyword_match_threshold")
    print(f"Текущее значение keyword_match_threshold: {current_value}")

    if current_value == "65":
        print("OK: Uzhe obnovleno do 65%")
        return

    # Обновляем
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE bot_settings SET value = ? WHERE key = ?",
            ("65", "keyword_match_threshold")
        )
        conn.commit()

    # Проверяем
    new_value = get_bot_setting("keyword_match_threshold")
    print(f"OK: Obnovleno keyword_match_threshold = {new_value}%")

if __name__ == "__main__":
    update_keyword_threshold()
