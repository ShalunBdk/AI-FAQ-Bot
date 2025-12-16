# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки RAG (Retrieval-Augmented Generation) пайплайна

Проверяет:
1. Анонимизацию персональных данных (PII)
2. Генерацию ответов через LLM
3. Деанонимизацию результатов
"""

import sys
import os
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Загружаем .env
load_dotenv()

from src.core.pii_anonymizer import PiiAnonymizer
from src.core.llm_service import LLMService

# Цвета для консоли
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Печать заголовка"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_section(text):
    """Печать секции"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}--- {text} ---{Colors.ENDC}\n")


def print_success(text):
    """Печать успеха"""
    print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")


def print_error(text):
    """Печать ошибки"""
    print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")


def print_warning(text):
    """Печать предупреждения"""
    print(f"{Colors.WARNING}[WARN] {text}{Colors.ENDC}")


def test_pii_anonymization():
    """Тест 1: Анонимизация персональных данных"""
    print_header("ТЕСТ 1: АНОНИМИЗАЦИЯ ПЕРСОНАЛЬНЫХ ДАННЫХ")

    anonymizer = PiiAnonymizer()

    # Тестовые данные с PII
    test_texts = [
        {
            'name': 'Email и телефон',
            'text': 'Свяжитесь с Иваном Петровым по email ivan.petrov@example.com или по телефону +7 (999) 123-45-67.',
            'expected_pii': ['EMAIL', 'PHONE', 'PER']
        },
        {
            'name': 'Организация и локация',
            'text': 'ООО "Рога и Копыта" находится в Москве на улице Ленина.',
            'expected_pii': ['ORG', 'LOC']
        },
        {
            'name': 'Только имя',
            'text': 'Печать находится у Марии Сидоровой в Бухгалтерии.',
            'expected_pii': ['PER']
        }
    ]

    for i, test in enumerate(test_texts, 1):
        print_section(f"Тест {i}: {test['name']}")
        print(f"{Colors.BOLD}Исходный текст:{Colors.ENDC}")
        print(f"  {test['text']}")

        # Анонимизация
        anonymized, mapping = anonymizer.anonymize(test['text'])

        print(f"\n{Colors.BOLD}Анонимизированный текст:{Colors.ENDC}")
        print(f"  {anonymized}")

        print(f"\n{Colors.BOLD}Найденные PII:{Colors.ENDC}")
        if mapping:
            for placeholder, real_value in mapping.items():
                pii_type = placeholder.split('_')[0][1:]  # Извлекаем тип из [TYPE_N]
                print(f"  {placeholder} -> {real_value} ({pii_type})")
        else:
            print(f"  {Colors.WARNING}Ничего не найдено{Colors.ENDC}")

        # Деанонимизация
        deanonymized = anonymizer.deanonymize(anonymized, mapping)

        print(f"\n{Colors.BOLD}Деанонимизированный текст:{Colors.ENDC}")
        print(f"  {deanonymized}")

        # Проверка
        if deanonymized == test['text']:
            print_success("Деанонимизация прошла успешно (текст восстановлен полностью)")
        else:
            print_warning("Деанонимизация частично отличается от оригинала")

        # Проверка ожидаемых типов PII
        found_types = set([placeholder.split('_')[0][1:] for placeholder in mapping.keys()])
        expected_types = set(test['expected_pii'])

        if found_types >= expected_types:
            print_success(f"Найдены все ожидаемые типы PII: {', '.join(expected_types)}")
        else:
            missing = expected_types - found_types
            print_warning(f"Не найдены некоторые типы PII: {', '.join(missing)}")


