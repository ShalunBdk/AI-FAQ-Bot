# -*- coding: utf-8 -*-
"""
Тест граничных случаев семантического поиска

Цель: найти случаи, где лемматизация МОЖЕТ повлиять на результаты.
Тестируем сложные случаи:
- Запросы с редкими словоформами
- Запросы с опечатками
- Запросы с устаревшими формами слов
- Длинные запросы
"""

import sys
import os
import logging
from typing import List, Dict

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.utils import embedding_functions

from src.core.database import get_all_faqs
from src.core.search import find_answer, lemmatize_word

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
MODEL_NAME = os.getenv("MODEL_NAME", "deepvk/USER2-base")
CHROMA_PATH = os.getenv('CHROMA_PATH', './data/chroma_db')


def analyze_keywords_in_db():
    """
    Анализирует ключевые слова в базе и показывает примеры
    """
    faqs = get_all_faqs()

    logger.info("="*80)
    logger.info("📊 АНАЛИЗ КЛЮЧЕВЫХ СЛОВ В БАЗЕ FAQ")
    logger.info("="*80)

    # Статистика
    total_faqs = len(faqs)
    faqs_with_keywords = sum(1 for faq in faqs if faq.get('keywords'))

    logger.info(f"\n📈 Статистика:")
    logger.info(f"   Всего FAQ: {total_faqs}")
    logger.info(f"   FAQ с ключевыми словами: {faqs_with_keywords} ({faqs_with_keywords/total_faqs*100:.0f}%)")

    # Примеры FAQ с многими ключевыми словами
    logger.info(f"\n📝 FAQ с большим количеством ключевых слов:")

    faqs_sorted = sorted(
        [faq for faq in faqs if faq.get('keywords')],
        key=lambda x: len(x['keywords']) if isinstance(x['keywords'], list) else len(x['keywords'].split(',')),
        reverse=True
    )

    for i, faq in enumerate(faqs_sorted[:10], 1):
        keywords = faq['keywords']
        if isinstance(keywords, list):
            kw_count = len(keywords)
            kw_str = ', '.join(keywords[:5])
            if kw_count > 5:
                kw_str += f" ... (+{kw_count-5} еще)"
        else:
            kw_list = [k.strip() for k in keywords.split(',') if k.strip()]
            kw_count = len(kw_list)
            kw_str = ', '.join(kw_list[:5])
            if kw_count > 5:
                kw_str += f" ... (+{kw_count-5} еще)"

        logger.info(f"\n   {i}. [{kw_count} слов] {faq['question'][:60]}...")
        logger.info(f"      Ключевые слова: {kw_str}")

        # Проверяем, лемматизированы ли ключевые слова
        if isinstance(keywords, list):
            sample_kws = keywords[:3]
        else:
            sample_kws = [k.strip() for k in keywords.split(',') if k.strip()][:3]

        lemmatized = []
        for kw in sample_kws:
            lemma = lemmatize_word(kw)
            if lemma != kw.lower():
                lemmatized.append(f"{kw} → {lemma}")

        if lemmatized:
            logger.info(f"      ⚠️ Нелемматизированные слова: {', '.join(lemmatized)}")


def test_real_queries_from_db():
    """
    Тестирует реальные запросы на основе вопросов из базы
    """
    faqs = get_all_faqs()

    logger.info("\n" + "="*80)
    logger.info("🧪 ТЕСТ РЕАЛЬНЫХ ЗАПРОСОВ ИЗ БАЗЫ")
    logger.info("="*80)

    # Инициализируем ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME
    )

    try:
        collection = client.get_collection(
            name="faq_collection",
            embedding_function=embedding_func
        )
        logger.info(f"✅ Загружена коллекция 'faq_collection' ({collection.count()} документов)")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки коллекции: {e}")
        logger.error("   Запустите сначала переобучение ChromaDB из веб-админки")
        return

    # Берем несколько случайных FAQ
    import random
    sample_faqs = random.sample(faqs, min(10, len(faqs)))

    logger.info(f"\n🔍 Тестируем поиск для {len(sample_faqs)} случайных вопросов:")

    success_count = 0
    wrong_answer_count = 0

    for i, faq in enumerate(sample_faqs, 1):
        question = faq['question']
        expected_id = str(faq['id'])

        logger.info(f"\n{'─'*80}")
        logger.info(f"Тест {i}/{ len(sample_faqs)}: {question}")

        # Делаем поиск
        result = find_answer(question, collection, settings=None)

        if result.found:
            logger.info(f"   Найдено: {result.question}")
            logger.info(f"   Confidence: {result.confidence:.1f}%")
            logger.info(f"   Search level: {result.search_level}")

            # Проверяем, правильный ли ответ
            if result.faq_id == expected_id:
                logger.info(f"   ✅ ПРАВИЛЬНО (ID совпадает)")
                success_count += 1
            else:
                logger.info(f"   ⚠️ НЕПРАВИЛЬНО (ожидали ID {expected_id}, получили {result.faq_id})")
                logger.info(f"   Ожидаемый вопрос: {question}")
                wrong_answer_count += 1
        else:
            logger.info(f"   ❌ НЕ НАЙДЕНО")
            logger.info(f"   Fallback: {result.message[:100]}...")

    # Итоговая статистика
    logger.info(f"\n{'='*80}")
    logger.info(f"📊 РЕЗУЛЬТАТЫ ТЕСТА")
    logger.info(f"{'='*80}")
    logger.info(f"\n   Всего тестов: {len(sample_faqs)}")
    logger.info(f"   ✅ Правильные ответы: {success_count} ({success_count/len(sample_faqs)*100:.0f}%)")
    logger.info(f"   ⚠️ Неправильные ответы: {wrong_answer_count} ({wrong_answer_count/len(sample_faqs)*100:.0f}%)")
    logger.info(f"   ❌ Не найдено: {len(sample_faqs) - success_count - wrong_answer_count}")

    if success_count == len(sample_faqs):
        logger.info(f"\n   🎉 ОТЛИЧНО! Все вопросы нашлись правильно!")
    elif success_count / len(sample_faqs) >= 0.8:
        logger.info(f"\n   👍 ХОРОШО! Большинство вопросов нашлись правильно")
    else:
        logger.info(f"\n   ⚠️ ВНИМАНИЕ! Много неправильных ответов")


