# test_cascade_search.py
# -*- coding: utf-8 -*-
"""
Тестирование каскадной системы поиска

Этот скрипт тестирует все 4 уровня поиска:
1. Exact Match (точное совпадение)
2. Keyword Search (поиск по ключевым словам)
3. Semantic Search (семантический поиск)
4. Fallback (вежливый отказ)
"""

import sys
import os

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import chromadb
from chromadb.utils import embedding_functions
from src.core.search import find_answer
from src.core.database import get_bot_settings

# Константы
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "faq_collection"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Тестовые запросы
TEST_CASES = {
    "УРОВЕНЬ 1 - ТОЧНОЕ СОВПАДЕНИЕ (>95%)": [
        {
            "query": "Можно ли приходить на работу в шортах?",
            "expected_level": "exact",
            "expected_faq_id": "faq_1",
            "expected_confidence_min": 95
        },
        {
            "query": "Почему в зарплате пришло меньше денег?",
            "expected_level": "exact",
            "expected_faq_id": "faq_2",
            "expected_confidence_min": 95
        },
        {
            "query": "Где получить спецодежду?",
            "expected_level": "exact",
            "expected_faq_id": "faq_3",
            "expected_confidence_min": 95
        },
        {
            "query": "  КАК ОФОРМИТЬ ОТПУСК?  ",  # С пробелами и CAPS
            "expected_level": "exact",
            "expected_faq_id": "faq_5",
            "expected_confidence_min": 95
        },
    ],

    "УРОВЕНЬ 2 - ПОИСК ПО КЛЮЧЕВЫМ СЛОВАМ (70-95%)": [
        {
            "query": "зарплата меньше",
            "expected_level": "keyword",
            "expected_faq_id": "faq_2",
            "expected_confidence_min": 70,
            "expected_confidence_max": 95
        },
        {
            "query": "пароль почта",
            "expected_level": "keyword",
            "expected_faq_id": "faq_7",
            "expected_confidence_min": 70,
            "expected_confidence_max": 95
        },
        {
            "query": "vpn доступ",
            "expected_level": "keyword",
            "expected_faq_id": "faq_13",
            "expected_confidence_min": 70,
            "expected_confidence_max": 95
        },
        {
            "query": "аванс 15",
            "expected_level": "keyword",
            "expected_faq_id": "faq_15",
            "expected_confidence_min": 70,
            "expected_confidence_max": 95
        },
    ],

    "УРОВЕНЬ 3 - СЕМАНТИЧЕСКИЙ ПОИСК (45-80%)": [
        {
            "query": "Как мне взять отгул на следующей неделе?",
            "expected_level": "semantic",
            "expected_faq_id": "faq_5",  # отпуск
            "expected_confidence_min": 45,
            "expected_confidence_max": 80
        },
        {
            "query": "У меня сломалось печатающее устройство",
            "expected_level": "semantic",
            "expected_faq_id": "faq_10",  # принтер
            "expected_confidence_min": 45,
            "expected_confidence_max": 80
        },
        {
            "query": "Мне нужна справка о зарплате для банка",
            "expected_level": "semantic",
            "expected_faq_id": "faq_6",  # 2-НДФЛ
            "expected_confidence_min": 45,
            "expected_confidence_max": 80
        },
        {
            "query": "Забыл логин от электронной почты",
            "expected_level": "semantic",
            "expected_faq_id": "faq_7",  # пароль почты
            "expected_confidence_min": 45,
            "expected_confidence_max": 80
        },
        {
            "query": "Нужно заказать ручки и бумагу",
            "expected_level": "semantic",
            "expected_faq_id": None,  # может быть faq_9 или faq_21
            "expected_confidence_min": 45,
            "expected_confidence_max": 80
        },
    ],

    "УРОВЕНЬ 4 - ОТКАЗ (0%)": [
        {
            "query": "Что такое квантовая физика?",
            "expected_level": "none",
            "expected_faq_id": None,
            "expected_confidence": 0
        },
        {
            "query": "asdfghjkl",
            "expected_level": "none",
            "expected_faq_id": None,
            "expected_confidence": 0
        },
        {
            "query": "Где купить пиццу рядом с офисом?",
            "expected_level": "none",
            "expected_faq_id": None,
            "expected_confidence": 0
        },
    ]
}