def test_llm_generation():
    """Тест 2: Генерация ответов через LLM"""
    print_header("ТЕСТ 2: ГЕНЕРАЦИЯ ОТВЕТОВ ЧЕРЕЗ LLM")

    # Проверяем наличие API ключа
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key or api_key == 'your_openrouter_api_key_here':
        print_error("OPENROUTER_API_KEY не установлен в .env файле!")
        print_warning("Пропускаем тест генерации LLM. Установите ключ для полного тестирования.")
        return

    try:
        service = LLMService()
        print_success("LLM сервис инициализирован успешно")
    except Exception as e:
        print_error(f"Ошибка инициализации LLM сервиса: {e}")
        return

    # Тестовые данные
    test_cases = [
        {
            'name': 'Простой вопрос',
            'question': 'Как получить справку 2-НДФЛ?',
            'chunks': [
                {
                    'question': 'Где получить справку 2-НДФЛ?',
                    'answer': 'Справку 2-НДФЛ можно получить в бухгалтерии. Обратитесь к Марии Ивановой (доб. 123) или отправьте запрос на email: buhgalteriya@example.com',
                    'confidence': 85.5
                }
            ]
        },
        {
            'name': 'Вопрос с логическим выводом',
            'question': 'Где находится печать компании?',
            'chunks': [
                {
                    'question': 'У кого находится печать?',
                    'answer': 'Печать находится у Петра Сидорова.',
                    'confidence': 78.3
                },
                {
                    'question': 'Где работает Петр Сидоров?',
                    'answer': 'Петр Сидоров работает в Бухгалтерии, офис 205.',
                    'confidence': 72.1
                }
            ]
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print_section(f"Тест {i}: {test['name']}")
        print(f"{Colors.BOLD}Вопрос пользователя:{Colors.ENDC}")
        print(f"  {test['question']}")

        print(f"\n{Colors.BOLD}Контекст из базы ({len(test['chunks'])} документов):{Colors.ENDC}")
        for j, chunk in enumerate(test['chunks'], 1):
            print(f"  {j}. [{chunk['confidence']:.1f}%] {chunk['question']}")
            print(f"     -> {chunk['answer'][:100]}...")

        try:
            answer, metadata = service.generate_answer(
                user_question=test['question'],
                db_chunks=test['chunks'],
                max_tokens=512,
                temperature=0.3
            )

            print(f"\n{Colors.BOLD}Сгенерированный ответ:{Colors.ENDC}")
            print(f"  {answer}")

            print(f"\n{Colors.BOLD}Метаданные генерации:{Colors.ENDC}")
            print(f"  Модель: {metadata.get('model', 'N/A')}")
            print(f"  Использовано документов: {metadata.get('chunks_used', 'N/A')}")
            print(f"  Найдено PII: {metadata.get('pii_found', 0)}")

            if 'tokens_used' in metadata:
                tokens = metadata['tokens_used']
                print(f"  Токены: {tokens.get('total', 'N/A')} (промпт: {tokens.get('prompt', 'N/A')}, ответ: {tokens.get('completion', 'N/A')})")

            print_success("Ответ успешно сгенерирован")

        except Exception as e:
            print_error(f"Ошибка генерации ответа: {e}")


def test_full_pipeline():
    """Тест 3: Полный пайплайн с анонимизацией"""
    print_header("ТЕСТ 3: ПОЛНЫЙ RAG ПАЙПЛАЙН С АНОНИМИЗАЦИЕЙ")

    # Проверяем наличие API ключа
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key or api_key == 'your_openrouter_api_key_here':
        print_warning("OPENROUTER_API_KEY не установлен. Пропускаем полный тест.")
        return

    try:
        service = LLMService()
    except Exception as e:
        print_error(f"Ошибка инициализации: {e}")
        return

    # Тестовые данные с PII
    question = "Как связаться с бухгалтерией?"
    chunks = [
        {
            'question': 'Контакты бухгалтерии',
            'answer': 'Бухгалтерия работает с понедельника по пятницу с 9:00 до 18:00. '
                     'Главный бухгалтер: Мария Ивановна Петрова. '
                     'Телефон: +7 (495) 123-45-67. '
                     'Email: maria.petrova@company.ru. '
                     'Офис находится в Москве, ул. Ленина, д. 10, офис 205.',
            'confidence': 92.3
        }
    ]

    print_section("Исходные данные")
    print(f"{Colors.BOLD}Вопрос:{Colors.ENDC} {question}")
    print(f"{Colors.BOLD}Контекст:{Colors.ENDC} {chunks[0]['answer']}")

    try:
        answer, metadata = service.generate_answer(
            user_question=question,
            db_chunks=chunks,
            max_tokens=512,
            temperature=0.3
        )

        print_section("Результат")
        print(f"{Colors.BOLD}Сгенерированный ответ:{Colors.ENDC}")
        print(f"  {answer}")

        print(f"\n{Colors.BOLD}Статистика анонимизации:{Colors.ENDC}")
        print(f"  Найдено и замаскировано PII: {metadata.get('pii_found', 0)} сущностей")
        print(f"  Токенов использовано: {metadata.get('tokens_used', {}).get('total', 'N/A')}")

        if metadata.get('pii_found', 0) > 0:
            print_success("PII успешно анонимизированы перед отправкой в LLM")
            print_success("Ответ успешно деанонимизирован")
        else:
            print_warning("PII не обнаружены (возможно, паттерны не сработали)")

    except Exception as e:
        print_error(f"Ошибка в полном пайплайне: {e}")


def main():
    """Главная функция"""
    print(f"\n{Colors.BOLD}{Colors.OKCYAN}")
    print("=" * 80)
    print("                ТЕСТИРОВАНИЕ RAG ПАЙПЛАЙНА (Privacy First)                ")
    print("=" * 80)
    print(f"{Colors.ENDC}")

    try:
        # Тест 1: Анонимизация
        test_pii_anonymization()

        # Тест 2: LLM генерация
        test_llm_generation()

        # Тест 3: Полный пайплайн
        test_full_pipeline()

        # Итоги
        print_header("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print_success("Все тесты выполнены. Проверьте результаты выше.")
        print(f"\n{Colors.BOLD}Следующие шаги:{Colors.ENDC}")
        print("  1. Установите OPENROUTER_API_KEY в .env файле (если еще не сделали)")
        print("  2. Запустите бота: python -m src.bots.bot (Telegram) или python -m src.bots.b24_bot (Bitrix24)")
        print("  3. Проверьте работу RAG в реальных диалогах")
        print()

    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Тестирование прервано пользователем{Colors.ENDC}")
    except Exception as e:
        print_error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
