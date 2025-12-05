# -*- coding: utf-8 -*-
"""
Тест влияния лемматизации на семантический поиск

Цель: проверить, не ухудшает ли лемматизация ключевых слов в документах
точность семантического поиска при различных формах слов в запросе.

Методика:
1. Загружаем FAQ с оригинальными (нелемматизированными) ключевыми словами
2. Создаем две версии ChromaDB:
   - Версия A: документы с оригинальными ключевыми словами
   - Версия B: документы с лемматизированными ключевыми словами
3. Тестируем одинаковые запросы в разных словоформах
4. Сравниваем результаты (similarity scores)
"""

import sys
import os
import logging
from typing import List, Dict, Tuple

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.utils import embedding_functions

from src.core.database import get_all_faqs
from src.core.search import lemmatize_word, lemmatize_text, normalize_text

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
MODEL_NAME = os.getenv("MODEL_NAME", "deepvk/USER2-base")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "45"))

# Тестовые запросы в разных формах
TEST_QUERIES = [
    # Формат: (оригинал, лемматизированная версия, описание)
    ("как составить претензию?", "как составить претензия?", "составить претензию"),
    ("у меня проблемы с почтой", "у я проблема с почта", "проблемы с почтой"),
    ("нужна справка о доходах", "нужный справка о доход", "справка о доходах"),
    ("не работает принтер", "не работать принтер", "не работает принтер"),
    ("отправка писем не работает", "отправка письмо не работать", "отправка писем"),
    ("хочу подать жалобу", "хотеть подать жалоба", "подать жалобу"),
    ("требуется замена картриджа", "требоваться замена картридж", "замена картриджа"),
    ("инструкция по настройке", "инструкция по настройка", "настройка"),
    ("проблема с авторизацией", "проблема с авторизация", "авторизация"),
    ("как оформить возврат товара?", "как оформить возврат товар?", "возврат товара"),
]


def create_collection_with_keywords(
    client: chromadb.Client,
    collection_name: str,
    faqs: List[Dict],
    lemmatize_keywords: bool = False
) -> chromadb.Collection:
    """
    Создает ChromaDB коллекцию с FAQ

    Args:
        client: ChromaDB клиент
        collection_name: Имя коллекции
        faqs: Список FAQ из базы данных
        lemmatize_keywords: Если True, лемматизирует ключевые слова

    Returns:
        ChromaDB коллекция
    """
    # Удаляем старую коллекцию если есть
    try:
        client.delete_collection(name=collection_name)
    except:
        pass

    # Создаем embedding function
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME
    )

    # Создаем коллекцию
    collection = client.create_collection(
        name=collection_name,
        embedding_function=embedding_func,
        metadata={"hnsw:space": "cosine"}
    )

    # Подготавливаем документы
    documents, metadatas, ids = [], [], []

    for faq in faqs:
        # Обрабатываем ключевые слова
        keywords_data = faq.get('keywords', '')

        # Проверяем тип данных (может быть строка или список)
        if isinstance(keywords_data, list):
            keywords_list = keywords_data
        elif isinstance(keywords_data, str):
            keywords_list = [kw.strip() for kw in keywords_data.split(',') if kw.strip()]
        else:
            keywords_list = []

        if keywords_list and lemmatize_keywords:
            # Лемматизируем каждое ключевое слово
            keywords_list = [lemmatize_word(kw) for kw in keywords_list]

        keywords = ' '.join(keywords_list) if keywords_list else ''

        # Формируем текст документа
        text = f"{faq['question']} {keywords}"
        documents.append(f"search_document: {text}")

        metadatas.append({
            "category": faq["category"],
            "question": faq["question"],
            "answer": faq["answer"][:100] + "..." if len(faq["answer"]) > 100 else faq["answer"]
        })
        ids.append(str(faq["id"]))

    # Добавляем в коллекцию
    collection.add(documents=documents, metadatas=metadatas, ids=ids)

    logger.info(f"✅ Создана коллекция '{collection_name}' с {len(faqs)} FAQ")
    logger.info(f"   Лемматизация ключевых слов: {'Да' if lemmatize_keywords else 'Нет'}")

    return collection


