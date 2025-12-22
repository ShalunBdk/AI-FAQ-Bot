#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция: Добавление таблицы llm_generations для RAG метаданных
"""

import sqlite3
import os
import sys

# Добавляем путь к корневой директории
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import get_db_connection

def migrate():
    """Добавляет таблицу llm_generations"""

    print("🔧 Начало миграции: Добавление таблицы llm_generations...")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Создаем таблицу llm_generations
        print("   📝 Создание таблицы llm_generations...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                answer_log_id INTEGER NOT NULL,
                model TEXT,
                chunks_used INTEGER,
                chunks_data TEXT,
                pii_detected INTEGER,
                tokens_prompt INTEGER,
                tokens_completion INTEGER,
                tokens_total INTEGER,
                finish_reason TEXT,
                generation_time_ms INTEGER,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (answer_log_id) REFERENCES answer_logs(id)
            )
        """)

        # 2. Создаем индексы
        print("   📑 Создание индексов...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_generations_answer_log
                ON llm_generations(answer_log_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_generations_model
                ON llm_generations(model)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_llm_generations_error
                ON llm_generations(error_message)
        """)

        conn.commit()

    print("✅ Миграция завершена успешно!")

if __name__ == "__main__":
    migrate()
