#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования RAG логирования
Проверяет, что метаданные RAG корректно сохраняются в базу данных
"""

import sys
import os
import json

# Добавляем путь к корневой директории
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import database

def test_rag_logging():
    """Тестирование RAG логирования"""

    print("🧪 ТЕСТ: RAG Logging Integration\n")
    print("=" * 60)

    # 1. Проверка таблицы llm_generations
    print("\n📋 1. Проверка структуры таблицы llm_generations...")
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_generations'")
            table_exists = cursor.fetchone()

            if table_exists:
                print("   ✅ Таблица llm_generations существует")

                # Получаем схему
                cursor.execute("PRAGMA table_info(llm_generations)")
                columns = cursor.fetchall()
                print(f"   ✅ Колонок в таблице: {len(columns)}")

                expected_columns = [
                    'id', 'answer_log_id', 'model', 'chunks_used', 'chunks_data',
                    'pii_detected', 'tokens_prompt', 'tokens_completion', 'tokens_total',
                    'finish_reason', 'generation_time_ms', 'error_message', 'created_at'
                ]

                actual_columns = [col[1] for col in columns]
                missing = set(expected_columns) - set(actual_columns)

                if missing:
                    print(f"   ❌ ОШИБКА: Отсутствуют колонки: {missing}")
                    return False
                else:
                    print("   ✅ Все необходимые колонки присутствуют")
            else:
                print("   ❌ ОШИБКА: Таблица llm_generations не существует!")
                print("   💡 Запустите: python scripts/migrate_add_llm_generations.py")
                return False
    except Exception as e:
        print(f"   ❌ ОШИБКА при проверке таблицы: {e}")
        return False

    # 2. Проверка функции add_llm_generation_log
    print("\n📝 2. Проверка функции add_llm_generation_log...")
    try:
        # Создаем тестовые данные
        test_chunks = [
            {"faq_id": "1", "question": "Тестовый вопрос 1", "confidence": 85.5},
            {"faq_id": "2", "question": "Тестовый вопрос 2", "confidence": 72.3}
        ]

        # Создаем тестовый query_log
        query_log_id = database.add_query_log(
            user_id=999999,
            username="test_user",
            query_text="Тестовый запрос для RAG",
            platform="web"
        )

        if not query_log_id:
            print("   ❌ ОШИБКА: Не удалось создать query_log")
            return False

        print(f"   ✅ Создан query_log (ID: {query_log_id})")

        # Создаем тестовый answer_log
        answer_log_id = database.add_answer_log(
            query_log_id=query_log_id,
            faq_id=1,
            similarity_score=85.5,
            answer_shown="Тестовый ответ с RAG генерацией",
            search_level="semantic"
        )

        if not answer_log_id:
            print("   ❌ ОШИБКА: Не удалось создать answer_log")
            return False

        print(f"   ✅ Создан answer_log (ID: {answer_log_id})")

        # Логируем RAG метаданные
        llm_gen_id = database.add_llm_generation_log(
            answer_log_id=answer_log_id,
            model="openai/gpt-4o-mini",
            chunks_used=2,
            chunks_data=test_chunks,
            pii_detected=0,
            tokens_prompt=150,
            tokens_completion=95,
            tokens_total=245,
            finish_reason="stop",
            generation_time_ms=1250,
            error_message=None
        )

        if llm_gen_id:
            print(f"   ✅ Создана RAG запись (ID: {llm_gen_id})")
        else:
            print("   ❌ ОШИБКА: Не удалось создать RAG запись")
            return False

    except Exception as e:
        print(f"   ❌ ОШИБКА при тестировании функции: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 3. Проверка сохраненных данных
    print("\n🔍 3. Проверка сохраненных данных...")
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    lg.*,
                    al.similarity_score,
                    ql.query_text
                FROM llm_generations lg
                LEFT JOIN answer_logs al ON lg.answer_log_id = al.id
                LEFT JOIN query_logs ql ON al.query_log_id = ql.id
                WHERE lg.id = ?
            """, (llm_gen_id,))

            row = cursor.fetchone()

            if not row:
                print("   ❌ ОШИБКА: Запись не найдена")
                return False

            print(f"   ✅ Найдена запись:")
            print(f"      - Model: {row['model']}")
            print(f"      - Chunks used: {row['chunks_used']}")
            print(f"      - Tokens: {row['tokens_prompt']} + {row['tokens_completion']} = {row['tokens_total']}")
            print(f"      - Generation time: {row['generation_time_ms']} ms")
            print(f"      - PII detected: {row['pii_detected']}")
            print(f"      - Finish reason: {row['finish_reason']}")
            print(f"      - Error: {row['error_message'] or 'None'}")

            # Проверяем chunks_data
            chunks_data = json.loads(row['chunks_data'])
            print(f"      - Chunks data: {len(chunks_data)} chunks")
            for i, chunk in enumerate(chunks_data, 1):
                print(f"        {i}. {chunk['question']} ({chunk['confidence']}%)")

    except Exception as e:
        print(f"   ❌ ОШИБКА при проверке данных: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. Проверка get_logs с LLM metadata
    print("\n📊 4. Проверка get_logs() с LLM metadata...")
    try:
        logs = database.get_logs(filters={})

        # Ищем нашу тестовую запись
        test_log = None
        for log in logs:
            if log.get('query_id') == query_log_id:
                test_log = log
                break

        if not test_log:
            print("   ❌ ОШИБКА: Тестовая запись не найдена в get_logs()")
            return False

        if 'llm_metadata' not in test_log:
            print("   ❌ ОШИБКА: llm_metadata отсутствует в результате")
            return False

        llm_meta = test_log['llm_metadata']

        if not llm_meta:
            print("   ❌ ОШИБКА: llm_metadata равен NULL")
            return False

        print("   ✅ LLM metadata найдена в get_logs()")
        print(f"      - ID: {llm_meta['id']}")
        print(f"      - Model: {llm_meta['model']}")
        print(f"      - Chunks: {llm_meta['chunks_used']}")
        print(f"      - Tokens: {llm_meta['tokens']}")
        print(f"      - Chunks data: {len(llm_meta['chunks_data'])} элементов")

    except Exception as e:
        print(f"   ❌ ОШИБКА при проверке get_logs: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 5. Проверка статистики
    print("\n📈 5. Проверка RAG статистики...")
    try:
        stats = database.get_statistics(filters={})

        if 'rag_answers' in stats:
            print(f"   ✅ RAG статистика найдена:")
            print(f"      - RAG answers: {stats['rag_answers']}")
            print(f"      - Avg tokens: {stats['rag_avg_tokens']}")
            print(f"      - Total tokens: {stats['rag_total_tokens']}")
            print(f"      - RAG errors: {stats['rag_errors']}")
        else:
            print("   ❌ ОШИБКА: RAG статистика отсутствует в get_statistics()")
            return False

    except Exception as e:
        print(f"   ❌ ОШИБКА при проверке статистики: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 6. Очистка тестовых данных
    print("\n🧹 6. Очистка тестовых данных...")
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()

            # Удаляем в обратном порядке (из-за FOREIGN KEY)
            cursor.execute("DELETE FROM llm_generations WHERE id = ?", (llm_gen_id,))
            cursor.execute("DELETE FROM answer_logs WHERE id = ?", (answer_log_id,))
            cursor.execute("DELETE FROM query_logs WHERE id = ?", (query_log_id,))

            conn.commit()
            print("   ✅ Тестовые данные удалены")

    except Exception as e:
        print(f"   ⚠️  ПРЕДУПРЕЖДЕНИЕ: Не удалось очистить тестовые данные: {e}")

    print("\n" + "=" * 60)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!\n")
    return True


if __name__ == "__main__":
    success = test_rag_logging()
    sys.exit(0 if success else 1)