def search_in_collection(
    collection: chromadb.Collection,
    query: str,
    n_results: int = 3
) -> List[Tuple[str, float, str]]:
    """
    Поиск в коллекции

    Args:
        collection: ChromaDB коллекция
        query: Поисковый запрос
        n_results: Количество результатов

    Returns:
        Список кортежей (question, similarity, faq_id)
    """
    try:
        results = collection.query(
            query_texts=[f"search_query: {query}"],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        if not results or not results['ids'] or not results['ids'][0]:
            return []

        output = []
        for i in range(len(results['ids'][0])):
            distance = results['distances'][0][i]
            similarity = max(0.0, 1.0 - distance) * 100.0
            metadata = results['metadatas'][0][i]
            faq_id = results['ids'][0][i]
            question = metadata['question']

            output.append((question, similarity, faq_id))

        return output

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return []


def compare_search_results(
    collection_original: chromadb.Collection,
    collection_lemmatized: chromadb.Collection,
    query_original: str,
    query_lemmatized: str,
    description: str
) -> Dict:
    """
    Сравнивает результаты поиска в двух коллекциях

    Args:
        collection_original: Коллекция с оригинальными ключевыми словами
        collection_lemmatized: Коллекция с лемматизированными ключевыми словами
        query_original: Оригинальный запрос (с разными формами слов)
        query_lemmatized: Лемматизированный запрос
        description: Описание теста

    Returns:
        Словарь с результатами сравнения
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"📝 Тест: {description}")
    logger.info(f"{'='*80}")

    # Поиск с оригинальным запросом
    logger.info(f"\n🔍 Запрос (оригинал): '{query_original}'")

    results_orig_orig = search_in_collection(collection_original, query_original, n_results=3)
    results_orig_lem = search_in_collection(collection_lemmatized, query_original, n_results=3)

    logger.info(f"\n   📊 Результаты (оригинальные ключевые слова):")
    if results_orig_orig:
        for i, (question, similarity, faq_id) in enumerate(results_orig_orig, 1):
            logger.info(f"      {i}. [{similarity:.1f}%] {question}")
    else:
        logger.info(f"      ❌ Ничего не найдено")

    logger.info(f"\n   📊 Результаты (лемматизированные ключевые слова):")
    if results_orig_lem:
        for i, (question, similarity, faq_id) in enumerate(results_orig_lem, 1):
            logger.info(f"      {i}. [{similarity:.1f}%] {question}")
    else:
        logger.info(f"      ❌ Ничего не найдено")

    # Поиск с лемматизированным запросом
    logger.info(f"\n🔍 Запрос (лемматизированный): '{query_lemmatized}'")

    results_lem_orig = search_in_collection(collection_original, query_lemmatized, n_results=3)
    results_lem_lem = search_in_collection(collection_lemmatized, query_lemmatized, n_results=3)

    logger.info(f"\n   📊 Результаты (оригинальные ключевые слова):")
    if results_lem_orig:
        for i, (question, similarity, faq_id) in enumerate(results_lem_orig, 1):
            logger.info(f"      {i}. [{similarity:.1f}%] {question}")
    else:
        logger.info(f"      ❌ Ничего не найдено")

    logger.info(f"\n   📊 Результаты (лемматизированные ключевые слова):")
    if results_lem_lem:
        for i, (question, similarity, faq_id) in enumerate(results_lem_lem, 1):
            logger.info(f"      {i}. [{similarity:.1f}%] {question}")
    else:
        logger.info(f"      ❌ Ничего не найдено")

    # Анализ различий
    logger.info(f"\n💡 Анализ:")

    # Сравниваем топ-1 результаты для оригинального запроса
    if results_orig_orig and results_orig_lem:
        top1_orig = results_orig_orig[0]
        top1_lem = results_orig_lem[0]

        diff_similarity = top1_lem[1] - top1_orig[1]

        if abs(diff_similarity) < 1.0:
            logger.info(f"   ✅ Разница незначительна: {diff_similarity:+.1f}%")
        elif diff_similarity > 0:
            logger.info(f"   ✅ Лемматизация улучшила поиск на {diff_similarity:.1f}%")
        else:
            logger.info(f"   ⚠️ Лемматизация ухудшила поиск на {abs(diff_similarity):.1f}%")

        if top1_orig[2] != top1_lem[2]:
            logger.info(f"   ⚠️ ВНИМАНИЕ: Изменился топ-1 результат!")
            logger.info(f"      Без лемматизации: {top1_orig[0]}")
            logger.info(f"      С лемматизацией: {top1_lem[0]}")

    return {
        'query_original': query_original,
        'query_lemmatized': query_lemmatized,
        'results_orig_orig': results_orig_orig,
        'results_orig_lem': results_orig_lem,
        'results_lem_orig': results_lem_orig,
        'results_lem_lem': results_lem_lem
    }


def main():
    """Главная функция"""

    logger.info("="*80)
    logger.info("🧪 ТЕСТ ВЛИЯНИЯ ЛЕММАТИЗАЦИИ НА СЕМАНТИЧЕСКИЙ ПОИСК")
    logger.info("="*80)
    logger.info(f"\n📋 Параметры:")
    logger.info(f"   Модель: {MODEL_NAME}")
    logger.info(f"   Порог similarity: {SIMILARITY_THRESHOLD}%")
    logger.info(f"   Количество тестов: {len(TEST_QUERIES)}")

    # Загружаем FAQ из базы
    logger.info(f"\n📥 Загрузка FAQ из базы данных...")
    faqs = get_all_faqs()

    if not faqs:
        logger.error("❌ В базе нет FAQ для тестирования!")
        return

    logger.info(f"✅ Загружено {len(faqs)} FAQ")

    # Показываем несколько примеров FAQ с ключевыми словами
    logger.info(f"\n📝 Примеры FAQ с ключевыми словами:")
    for i, faq in enumerate(faqs[:5], 1):
        keywords = faq.get('keywords', '')
        logger.info(f"   {i}. {faq['question']}")
        logger.info(f"      Ключевые слова: {keywords if keywords else '(нет)'}")

    # Создаем ChromaDB клиент (in-memory для тестов)
    logger.info(f"\n🔧 Создание тестовых коллекций...")
    client = chromadb.Client()

    # Создаем две коллекции
    collection_original = create_collection_with_keywords(
        client, "test_original", faqs, lemmatize_keywords=False
    )

    collection_lemmatized = create_collection_with_keywords(
        client, "test_lemmatized", faqs, lemmatize_keywords=True
    )

    # Запускаем тесты
    logger.info(f"\n🚀 Запуск тестов...")

    all_results = []
    improvements = 0
    degradations = 0
    no_change = 0

    for query_original, query_lemmatized, description in TEST_QUERIES:
        result = compare_search_results(
            collection_original,
            collection_lemmatized,
            query_original,
            query_lemmatized,
            description
        )
        all_results.append(result)

        # Считаем статистику
        if result['results_orig_orig'] and result['results_orig_lem']:
            top1_orig = result['results_orig_orig'][0]
            top1_lem = result['results_orig_lem'][0]
            diff = top1_lem[1] - top1_orig[1]

            if abs(diff) < 1.0:
                no_change += 1
            elif diff > 0:
                improvements += 1
            else:
                degradations += 1

    # Итоговая статистика
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 ИТОГОВАЯ СТАТИСТИКА")
    logger.info(f"{'='*80}")
    logger.info(f"\n   Всего тестов: {len(TEST_QUERIES)}")
    logger.info(f"   ✅ Улучшение: {improvements} ({improvements/len(TEST_QUERIES)*100:.0f}%)")
    logger.info(f"   ⚠️ Ухудшение: {degradations} ({degradations/len(TEST_QUERIES)*100:.0f}%)")
    logger.info(f"   ➖ Без изменений: {no_change} ({no_change/len(TEST_QUERIES)*100:.0f}%)")

    # Выводы
    logger.info(f"\n💡 ВЫВОДЫ:")

    if degradations > improvements:
        logger.info(f"   ⚠️ Лемматизация ключевых слов в документах УХУДШАЕТ семантический поиск")
        logger.info(f"   Рекомендация: использовать оригинальные формы слов в ключевых словах")
    elif improvements > degradations:
        logger.info(f"   ✅ Лемматизация ключевых слов в документах УЛУЧШАЕТ семантический поиск")
        logger.info(f"   Рекомендация: продолжать использовать лемматизацию")
    else:
        logger.info(f"   ➖ Лемматизация ключевых слов НЕ ВЛИЯЕТ на семантический поиск")
        logger.info(f"   Рекомендация: можно использовать любой подход")

    logger.info(f"\n" + "="*80)


if __name__ == "__main__":
    main()
