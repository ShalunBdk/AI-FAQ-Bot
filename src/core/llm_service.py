# -*- coding: utf-8 -*-
"""
Модуль RAG (Retrieval-Augmented Generation) с Privacy First подходом

Реализует:
- Анонимизацию персональных данных перед отправкой в LLM
- Генерацию ответов через OpenRouter API
- Деанонимизацию ответов
"""

import logging
import os
import time
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from datetime import datetime

from src.core.pii_anonymizer import PiiAnonymizer

logger = logging.getLogger(__name__)


class LLMService:
    """
    Сервис для генерации ответов через LLM с Privacy First подходом

    Использует OpenRouter API для доступа к различным LLM моделям
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1"
    ):
        """
        Инициализация LLM сервиса

        Args:
            api_key: OpenRouter API ключ (если None - берется из OPENROUTER_API_KEY)
            model: Название модели (если None - берется из OPENROUTER_MODEL или используется дефолт)
            base_url: Base URL для OpenRouter API
        """
        # API ключ
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY не установлен!")
            raise ValueError("OPENROUTER_API_KEY обязателен для работы LLM сервиса")

        # Модель
        self.model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        logger.info(f"Используется LLM модель: {self.model}")

        # Retry параметры (настраиваемые через env)
        self.max_retries = int(os.getenv("OPENROUTER_MAX_RETRIES", "3"))
        self.retry_delay = int(os.getenv("OPENROUTER_RETRY_DELAY", "2"))
        logger.debug(f"Retry настройки: {self.max_retries} попыток, начальная задержка {self.retry_delay}с")

        # Инициализируем OpenAI клиент (совместим с OpenRouter)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=base_url
        )

        # Анонимайзер
        self.anonymizer = PiiAnonymizer()

        # Кэш системного промпта (загружается при старте и обновляется через reload_prompt)
        self._system_prompt_cache = None
        self.reload_prompt()

    def reload_prompt(self):
        """
        Перезагрузить системный промпт из БД в кэш

        Вызывается при старте и при обновлении настроек через админку
        """
        from src.core.database import get_bot_setting, DEFAULT_BOT_SETTINGS

        # Загружаем отделы и промпт из настроек
        departments_info = get_bot_setting("rag_departments_info") or DEFAULT_BOT_SETTINGS.get("rag_departments_info", "")
        system_prompt_template = get_bot_setting("rag_system_prompt") or DEFAULT_BOT_SETTINGS.get("rag_system_prompt", "")

        # Подставляем отделы в промпт
        self._system_prompt_cache = system_prompt_template.replace("{DEPARTMENTS_INFO}", departments_info)

        logger.info("✅ Системный промпт RAG загружен из настроек")

    def _get_system_prompt(self) -> str:
        """Получить системный промпт из кэша"""
        if self._system_prompt_cache is None:
            self.reload_prompt()
        return self._system_prompt_cache

    def _prepare_context(self, chunks: List[Dict]) -> str:
        """
        Подготовка контекста из найденных чанков

        Args:
            chunks: Список словарей с полями: question, answer, confidence

        Returns:
            Объединенный контекст для LLM
        """
        if not chunks:
            return ""

        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            question = chunk.get('question', '')
            answer = chunk.get('answer', '')
            confidence = chunk.get('confidence', 0)

            # Форматируем каждый чанк
            context_parts.append(
                f"Документ {i} (релевантность: {confidence:.1f}%):\n"
                f"Вопрос: {question}\n"
                f"Ответ: {answer}\n"
            )

        context = "\n---\n".join(context_parts)

        logger.debug(f"Подготовлен контекст из {len(chunks)} чанков (длина: {len(context)} символов)")

        return context

    def generate_answer(
        self,
        user_question: str,
        db_chunks: List[Dict],
        max_tokens: int = 1024,
        temperature: float = 0.3
    ) -> Tuple[str, Dict[str, any]]:
        """
        Генерация ответа через LLM с анонимизацией PII

        Процесс:
        1. Подготовка контекста из чанков
        2. Анонимизация контекста и вопроса
        3. Запрос к LLM
        4. Деанонимизация ответа

        Args:
            user_question: Вопрос пользователя
            db_chunks: Список найденных контекстов из ChromaDB
                      Формат: [{"question": "...", "answer": "...", "confidence": 85.5}, ...]
            max_tokens: Максимальное количество токенов в ответе
            temperature: Температура генерации (0.0 - детерминированный, 1.0 - креативный)

        Returns:
            Tuple (answer, metadata)
            - answer: Сгенерированный ответ (деанонимизированный)
            - metadata: Метаданные генерации (модель, токены, анонимизация и т.д.)
        """
        try:
            logger.info(f"🤖 RAG генерация ответа для вопроса: '{user_question}'")
            logger.debug(f"Получено {len(db_chunks)} чанков из базы данных")
            now = datetime.now()
            days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            current_date_str = f"{now.strftime('%d.%m.%Y')} ({days[now.weekday()]})"

            # Загружаем системный промпт из настроек (hot reload)
            system_prompt = self._get_system_prompt()

            # Собираем финальный промпт с датой
            full_system_prompt = f"СЕГОДНЯШНЯЯ ДАТА: {current_date_str}\n\n{system_prompt}"

            # Шаг 1: Подготовка контекста
            context = self._prepare_context(db_chunks)

            if not context:
                logger.warning("Контекст пуст! Возвращаем fallback ответ.")
                return (
                    "К сожалению, я не нашел информации по этому вопросу в базе знаний.",
                    {"error": "empty_context"}
                )

            # Шаг 2: Анонимизация контекста
            logger.debug("Анонимизация контекста...")
            anonymized_context, context_mapping = self.anonymizer.anonymize(context)

            # Шаг 3: Анонимизация вопроса
            logger.debug("Анонимизация вопроса...")
            anonymized_question, question_mapping = self.anonymizer.anonymize(user_question)

            # Объединяем маппинги
            combined_mapping = {**context_mapping, **question_mapping}

            logger.info(f"Анонимизация завершена. Найдено PII: {len(combined_mapping)} сущностей")

            # Шаг 4: Формируем запрос к LLM
            messages = [
                {"role": "system", "content": full_system_prompt}, 
                {"role": "user", "content": f"КОНТЕКСТ:\n{anonymized_context}\n\nВОПРОС: {anonymized_question}"}
            ]

            logger.debug(f"Запрос к LLM модели: {self.model}")

            # Шаг 5: Запрос к OpenRouter с retry механизмом
            retry_delay = self.retry_delay  # начальная задержка

            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.debug(f"Попытка {attempt}/{self.max_retries} подключения к OpenRouter...")

                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )

                    logger.debug(f"✅ Успешное подключение на попытке {attempt}")
                    break  # Успех, выходим из цикла

                except Exception as e:
                    error_msg = str(e)

                    if attempt < self.max_retries:
                        logger.warning(
                            f"⚠️ Попытка {attempt}/{self.max_retries} не удалась: {error_msg}. "
                            f"Повтор через {retry_delay} секунд..."
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff: 2s, 4s, 8s, ...
                    else:
                        logger.error(f"❌ Все {self.max_retries} попытки подключения к OpenRouter не удались")
                        raise  # Пробрасываем исключение после всех попыток

            # Получаем ответ
            anonymized_answer = response.choices[0].message.content

            logger.debug(f"Получен ответ от LLM (длина: {len(anonymized_answer)} символов)")

            # Шаг 6: Деанонимизация ответа
            logger.debug("Деанонимизация ответа...")
            final_answer = self.anonymizer.deanonymize(anonymized_answer, combined_mapping)

            # Метаданные
            metadata = {
                "model": self.model,
                "chunks_used": len(db_chunks),
                "pii_found": len(combined_mapping),
                "tokens_used": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                },
                "finish_reason": response.choices[0].finish_reason
            }

            logger.info(f"✅ RAG генерация успешна. Токенов: {metadata['tokens_used']['total']}, PII: {metadata['pii_found']}")

            return final_answer, metadata

        except Exception as e:
            logger.error(f"Ошибка RAG генерации: {e}", exc_info=True)
            return (
                "😔 Извините, произошла ошибка при генерации ответа. Попробуйте позже.",
                {"error": str(e)}
            )


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def generate_rag_answer(
    user_question: str,
    db_chunks: List[Dict],
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> Tuple[str, Dict[str, any]]:
    """
    Удобная функция для одноразовой генерации RAG ответа

    Args:
        user_question: Вопрос пользователя
        db_chunks: Список найденных контекстов
        api_key: OpenRouter API ключ (опционально)
        model: Модель для использования (опционально)

    Returns:
        Tuple (answer, metadata)
    """
    service = LLMService(api_key=api_key, model=model)
    return service.generate_answer(user_question, db_chunks)
