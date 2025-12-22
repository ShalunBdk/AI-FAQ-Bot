# -*- coding: utf-8 -*-
"""
Модуль анонимизации персональных данных (PII) для Privacy First RAG

Реализует двухэтапную анонимизацию:
1. Regex: Email и Телефоны
2. NER (natasha): Имена (PER), Локации (LOC), Организации (ORG)

Поддерживает деанонимизацию ответов от LLM.
"""

import re
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class PiiAnonymizer:
    """
    Класс для анонимизации и деанонимизации персональных данных

    Privacy First подход: маскирование PII перед отправкой в облачную LLM
    """

    def __init__(self):
        """Инициализация анонимайзера с ленивой загрузкой natasha"""
        self.mapping: Dict[str, str] = {}  # {placeholder: real_value}
        self.reverse_mapping: Dict[str, str] = {}  # {real_value: placeholder} для дедупликации

        # Счетчики для каждого типа PII
        self.counters = {
            'EMAIL': 0,
            'PHONE': 0,
            'PER': 0,
            'LOC': 0,
            'ORG': 0,
            'URL': 0  # BB-код ссылки (часто содержат имена и профили)
        }

        # Natasha компоненты (ленивая инициализация)
        self._segmenter = None
        self._morph_vocab = None
        self._ner_tagger = None
        self._names_extractor = None

    def _init_natasha(self):
        """
        Ленивая инициализация natasha компонентов

        Импортируем только когда действительно нужно NER
        """
        if self._segmenter is not None:
            return  # Уже инициализировано

        try:
            from natasha import (
                Segmenter,
                MorphVocab,
                NewsNERTagger,
                NamesExtractor,
                Doc
            )
            from navec import Navec
            import os

            # Пытаемся загрузить предобученную модель navec
            logger.debug("Инициализация natasha NER...")

            # Путь для кэширования модели (используем правильную версию для NewsNERTagger)
            cache_dir = os.path.join(os.path.expanduser('~'), '.natasha_cache')
            navec_model_path = os.path.join(cache_dir, 'navec_news_v1_1B_250K_300d_100q.tar')

            # Проверяем есть ли закэшированная модель
            if os.path.exists(navec_model_path):
                logger.debug(f"Загрузка navec из кэша: {navec_model_path}")
                navec = Navec.load(navec_model_path)
            else:
                # Пытаемся скачать модель
                logger.debug("Скачивание navec модели (это может занять ~30 сек при первом запуске)...")
                os.makedirs(cache_dir, exist_ok=True)

                # Используем requests для скачивания (надежнее чем прямой load)
                # Правильная модель для NewsNERTagger
                import requests
                url = 'https://storage.yandexcloud.net/natasha-navec/packs/navec_news_v1_1B_250K_300d_100q.tar'

                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()

                with open(navec_model_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                logger.debug("Navec модель скачана успешно")
                navec = Navec.load(navec_model_path)

            self._segmenter = Segmenter()
            self._morph_vocab = MorphVocab()
            self._ner_tagger = NewsNERTagger(navec)
            self._names_extractor = NamesExtractor(self._morph_vocab)

            logger.info("✅ Natasha NER инициализирована успешно")

        except ImportError as e:
            logger.warning(f"natasha или navec не установлены: {e}. NER анонимизация отключена (используется только regex).")
            self._segmenter = False

        except Exception as e:
            logger.warning(f"Ошибка инициализации natasha: {e}. NER анонимизация отключена (используется только regex).")
            self._segmenter = False

    def _add_to_mapping(self, entity_type: str, real_value: str) -> str:
        """
        Добавить сущность в маппинг и вернуть placeholder

        Дедупликация: одинаковые значения получают одинаковый placeholder

        Args:
            entity_type: Тип сущности (EMAIL, PHONE, PER, LOC, ORG)
            real_value: Реальное значение

        Returns:
            Placeholder (например: [EMAIL_1])
        """
        # Проверяем дедупликацию
        if real_value in self.reverse_mapping:
            return self.reverse_mapping[real_value]

        # Создаем новый placeholder
        self.counters[entity_type] += 1
        placeholder = f"[{entity_type}_{self.counters[entity_type]}]"

        # Сохраняем в оба маппинга
        self.mapping[placeholder] = real_value
        self.reverse_mapping[real_value] = placeholder

        logger.debug(f"Анонимизация: {real_value} → {placeholder}")

        return placeholder

    def _anonymize_emails(self, text: str) -> str:
        """
        Анонимизация email адресов через regex

        Args:
            text: Исходный текст

        Returns:
            Текст с замененными email на [EMAIL_N]
        """
        # Regex для email (упрощенный, но покрывает большинство случаев)
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        def replace_email(match):
            email = match.group(0)
            return self._add_to_mapping('EMAIL', email)

        return re.sub(email_pattern, replace_email, text)

    def _anonymize_phones(self, text: str) -> str:
        """
        Анонимизация телефонных номеров через regex

        Поддерживаемые форматы:
        - +7 (999) 123-45-67
        - +79991234567
        - 8 (999) 123-45-67
        - 89991234567
        - 8-999-123-45-67

        Args:
            text: Исходный текст

        Returns:
            Текст с замененными телефонами на [PHONE_N]
        """
        # Regex для российских телефонов (различные форматы)
        phone_patterns = [
            # +7 (999) 123-45-67 или +7 999 123-45-67
            r'\+7\s*\(?\d{3}\)?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}',
            # 8 (999) 123-45-67 или 8 999 123-45-67
            r'8\s*\(?\d{3}\)?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}',
            # +79991234567 или 89991234567
            r'[+]?[78]\d{10}',
        ]

        result = text
        for pattern in phone_patterns:
            def replace_phone(match):
                phone = match.group(0)
                return self._add_to_mapping('PHONE', phone)

            result = re.sub(pattern, replace_phone, result)

        return result

    def _anonymize_bb_urls(self, text: str) -> str:
        """
        Анонимизация BB-код URL тегов (Bitrix24)

        Находит паттерны вида: [URL=...]текст[/URL]
        Заменяет на: [URL_N]

        Это защищает:
        - Ссылки на профили сотрудников
        - Имена в тексте ссылки
        - Внутренние URL компании

        Args:
            text: Исходный текст

        Returns:
            Текст с замененными BB URL на [URL_N]
        """
        # Regex для BB-кода URL: [URL=...]...[/URL]
        # Использует non-greedy match .*? чтобы не захватить несколько тегов сразу
        bb_url_pattern = r'\[URL=.*?\].*?\[/URL\]'

        def replace_bb_url(match):
            full_tag = match.group(0)
            return self._add_to_mapping('URL', full_tag)

        result = re.sub(bb_url_pattern, replace_bb_url, text, flags=re.IGNORECASE)

        return result

    def _anonymize_ner(self, text: str) -> str:
        """
        Анонимизация через NER (natasha)

        Находит:
        - PER: Имена людей
        - LOC: Географические объекты
        - ORG: Организации

        Args:
            text: Исходный текст

        Returns:
            Текст с замененными сущностями на [PER_N], [LOC_N], [ORG_N]
        """
        # Ленивая инициализация natasha
        self._init_natasha()

        # Проверяем что natasha доступна
        if self._segmenter is False or self._segmenter is None:
            logger.warning("NER анонимизация пропущена (natasha недоступна)")
            return text

        try:
            from natasha import Doc

            # Создаем документ
            doc = Doc(text)

            # Сегментация
            doc.segment(self._segmenter)

            # NER тегирование
            doc.tag_ner(self._ner_tagger)

            # Собираем все найденные сущности
            entities = []
            if doc.spans:
                for span in doc.spans:
                    entities.append({
                        'start': span.start,
                        'stop': span.stop,
                        'type': span.type,
                        'text': text[span.start:span.stop]
                    })

            # Сортируем по позиции (справа налево для корректной замены)
            entities.sort(key=lambda x: x['start'], reverse=True)

            # Заменяем сущности на placeholder'ы
            result = text
            for entity in entities:
                entity_type = entity['type']
                entity_text = entity['text']
                start = entity['start']
                stop = entity['stop']

                # Маппинг типов natasha на наши типы
                type_mapping = {
                    'PER': 'PER',
                    'LOC': 'LOC',
                    'ORG': 'ORG'
                }

                if entity_type in type_mapping:
                    our_type = type_mapping[entity_type]
                    placeholder = self._add_to_mapping(our_type, entity_text)

                    # Заменяем текст
                    result = result[:start] + placeholder + result[stop:]

            return result

        except Exception as e:
            logger.error(f"Ошибка NER анонимизации: {e}", exc_info=True)
            return text

    def anonymize(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Полная анонимизация текста

        Процесс:
        1. BB-код URL теги (regex) - защита ссылок и имен в [URL=...]...[/URL]
        2. Email (regex)
        3. Телефоны (regex)
        4. NER: ОТКЛЮЧЕН (дает много ложных срабатываний)

        Args:
            text: Исходный текст

        Returns:
            Tuple (anonymized_text, mapping)
            - anonymized_text: Текст с placeholder'ами
            - mapping: Словарь {placeholder: real_value}
        """
        if not text:
            return text, {}

        logger.debug(f"Начало анонимизации текста (длина: {len(text)} символов)")

        # Сбрасываем маппинг для нового запроса
        self.mapping = {}
        self.reverse_mapping = {}
        self.counters = {k: 0 for k in self.counters}

        # Шаг 1: BB-код URL теги (делаем первым, чтобы защитить имена в ссылках)
        result = self._anonymize_bb_urls(text)

        # Шаг 2: Email
        result = self._anonymize_emails(result)

        # Шаг 3: Телефоны
        result = self._anonymize_phones(result)

        # Шаг 4: NER ОТКЛЮЧЕН
        # Natasha дает много ложных срабатываний ("Бухгалтерии" -> [PER_1])
        # и пропускает реальные имена в BB-кодах ([URL]Иванов Иван[/URL])
        # Теперь имена защищены через BB URL анонимизацию (шаг 1)
        # result = self._anonymize_ner(result)  # ОТКЛЮЧЕНО

        logger.info(f"Анонимизация завершена. Найдено PII: "
                   f"URL={self.counters['URL']}, "
                   f"EMAIL={self.counters['EMAIL']}, "
                   f"PHONE={self.counters['PHONE']}")

        return result, self.mapping.copy()

    def deanonymize(self, text: str, mapping: Optional[Dict[str, str]] = None) -> str:
        """
        Деанонимизация текста (восстановление реальных данных)

        Args:
            text: Текст с placeholder'ами
            mapping: Словарь {placeholder: real_value} (опционально, если не указан - использует self.mapping)

        Returns:
            Текст с восстановленными реальными значениями
        """
        if not text:
            return text

        # Используем переданный маппинг или сохраненный
        mapping_to_use = mapping if mapping is not None else self.mapping

        if not mapping_to_use:
            logger.warning("Попытка деанонимизации без маппинга")
            return text

        logger.debug(f"Начало деанонимизации текста (placeholder'ов: {len(mapping_to_use)})")

        result = text

        # Заменяем каждый placeholder на реальное значение
        # Сортируем по длине ключа (длинные первыми) чтобы избежать частичных замен
        sorted_placeholders = sorted(mapping_to_use.keys(), key=len, reverse=True)

        for placeholder in sorted_placeholders:
            real_value = mapping_to_use[placeholder]
            result = result.replace(placeholder, real_value)

        logger.debug("Деанонимизация завершена")

        return result


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def anonymize_text(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Удобная функция для одноразовой анонимизации

    Args:
        text: Исходный текст

    Returns:
        Tuple (anonymized_text, mapping)
    """
    anonymizer = PiiAnonymizer()
    return anonymizer.anonymize(text)


def deanonymize_text(text: str, mapping: Dict[str, str]) -> str:
    """
    Удобная функция для одноразовой деанонимизации

    Args:
        text: Текст с placeholder'ами
        mapping: Словарь {placeholder: real_value}

    Returns:
        Деанонимизированный текст
    """
    anonymizer = PiiAnonymizer()
    return anonymizer.deanonymize(text, mapping)