def print_separator(title=""):
    """Печать разделителя"""
    if title:
        print(f"\n{'='*80}")
        print(f" {title}")
        print('='*80)
    else:
        print('-'*80)


def test_search(query, expected_level, expected_faq_id=None,
                expected_confidence_min=None, expected_confidence_max=None,
                expected_confidence=None):
    """
    Тестирование одного запроса

    Args:
        query: текст запроса
        expected_level: ожидаемый уровень поиска
        expected_faq_id: ожидаемый ID FAQ (или None)
        expected_confidence_min: минимальная ожидаемая уверенность
        expected_confidence_max: максимальная ожидаемая уверенность
        expected_confidence: точная ожидаемая уверенность

    Returns:
        bool: True если тест пройден
    """
    # Выполняем поиск
    result = find_answer(query, collection, settings)

    # Проверяем результат
    passed = True
    issues = []

    # Проверка уровня поиска
    if result.search_level != expected_level:
        passed = False
        issues.append(f"Уровень: ожидался '{expected_level}', получен '{result.search_level}'")

    # Проверка FAQ ID
    if expected_faq_id is not None:
        if result.faq_id != expected_faq_id:
            passed = False
            issues.append(f"FAQ ID: ожидался '{expected_faq_id}', получен '{result.faq_id}'")

    # Проверка уверенности
    if expected_confidence is not None:
        if result.confidence != expected_confidence:
            passed = False
            issues.append(f"Уверенность: ожидалась {expected_confidence}%, получена {result.confidence}%")

    if expected_confidence_min is not None:
        if result.confidence < expected_confidence_min:
            passed = False
            issues.append(f"Уверенность: {result.confidence}% < {expected_confidence_min}% (минимум)")

    if expected_confidence_max is not None:
        if result.confidence > expected_confidence_max:
            passed = False
            issues.append(f"Уверенность: {result.confidence}% > {expected_confidence_max}% (максимум)")

    # Вывод результата
    status = "[OK]" if passed else "[FAIL]"
    print(f"\n{status} Запрос: {query}")
    print(f"    Уровень: {result.search_level} | Уверенность: {result.confidence:.1f}%")

    if result.found:
        print(f"    FAQ ID: {result.faq_id}")
        print(f"    Вопрос: {result.question}")
    else:
        print(f"    Результат: Ответ не найден")

    if not passed:
        for issue in issues:
            print(f"    [WARNING] {issue}")

    return passed


def main():
    """Главная функция тестирования"""
    print_separator("ТЕСТИРОВАНИЕ КАСКАДНОЙ СИСТЕМЫ ПОИСКА")

    # Загружаем ChromaDB
    print("\n[*] Загрузка ChromaDB...")
    global collection, settings

    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
        collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embedding_func)
        print(f"[OK] Коллекция загружена: {collection.count()} FAQ")
    except Exception as e:
        print(f"[ERROR] Не удалось загрузить ChromaDB: {e}")
        return

    # Загружаем настройки
    print("\n[*] Загрузка настроек...")
    settings = get_bot_settings()
    print(f"[OK] Настройки загружены")
    print(f"    - Порог точного совпадения: {settings.get('exact_match_threshold', '95')}%")
    print(f"    - Порог ключевых слов: {settings.get('keyword_match_threshold', '80')}%")
    print(f"    - Порог семантического поиска: {settings.get('semantic_match_threshold', '45')}%")
    print(f"    - Макс. слов для keyword search: {settings.get('keyword_search_max_words', '5')}")

    # Статистика
    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    # Выполняем тесты
    for category, tests in TEST_CASES.items():
        print_separator(category)

        for test_case in tests:
            total_tests += 1
            query = test_case.pop("query")

            if test_search(query, **test_case):
                passed_tests += 1
            else:
                failed_tests += 1

    # Итоги
    print_separator("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print(f"\nВсего тестов: {total_tests}")
    print(f"Пройдено: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"Провалено: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")

    if failed_tests == 0:
        print("\n[OK] Все тесты пройдены успешно!")
        return 0
    else:
        print(f"\n[WARNING] {failed_tests} тест(ов) провалено")
        return 1


if __name__ == "__main__":
    exit(main())
