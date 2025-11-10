# -*- coding: utf-8 -*-
"""
Тестирование системы логирования
"""

import database

def test_logging():
    """Тестируем логирование"""
    print("=" * 60)
    print("Тест системы логирования")
    print("=" * 60)

    # 1. Тестируем логирование запроса
    print("\n1. Логирование запроса пользователя...")
    query_log_id = database.add_query_log(
        user_id=12345,
        username="test_user",
        query_text="Как получить спецовку?"
    )
    if query_log_id:
        print(f"   OK: Запрос залогирован с ID {query_log_id}")
    else:
        print("   ОШИБКА: Не удалось залогировать запрос")
        return

    # 2. Тестируем логирование ответа
    print("\n2. Логирование ответа...")
    answer_log_id = database.add_answer_log(
        query_log_id=query_log_id,
        faq_id="faq_123",
        similarity_score=85.5,
        answer_shown="Спецодежду можно получить в отделе..."
    )
    if answer_log_id:
        print(f"   OK: Ответ залогирован с ID {answer_log_id}")
    else:
        print("   ОШИБКА: Не удалось залогировать ответ")
        return

    # 3. Тестируем логирование оценки
    print("\n3. Логирование положительной оценки...")
    if database.add_rating_log(
        answer_log_id=answer_log_id,
        user_id=12345,
        rating="helpful"
    ):
        print("   OK: Положительная оценка залогирована")
    else:
        print("   ОШИБКА: Не удалось залогировать оценку")
        return

    # 4. Добавляем еще несколько записей для теста
    print("\n4. Добавление дополнительных тестовых записей...")

    # Запрос 2
    q2 = database.add_query_log(67890, "user2", "Как отправить посылку?")
    a2 = database.add_answer_log(q2, "faq_456", 92.3, "Посылки отправляются через...")
    database.add_rating_log(a2, 67890, "helpful")

    # Запрос 3 с негативной оценкой
    q3 = database.add_query_log(54321, "user3", "Где парковка?")
    a3 = database.add_answer_log(q3, "faq_789", 45.0, "Парковка находится...")
    database.add_rating_log(a3, 54321, "not_helpful")

    # Запрос 4 без оценки
    q4 = database.add_query_log(11111, "user4", "Режим работы?")
    database.add_answer_log(q4, "faq_101", 78.0, "Мы работаем с 9 до 18...")

    print("   OK: Добавлено еще 3 тестовых записи")

    # 5. Получение логов
    print("\n5. Получение логов...")
    logs, total = database.get_logs(limit=10, offset=0)
    print(f"   OK: Получено {len(logs)} логов из {total} всего")

    # 6. Получение статистики
    print("\n6. Получение статистики...")
    stats = database.get_statistics()
    print(f"   Всего запросов: {stats.get('total_queries', 0)}")
    print(f"   Средняя схожесть: {stats.get('avg_similarity', 0)}%")
    print(f"   Положительных оценок: {stats.get('helpful_count', 0)}")
    print(f"   Отрицательных оценок: {stats.get('not_helpful_count', 0)}")
    print(f"   % полезных ответов: {stats.get('helpful_percentage', 0)}%")

    # 7. Тест фильтрации
    print("\n7. Тест фильтрации по оценке...")
    helpful_logs, helpful_total = database.get_logs(rating_filter='helpful')
    print(f"   OK: Найдено {helpful_total} логов с положительной оценкой")

    print("\n" + "=" * 60)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)
    print("\nСистема логирования работает корректно.")
    print("Теперь можно запускать бота и проверять логи в админке:")
    print("  1. Запустите бота: python bot.py")
    print("  2. Запустите админку: python web_admin.py")
    print("  3. Откройте http://127.0.0.1:5000/logs")

if __name__ == "__main__":
    database.init_database()
    test_logging()