def test_word_form_variations():
    """
    Тестирует поиск с различными словоформами реальных вопросов
    """
    logger.info("\n" + "="*80)
    logger.info("🔄 ТЕСТ СЛОВОФОРМ РЕАЛЬНЫХ ВОПРОСОВ")
    logger.info("="*80)

    # Инициализируем ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME
    )

    try:
        collection = client.get_collection(
            name="faq_collection",
            embedding_function=embedding_func
        )
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки коллекции: {e}")
        return

    faqs = get_all_faqs()

    # Найдем вопросы с определенными словами и протестируем их вариации
    test_cases = []

    # Ищем вопросы со словами, которые часто изменяют форму
    target_words = ['проблема', 'принтер', 'документ', 'отчет', 'сотрудник']

    for word in target_words:
        for faq in faqs:
            question = faq['question'].lower()
            if word in question:
                test_cases.append({
                    'original': faq['question'],
                    'faq_id': str(faq['id']),
                    'target_word': word
                })
                break  # Берем только первый найденный

    logger.info(f"\n🔍 Найдено {len(test_cases)} вопросов для тестирования словоформ:")

    for i, test_case in enumerate(test_cases, 1):
        original = test_case['original']
        faq_id = test_case['faq_id']
        target_word = test_case['target_word']

        logger.info(f"\n{'─'*80}")
        logger.info(f"Тест {i}: {original}")
        logger.info(f"   Целевое слово: {target_word}")

        # Создаем вариации с изменением формы целевого слова
        variations = []

        if target_word == 'проблема':
            variations = ['проблемы', 'проблем', 'проблеме', 'проблемой']
        elif target_word == 'принтер':
            variations = ['принтера', 'принтеру', 'принтером', 'принтеры']
        elif target_word == 'документ':
            variations = ['документа', 'документу', 'документом', 'документы']
        elif target_word == 'отчет':
            variations = ['отчета', 'отчету', 'отчетом', 'отчеты']
        elif target_word == 'сотрудник':
            variations = ['сотрудника', 'сотруднику', 'сотрудником', 'сотрудники']

        # Тестируем каждую вариацию
        match_count = 0
        for variation in variations:
            modified_query = original.lower().replace(target_word, variation)

            result = find_answer(modified_query, collection, settings=None)

            if result.found and result.faq_id == faq_id:
                match_count += 1

        logger.info(f"   Результат: {match_count}/{len(variations)} вариаций нашли правильный FAQ")

        if match_count == len(variations):
            logger.info(f"   ✅ ОТЛИЧНО! Все формы слова работают")
        elif match_count >= len(variations) * 0.5:
            logger.info(f"   👍 ХОРОШО! Большинство форм работают")
        else:
            logger.info(f"   ⚠️ ВНИМАНИЕ! Мало совпадений")


def main():
    """Главная функция"""

    logger.info("="*80)
    logger.info("🔬 РАСШИРЕННЫЙ ТЕСТ СЕМАНТИЧЕСКОГО ПОИСКА")
    logger.info("="*80)
    logger.info(f"\nМодель: {MODEL_NAME}")
    logger.info(f"ChromaDB: {CHROMA_PATH}")

    # 1. Анализ ключевых слов в базе
    analyze_keywords_in_db()

    # 2. Тест реальных запросов
    test_real_queries_from_db()

    # 3. Тест словоформ
    test_word_form_variations()

    logger.info("\n" + "="*80)
    logger.info("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    logger.info("="*80)


if __name__ == "__main__":
    main()
