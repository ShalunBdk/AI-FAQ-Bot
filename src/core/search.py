# -*- coding: utf-8 -*-
"""
Модуль каскадного поиска ответов в FAQ

Реализует 4-уровневую систему поиска:
1. Exact Match - точное совпадение вопроса
2. Keyword Search - поиск по ключевым словам (для коротких запросов)
3. Semantic Search - семантический поиск через ChromaDB
4. Fallback - вежливый отказ с предложениями
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional, Dict, List, Set

logger = logging.getLogger(__name__)

# ========== СТОП-СЛОВА ДЛЯ РУССКОГО ЯЗЫКА ==========

RUSSIAN_STOP_WORDS = {
    'в', 'и', 'на', 'с', 'по', 'к', 'о', 'от', 'для', 'из', 'у', 'при',
    'это', 'как', 'что', 'где', 'когда', 'кто', 'чем', 'же', 'бы', 'ли',
    'а', 'но', 'или', 'да', 'нет', 'не', 'ни', 'то', 'те', 'эти', 'вы',
    'мы', 'он', 'она', 'они', 'оно', 'я', 'ты', 'мой', 'твой', 'его',
    'её', 'наш', 'ваш', 'их', 'был', 'была', 'было', 'были', 'есть',
    'быть', 'делать', 'сделать', 'мочь', 'хотеть', 'сказать', 'говорить',
    'знать', 'стать', 'видеть', 'хороший', 'новый', 'большой', 'другой'
}


# ========== ЛЕММАТИЗАЦИЯ ==========

# Глобальный морфологический анализатор (lazy loading)
_morph_analyzer = None


def get_morph_analyzer():
    """
    Получить морфологический анализатор с ленивой инициализацией

    Returns:
        pymorphy3.MorphAnalyzer
    """
    global _morph_analyzer
    if _morph_analyzer is None:
        try:
            import pymorphy3
            _morph_analyzer = pymorphy3.MorphAnalyzer()
            logger.debug("Морфологический анализатор pymorphy3 инициализирован")
        except ImportError:
            logger.warning("pymorphy3 не установлен. Лемматизация отключена.")
            _morph_analyzer = False  # Отметить, что попытка была
        except Exception as e:
            logger.error(f"Ошибка при инициализации pymorphy3: {e}")
            _morph_analyzer = False

    return _morph_analyzer if _morph_analyzer else None


def lemmatize_word(word: str) -> str:
    """
    Лемматизация одного слова (приведение к начальной форме)

    Примеры:
        - претензию → претензия
        - претензии → претензия
        - составить → составить
        - нарушения → нарушение

    Args:
        word: Слово для лемматизации

    Returns:
        Лемма (начальная форма) или исходное слово, если лемматизация недоступна
    """
    morph = get_morph_analyzer()

    if not morph or not word:
        return word.lower()

    try:
        # Парсим слово и берем первую (наиболее вероятную) лемму
        parsed = morph.parse(word)
        if parsed:
            lemma = parsed[0].normal_form
            return lemma.lower()
    except Exception as e:
        logger.debug(f"Ошибка лемматизации слова '{word}': {e}")

    return word.lower()


def lemmatize_text(text: str) -> List[str]:
    """
    Лемматизация текста (список лемм всех слов)

    Args:
        text: Текст для лемматизации

    Returns:
        Список лемматизированных слов
    """
    # Нормализуем текст (удаление пунктуации, приведение к lowercase)
    normalized = normalize_text(text)
    words = normalized.split()

    # Лемматизируем каждое слово
    lemmas = [lemmatize_word(word) for word in words]

    return lemmas


# ========== КЛАСС РЕЗУЛЬТАТА ПОИСКА ==========

@dataclass
class SearchResult:
    """
    Результат каскадного поиска

    Attributes:
        found: True если ответ найден, False если нет
        faq_id: ID FAQ из базы данных
        question: Текст вопроса из FAQ
        answer: Текст ответа
        confidence: Уверенность в ответе (0-100%)
        search_level: Уровень поиска ('exact', 'keyword', 'semantic', 'none', 'direct')
        all_results: Полные результаты ChromaDB (для похожих вопросов)
        message: Сообщение для пользователя (используется для fallback)
    """
    found: bool
    faq_id: Optional[str]
    question: Optional[str]
    answer: Optional[str]
    confidence: float
    search_level: str
    all_results: Optional[Dict]
    message: Optional[str]


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def normalize_text(text: str) -> str:
    """
    Нормализация текста для точного совпадения

    Выполняет:
    - Приведение к нижнему регистру
    - Удаление лишних пробелов
    - Удаление знаков препинания
    - Нормализация множественных пробелов

    Args:
        text: Исходный текст

    Returns:
        Нормализованный текст
    """
    if not text:
        return ""

    # Нижний регистр
    text = text.lower().strip()

    # Удаляем знаки препинания (кроме дефиса и точки в числах)
    text = re.sub(r'[^\w\s\-]', ' ', text)

    # Множественные пробелы → один пробел
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def extract_keywords(text: str, min_length: int = 3, use_lemmatization: bool = True) -> List[str]:
    """
    Извлечение ключевых слов из текста с лемматизацией

    Процесс:
    1. Нормализация текста (удаление пунктуации, lowercase)
    2. Лемматизация слов (приведение к начальной форме)
    3. Удаление стоп-слов и коротких слов
    4. Удаление дубликатов

    Args:
        text: Исходный текст
        min_length: Минимальная длина слова
        use_lemmatization: Использовать лемматизацию (True по умолчанию)

    Returns:
        Список уникальных лемматизированных ключевых слов

    Examples:
        >>> extract_keywords("Как составить претензию?")
        ['составить', 'претензия']  # "составить" уже в начальной форме
        >>> extract_keywords("У меня проблемы с оборудованием")
        ['проблема', 'оборудование']  # "проблемы" → "проблема"
    """
    if use_lemmatization:
        # Лемматизируем текст
        lemmas = lemmatize_text(text)
    else:
        # Обычная нормализация (без лемматизации)
        normalized = normalize_text(text)
        lemmas = normalized.split()

    # Фильтруем стоп-слова и короткие слова
    keywords = [
        word for word in lemmas
        if word not in RUSSIAN_STOP_WORDS and len(word) >= min_length
    ]

    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return unique_keywords


def calculate_keyword_confidence(
    matched_keywords: int,
    total_query_keywords: int,
    total_faq_keywords: int
) -> float:
    """
    Вычисление confidence для keyword search

    Приоритет: сколько слов из запроса пользователя найдено.
    Формула НЕ штрафует FAQ с большим количеством ключевых слов.

    Логика:
    - Все слова из запроса найдены → 95% (максимум для keyword search)
    - Частичное совпадение → 70% + (процент_совпадений * 25%)

    Args:
        matched_keywords: Количество совпавших ключевых слов
        total_query_keywords: Общее количество ключевых слов в запросе
        total_faq_keywords: Общее количество ключевых слов в FAQ (не используется)

    Returns:
        Confidence (70-95%)
    """
    if total_query_keywords == 0:
        return 0.0

    # Процент совпадения с запросом пользователя (главный критерий)
    query_match_ratio = matched_keywords / total_query_keywords

    # Если все слова из запроса найдены → максимальный confidence
    if query_match_ratio == 1.0:
        return 95.0

    # Частичное совпадение: базовый confidence 70% + бонус за каждое совпадение
    base_confidence = 70.0
    match_bonus = query_match_ratio * 25.0  # До +25% за совпадения

    confidence = base_confidence + match_bonus

    # Максимум 95% для keyword search (чтобы exact match всегда был лучше)
    return min(confidence, 95.0)


# ========== УРОВЕНЬ 1: EXACT MATCH ==========

def find_exact_match(query_text: str) -> Optional[SearchResult]:
    """
    Уровень 1: Поиск точного совпадения вопроса в базе данных

    Самый быстрый метод (O(1) с индексом). Ищет полное совпадение
    нормализованного вопроса.

    Args:
        query_text: Текст запроса пользователя

    Returns:
        SearchResult с confidence=100% или None
    """
    from src.core.database import get_db_connection

    normalized_query = normalize_text(query_text)

    if not normalized_query:
        return None

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Получаем все вопросы и проверяем нормализованное совпадение
            cursor.execute("""
                SELECT id, category, question, answer, keywords
                FROM faq
            """)

            for row in cursor.fetchall():
                # Нормализуем вопрос из БД тем же способом
                normalized_db_question = normalize_text(row["question"])

                if normalized_db_question == normalized_query:
                    logger.debug(f"  [Exact Match] Найдено: {row['question']}")
                    return SearchResult(
                        found=True,
                        faq_id=row["id"],
                        question=row["question"],
                        answer=row["answer"],
                        confidence=100.0,
                        search_level='exact',
                        all_results=None,
                        message=None
                    )

    except Exception as e:
        logger.error(f"Ошибка в find_exact_match: {e}", exc_info=True)

    return None


# ========== УРОВЕНЬ 2: KEYWORD SEARCH ==========

def find_by_keywords(query_text: str, max_query_words: int = 5, threshold: float = 80.0) -> Optional[SearchResult]:
    """
    Уровень 2: Поиск по ключевым словам (только для коротких запросов)

    Подходит для коротких запросов типа "справка 2-НДФЛ", "зарплата отпуск"

    Args:
        query_text: Текст запроса
        max_query_words: Максимум слов в запросе для keyword search
        threshold: Минимальный порог уверенности (по умолчанию 80%)

    Returns:
        SearchResult с confidence 80-95% или None
    """
    from src.core.database import get_db_connection

    # Проверяем длину запроса
    if len(query_text.split()) > max_query_words:
        logger.debug(f"  [Keyword Search] Пропущен: запрос слишком длинный ({len(query_text.split())} слов)")
        return None

    # Извлекаем ключевые слова
    query_keywords = extract_keywords(query_text)

    if not query_keywords:
        logger.debug("  [Keyword Search] Пропущен: нет ключевых слов")
        return None

    logger.debug(f"  [Keyword Search] Ключевые слова: {query_keywords}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Строим WHERE условие для поиска по каждому ключевому слову
            # Ищем в вопросе И в ключевых словах
            conditions = []
            params = []

            for keyword in query_keywords:
                conditions.append(
                    "(LOWER(question) LIKE ? OR LOWER(keywords) LIKE ?)"
                )
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            where_clause = " OR ".join(conditions)

            # Запрос с подсчетом совпадений
            # Для каждого ключевого слова проверяем, есть ли оно в question или keywords
            match_checks = []
            count_params = []
            for keyword in query_keywords:
                match_checks.append(
                    "(CASE WHEN LOWER(question) LIKE ? OR LOWER(keywords) LIKE ? THEN 1 ELSE 0 END)"
                )
                count_params.extend([f"%{keyword}%", f"%{keyword}%"])

            query_sql = f"""
                SELECT
                    id, category, question, answer, keywords,
                    ({' + '.join(match_checks)}) as match_count
                FROM faq
                WHERE {where_clause}
                ORDER BY match_count DESC
                LIMIT 1
            """

            # Полные параметры: для подсчета + для WHERE
            full_params = count_params + params

            cursor.execute(query_sql, full_params)
            row = cursor.fetchone()

            if row and row["match_count"] > 0:
                # Вычисляем confidence
                matched_keywords = row["match_count"]

                # Получаем ключевые слова из FAQ
                faq_keywords_str = row["keywords"] or ""
                faq_keywords = [k.strip() for k in faq_keywords_str.split(",") if k.strip()]

                confidence = calculate_keyword_confidence(
                    matched_keywords=matched_keywords,
                    total_query_keywords=len(query_keywords),
                    total_faq_keywords=len(faq_keywords)
                )

                logger.debug(f"  [Keyword Search] Совпадений: {matched_keywords}/{len(query_keywords)}, confidence: {confidence:.1f}%")

                # Проверяем порог уверенности
                if confidence >= threshold:
                    return SearchResult(
                        found=True,
                        faq_id=row["id"],
                        question=row["question"],
                        answer=row["answer"],
                        confidence=confidence,
                        search_level='keyword',
                        all_results=None,
                        message=None
                    )
                else:
                    logger.debug(f"  [Keyword Search] Отклонено: confidence {confidence:.1f}% < {threshold}%")

    except Exception as e:
        logger.error(f"Ошибка в find_by_keywords: {e}", exc_info=True)

    return None


# ========== УРОВЕНЬ 3: SEMANTIC SEARCH ==========

def find_semantic_match(
    query_text: str,
    collection,
    threshold: float = 45.0,
    n_results: int = 3
) -> Optional[SearchResult]:
    """
    Уровень 3: Семантический поиск через ChromaDB

    Использует векторные эмбеддинги для понимания смысла вопроса.
    Самый "умный", но и самый медленный метод.

    Args:
        query_text: Текст запроса
        collection: ChromaDB коллекция
        threshold: Порог схожести (по умолчанию из настроек)
        n_results: Количество результатов

    Returns:
        SearchResult с confidence >= threshold или None
    """
    if collection is None:
        logger.error("ChromaDB collection не инициализирована")
        return None

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        if not results or not results['ids'] or not results['ids'][0]:
            logger.debug("  [Semantic Search] Ничего не найдено в ChromaDB")
            return None

        # Лучший результат
        best_distance = results['distances'][0][0]
        similarity = max(0.0, 1.0 - best_distance) * 100.0
        best_metadata = results['metadatas'][0][0]
        faq_id = results['ids'][0][0]

        logger.debug(f"  [Semantic Search] Лучший результат: similarity={similarity:.1f}%, threshold={threshold}%")

        if similarity >= threshold:
            return SearchResult(
                found=True,
                faq_id=faq_id,
                question=best_metadata['question'],
                answer=best_metadata['answer'],
                confidence=similarity,
                search_level='semantic',
                all_results=results,
                message=None
            )
        else:
            logger.debug(f"  [Semantic Search] Отклонено: similarity {similarity:.1f}% < threshold {threshold}%")

    except Exception as e:
        logger.error(f"Ошибка в find_semantic_match: {e}", exc_info=True)

    return None


# ========== УРОВЕНЬ 4: FALLBACK ==========

def get_fallback_result() -> SearchResult:
    """
    Уровень 4: Fallback - вежливый отказ с предложениями

    Вызывается когда все предыдущие уровни не нашли ответ.

    Returns:
        SearchResult с found=False и сообщением пользователю
    """
    from src.core.database import get_bot_setting

    # Получаем сообщение из настроек (если есть)
    fallback_message = get_bot_setting("fallback_message")

    if not fallback_message:
        fallback_message = (
            "😔 Извините, я не нашел точного ответа на ваш вопрос.\n\n"
            "Попробуйте:\n"
            "• Переформулировать вопрос\n"
            "• Выбрать категорию из списка\n"
            "• Обратиться к ответственному сотруднику"
        )

    return SearchResult(
        found=False,
        faq_id=None,
        question=None,
        answer=None,
        confidence=0.0,
        search_level='none',
        all_results=None,
        message=fallback_message
    )


# ========== ГЛАВНАЯ ФУНКЦИЯ: КАСКАДНЫЙ ПОИСК ==========

def find_answer(
    query_text: str,
    collection,
    settings: Optional[Dict] = None
) -> SearchResult:
    """
    Каскадный поиск ответа по 4 уровням

    Процесс:
    1. Пытается найти точное совпадение (exact match)
    2. Если не найдено и запрос короткий - ищет по ключевым словам
    3. Если не найдено - семантический поиск через ChromaDB
    4. Если ничего не найдено - возвращает fallback

    Args:
        query_text: Текст запроса пользователя
        collection: ChromaDB коллекция
        settings: Настройки (пороги, параметры). Если None - берутся из БД

    Returns:
        SearchResult с найденным ответом или fallback
    """
    from src.core.database import get_bot_settings

    # Загружаем настройки если не переданы
    if settings is None:
        settings = get_bot_settings()

    # Пороги из настроек
    exact_threshold = float(settings.get('exact_match_threshold', 95))
    keyword_threshold = float(settings.get('keyword_match_threshold', 80))
    semantic_threshold = float(settings.get('semantic_match_threshold', 45))
    keyword_max_words = int(settings.get('keyword_search_max_words', 5))

    logger.info(f"🔍 Каскадный поиск для запроса: '{query_text}'")
    logger.debug(f"  Пороги: exact={exact_threshold}%, keyword={keyword_threshold}%, semantic={semantic_threshold}%")

    # УРОВЕНЬ 1: Exact Match
    logger.debug("  Уровень 1: Поиск точного совпадения...")
    result = find_exact_match(query_text)
    if result and result.confidence >= exact_threshold:
        logger.info(f"  ✅ Найдено точное совпадение! Confidence: {result.confidence}%")
        return result

    # УРОВЕНЬ 2: Keyword Search (только для коротких запросов)
    if len(query_text.split()) <= keyword_max_words:
        logger.debug("  Уровень 2: Поиск по ключевым словам...")
        result = find_by_keywords(query_text, max_query_words=keyword_max_words, threshold=keyword_threshold)
        if result and result.confidence >= keyword_threshold:
            logger.info(f"  ✅ Найдено по ключевым словам! Confidence: {result.confidence}%")
            return result
    else:
        logger.debug(f"  Уровень 2: Пропущен (запрос длинный: {len(query_text.split())} слов > {keyword_max_words})")

    # УРОВЕНЬ 3: Semantic Search
    logger.debug("  Уровень 3: Семантический поиск...")
    result = find_semantic_match(query_text, collection, threshold=semantic_threshold)
    if result:
        logger.info(f"  ✅ Найдено семантическим поиском! Confidence: {result.confidence}%")
        return result

    # УРОВЕНЬ 4: Fallback
    logger.info("  ❌ Ответ не найден ни на одном уровне. Возвращаем fallback.")
    return get_fallback_result()
