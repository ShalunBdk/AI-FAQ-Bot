"""
FAQ Бот для Bitrix24
Использует ChromaDB для семантического поиска ответов
"""

import logging
import os
import sys
import json
import time
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import chromadb
from chromadb.utils import embedding_functions

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core import database
from src.core import logging_config
from src.api.b24_api import Bitrix24API, Bitrix24Event
from src.core.search import find_answer, SearchResult
from src.core.llm_service import LLMService

# Загрузка конфигурации
load_dotenv()
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Настройка логирования (DEBUG для детальной диагностики)
logging_config.configure_root_logger(level=logging.DEBUG)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ ==========

BITRIX24_WEBHOOK = os.getenv("BITRIX24_WEBHOOK")
BITRIX24_BOT_ID = os.getenv("BITRIX24_BOT_ID")  # Числовой BOT_ID для регистрации команд
BITRIX24_BOT_CLIENT_ID = os.getenv("BITRIX24_BOT_CLIENT_ID")  # Строковый CLIENT_ID бота для API запросов
BITRIX24_HANDLER_URL = os.getenv("BITRIX24_HANDLER_URL", "https://your-server.com/webhook/bitrix24")

# Поддержка BASE_PATH для reverse proxy (например, /faqbot)
BASE_PATH = os.getenv("BASE_PATH", "").rstrip('/')
if BASE_PATH and BITRIX24_HANDLER_URL:
    # Если HANDLER_URL уже содержит BASE_PATH - не дублируем
    if BASE_PATH not in BITRIX24_HANDLER_URL:
        # Вставляем BASE_PATH между доменом и путём
        # Например: https://domain.com/webhook/bitrix24 → https://domain.com/faqbot/webhook/bitrix24
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(BITRIX24_HANDLER_URL)
        new_path = f"{BASE_PATH}{parsed.path}"
        BITRIX24_HANDLER_URL = urlunparse((
            parsed.scheme, parsed.netloc, new_path,
            parsed.params, parsed.query, parsed.fragment
        ))
        logger.info(f"🔧 BASE_PATH применён к HANDLER_URL: {BITRIX24_HANDLER_URL}")

MODEL_NAME = os.getenv("MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "45.0"))

if not BITRIX24_WEBHOOK:
    logger.warning("⚠️ BITRIX24_WEBHOOK не настроен в .env")

# ========== ИНИЦИАЛИЗАЦИЯ ==========

# ChromaDB
CHROMA_PATH = os.getenv('CHROMA_PATH', './data/chroma_db')
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=MODEL_NAME
)
collection = None  # Загрузится при старте

# Bitrix24 API
b24_api = None  # Инициализируется при получении webhook

# Кэш настроек бота
bot_settings_cache = {}

# RAG настройки
RAG_ENABLED = os.getenv('RAG_ENABLED', 'true').lower() == 'true'
RAG_MAX_TOKENS = int(os.getenv('RAG_MAX_TOKENS', '1024'))
RAG_TEMPERATURE = float(os.getenv('RAG_TEMPERATURE', '0.3'))
RAG_MIN_RELEVANCE_SCORE = float(os.getenv('RAG_MIN_RELEVANCE_SCORE', '45.0'))
RAG_MAX_CHUNKS = int(os.getenv('RAG_MAX_CHUNKS', '5'))

# LLM сервис (инициализируется при первом использовании)
llm_service = None

def get_llm_service():
    """Ленивая инициализация LLM сервиса"""
    global llm_service
    if llm_service is None and RAG_ENABLED:
        try:
            llm_service = LLMService()
            logger.info("✅ LLM сервис инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации LLM сервиса: {e}")
            # Не падаем, просто отключаем RAG
            return None
    return llm_service

# Flask app для приема вебхуков
app = Flask(__name__)


# ========== ФУНКЦИИ КОНВЕРТАЦИИ ФОРМАТИРОВАНИЯ ==========

def convert_html_to_bbcode(html: str) -> str:
    """
    Конвертирует HTML (Telegram формат) в BB коды Битрикс24

    Поддерживаемые преобразования:
    - <b>, <strong> → [b]...[/b]
    - <i>, <em> → [i]...[/i]
    - <u> → [u]...[/u]
    - <s>, <strike>, <del> → [s]...[/s]
    - <code> → [code]...[/code]
    - <pre> → [code]...[/code]
    - <a href="url">text</a> → [URL=url]text[/URL]
    - Переносы строк сохраняются

    Args:
        html: HTML текст в Telegram формате

    Returns:
        Текст в BB кодах
    """
    import re

    if not html:
        return ""

    text = html

    # Жирный текст
    text = re.sub(r'<b>(.*?)</b>', r'[b]\1[/b]', text, flags=re.DOTALL)
    text = re.sub(r'<strong>(.*?)</strong>', r'[b]\1[/b]', text, flags=re.DOTALL)

    # Курсив
    text = re.sub(r'<i>(.*?)</i>', r'[i]\1[/i]', text, flags=re.DOTALL)
    text = re.sub(r'<em>(.*?)</em>', r'[i]\1[/i]', text, flags=re.DOTALL)

    # Подчёркнутый
    text = re.sub(r'<u>(.*?)</u>', r'[u]\1[/u]', text, flags=re.DOTALL)

    # Зачёркнутый
    text = re.sub(r'<s>(.*?)</s>', r'[s]\1[/s]', text, flags=re.DOTALL)
    text = re.sub(r'<strike>(.*?)</strike>', r'[s]\1[/s]', text, flags=re.DOTALL)
    text = re.sub(r'<del>(.*?)</del>', r'[s]\1[/s]', text, flags=re.DOTALL)

    # Код
    text = re.sub(r'<code>(.*?)</code>', r'[code]\1[/code]', text, flags=re.DOTALL)
    text = re.sub(r'<pre>(.*?)</pre>', r'[code]\1[/code]', text, flags=re.DOTALL)
    text = re.sub(r'<pre[^>]*>(.*?)</pre>', r'[code]\1[/code]', text, flags=re.DOTALL)

    # Ссылки
    text = re.sub(r'<a\s+href=["\']([^"\']+)["\']>(.*?)</a>', r'[URL=\1]\2[/URL]', text, flags=re.DOTALL)

    # Убираем оставшиеся HTML теги (например, <p>, <div>, <br>)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p>', '', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<div>', '', text)
    text = re.sub(r'</div>', '\n', text)

    # Очистка множественных переносов строк
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text


# ========== ФУНКЦИИ ПОИСКА ==========

def find_best_match(query_text: str, n_results: int = 3) -> Tuple[Optional[Dict], float, Dict]:
    """
    Поиск наиболее подходящего ответа в ChromaDB

    Args:
        query_text: Текст вопроса пользователя
        n_results: Количество результатов для возврата

    Returns:
        (best_match_metadata, similarity_percent, all_results)
    """
    global collection

    if collection is None:
        logger.error("ChromaDB collection не инициализирована")
        return None, 0.0, {}

    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        if not results or not results['ids'] or not results['ids'][0]:
            logger.info("Ничего не найдено в ChromaDB")
            return None, 0.0, {}

        # Конвертируем distance в similarity (0-100%)
        best_distance = results['distances'][0][0]
        similarity = max(0.0, 1.0 - best_distance) * 100.0
        best_metadata = results['metadatas'][0][0]

        logger.info(f"Найдено результатов: {len(results['documents'][0])}, лучший score: {similarity:.1f}%")

        return best_metadata, similarity, results

    except Exception as e:
        logger.error(f"Ошибка поиска в ChromaDB: {e}", exc_info=True)
        return None, 0.0, {}


def init_chromadb():
    """Инициализация ChromaDB из существующих FAQ"""
    global collection

    try:
        collection = chroma_client.get_collection(
            name="faq_collection",
            embedding_function=embedding_func
        )
        logger.info(f"✅ ChromaDB загружена: {collection.count()} записей")
    except Exception as e:
        logger.warning(f"ChromaDB коллекция не найдена, создаем новую: {e}")
        # Создадим коллекцию если её нет
        try:
            collection = chroma_client.create_collection(
                name="faq_collection",
                embedding_function=embedding_func
            )
            logger.info("✅ Создана новая ChromaDB коллекция")

            # Попробуем загрузить данные из БД
            init_demo_data()
        except Exception as create_error:
            logger.error(f"❌ Ошибка создания коллекции: {create_error}")


def init_demo_data():
    """Инициализация данных в ChromaDB из БД (если пусто)"""
    try:
        if collection.count() > 0:
            logger.info(f"В ChromaDB уже есть {collection.count()} записей")
            return

        logger.info("Добавление данных из БД в ChromaDB...")

        all_faqs = database.get_all_faqs()

        if not all_faqs:
            logger.warning("⚠️ В базе данных нет FAQ. Запустите migrate_data.py для миграции данных.")
            return

        documents, metadatas, ids = [], [], []

        for faq in all_faqs:
            text = f"{faq['question']} {' '.join(faq.get('keywords', []))}"
            documents.append(f"search_document: {text}")
            metadatas.append({
                "id": faq["id"],
                "category": faq["category"],
                "question": faq["question"],
                "answer": faq["answer"]
            })
            ids.append(faq["id"])

        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        logger.info(f"✅ Добавлено {len(all_faqs)} записей в ChromaDB")

    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации данных: {e}", exc_info=True)


def reload_chromadb():
    """Перезагрузка ChromaDB (для горячего обновления)"""
    global collection
    try:
        collection = chroma_client.get_collection(
            name="faq_collection",
            embedding_function=embedding_func
        )
        logger.info(f"🔄 ChromaDB перезагружена: {collection.count()} записей")
        return True
    except Exception as e:
        logger.error(f"Ошибка перезагрузки ChromaDB: {e}")
        return False


def reload_bot_settings():
    """Перезагружает настройки бота из БД"""
    global bot_settings_cache
    try:
        bot_settings_cache = database.get_bot_settings()
        logger.info(f"✅ Настройки бота загружены: {len(bot_settings_cache)} параметров")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке настроек бота: {e}")
        # Используем дефолтные настройки в случае ошибки
        bot_settings_cache = database.DEFAULT_BOT_SETTINGS.copy()
        return False


def register_bot_commands(api: Bitrix24API):
    """Регистрация команд для кнопок"""
    try:
        if not BITRIX24_HANDLER_URL or BITRIX24_HANDLER_URL == "https://your-server.com/webhook/bitrix24":
            logger.warning("⚠️ BITRIX24_HANDLER_URL не настроен в .env - команды не будут зарегистрированы")
            logger.warning("⚠️ Добавьте BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24 в .env")
            logger.warning("⚠️ Или запустите: python register_bot.py для регистрации бота")
            return

        # Регистрируем команды для обратной связи и похожих вопросов
        # Используем шаблоны без ID - Bitrix24 будет принимать любые суффиксы
        commands = [
            ('helpful_yes', 'Полезно'),
            ('helpful_no', 'Не помогло'),
            ('cat', 'Выбор категории'),
            ('similar_question', 'Похожий вопрос'),
            ('disambig', 'Уточнение вопроса'),
        ]

        for command, title in commands:
            result = api.register_command(command, title, BITRIX24_HANDLER_URL, hidden=True)
            if result.get('success') == False:
                error_msg = result.get('error', '')
                if 'Bot not found' in error_msg or 'BOT_ID_ERROR' in error_msg:
                    logger.error(f"❌ Бот не зарегистрирован в Bitrix24!")
                    logger.error(f"❌ Запустите: python register_bot.py для регистрации бота")
                    return  # Прерываем попытки регистрации команд
                else:
                    logger.warning(f"⚠️ Не удалось зарегистрировать команду '{command}': {error_msg}")
            elif 'result' in result:
                logger.info(f"✅ Команда '{command}' зарегистрирована")

    except Exception as e:
        logger.error(f"❌ Ошибка регистрации команд: {e}", exc_info=True)


# ========== ОБРАБОТЧИКИ КОМАНД ==========

def handle_new_user_welcome(event: Bitrix24Event, api: Bitrix24API):
    """
    Отправка приветственного сообщения новому пользователю Bitrix24

    Вызывается при событии ONUSERADD (добавление нового сотрудника)
    """
    # Проверяем, включена ли функция приветствия
    welcome_enabled = bot_settings_cache.get("new_user_welcome_enabled", "false") == "true"
    if not welcome_enabled:
        logger.debug(f"⏭️ Приветствие новых пользователей отключено в настройках")
        return

    new_user_id = event.new_user_id
    new_user_name = event.new_user_name

    if not new_user_id:
        logger.warning(f"⚠️ Не удалось получить ID нового пользователя из события ONUSERADD")
        return

    # Проверяем, что пользователь активен
    if not event.new_user_active:
        logger.debug(f"⏭️ Пользователь {new_user_id} не активен, пропускаем приветствие")
        return

    logger.info(f"👋 Новый пользователь: {new_user_name} (ID: {new_user_id})")

    # Получаем текст приветствия из настроек
    welcome_message = bot_settings_cache.get(
        "new_user_welcome_message",
        database.DEFAULT_BOT_SETTINGS.get("new_user_welcome_message", "Добро пожаловать!")
    )

    # Логируем отправку приветствия
    query_log_id = database.add_query_log(
        user_id=new_user_id,
        username=new_user_name,
        query_text="[Автоматическое приветствие нового пользователя]",
        platform='bitrix24_welcome'
    )

    try:
        # Отправляем сообщение новому пользователю
        result = api.send_message_to_user(new_user_id, welcome_message)

        if result.get('result'):
            logger.info(f"✅ Приветствие отправлено новому пользователю {new_user_name} (ID: {new_user_id})")

            # Логируем успешную отправку
            database.add_answer_log(
                query_log_id=query_log_id,
                faq_id=None,
                similarity_score=100.0,
                answer_shown=welcome_message,
                search_level='direct'
            )
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ Ошибка отправки приветствия пользователю {new_user_id}: {error_msg}")

            # Логируем ошибку
            database.add_answer_log(
                query_log_id=query_log_id,
                faq_id=None,
                similarity_score=0.0,
                answer_shown=f"Ошибка отправки: {error_msg}",
                search_level='none'
            )

    except Exception as e:
        logger.error(f"❌ Исключение при отправке приветствия: {e}", exc_info=True)


def handle_start(event: Bitrix24Event, api: Bitrix24API):
    """Обработка команды /start или /помощь"""
    logger.info(f"📩 Обработка команды /start от пользователя ID: {event.user_id}, Dialog ID: {event.dialog_id}")

    # Получаем текст приветствия из настроек
    message = bot_settings_cache.get("start_message", database.DEFAULT_BOT_SETTINGS["start_message"])

    logger.debug(f"📤 Отправка приветственного сообщения. Dialog ID: {event.dialog_id}, длина текста: {len(message)} символов")
    result = api.send_message(event.dialog_id, convert_html_to_bbcode(message))

    if result.get('success') == False:
        logger.error(f"❌ Ошибка отправки приветствия: {result.get('error')}")
    elif 'result' in result:
        logger.info(f"✅ Приветствие успешно отправлено пользователю {event.user_id}, Message ID: {result.get('result')}")
    else:
        logger.warning(f"⚠️ Неизвестный ответ от Bitrix24 API: {result}")


def handle_categories(event: Bitrix24Event, api: Bitrix24API):
    """Показать список категорий"""
    categories = database.get_all_categories()

    if not categories:
        api.send_message(event.dialog_id, "❌ Категории не найдены")
        return

    # Создаем кнопки для категорий (максимум 2 в ряд)
    buttons = []
    current_row = []

    for i, category in enumerate(categories):
        current_row.append({
            'text': f"📂 {category}",
            'action': 'cat',
            'params': category
        })

        # Каждые 2 кнопки - новый ряд
        if len(current_row) == 2 or i == len(categories) - 1:
            buttons.append(current_row)
            current_row = []

    keyboard = api.create_keyboard(buttons)

    api.send_message(
        event.dialog_id,
        "📂 Выберите категорию:",
        keyboard=keyboard
    )
    logger.info(f"Отправлены категории пользователю {event.user_id}")


def handle_category_select(event: Bitrix24Event, api: Bitrix24API, category: str):
    """Показать FAQ из выбранной категории"""
    faqs = database.get_faqs_by_category(category)

    if not faqs:
        api.send_message(event.dialog_id, f"❌ В категории '{category}' нет вопросов")
        return

    # Формируем список вопросов как вложения
    attach_items = [{'type': 'message', 'text': f'📂 Категория: {category}'}]

    for i, faq in enumerate(faqs[:10]):  # Максимум 10 вопросов
        attach_items.append({
            'type': 'link',
            'name': faq['question'],
            'url': '#'
        })
        if i < len(faqs[:10]) - 1:  # Разделитель между вопросами
            attach_items.append({'type': 'delimiter'})

    attach = api.create_attach(attach_items)

    message = f"Найдено вопросов: {len(faqs)}"
    if len(faqs) > 10:
        message += f"\nПоказаны первые 10 из {len(faqs)}"

    api.send_message(
        event.dialog_id,
        message,
        attach=attach
    )
    logger.info(f"Отправлена категория '{category}' пользователю {event.user_id}")


def is_rag_clarification(answer_text: str) -> bool:
    """
    Определяет, является ли RAG ответ просьбой уточнить вопрос

    Проверяет ключевые фразы, которые RAG использует когда вопрос слишком широкий

    Returns:
        True если RAG просит уточнить
    """
    clarification_patterns = [
        'уточните',
        'уточнить',
        'пожалуйста, уточните',
        'какой именно',
        'что именно',
        'конкретнее',
        'например:',
        'вас интересует'
    ]

    answer_lower = answer_text.lower()
    for pattern in clarification_patterns:
        if pattern in answer_lower:
            return True

    return False


def is_rag_no_answer(answer_text: str, metadata: dict) -> bool:
    """
    Определяет, является ли RAG ответ фактическим "no answer"

    Проверяет:
    1. Наличие error в metadata
    2. Ключевые фразы "no answer" в тексте ответа

    Returns:
        True если RAG не смог дать ответ
    """
    # Проверка 1: Error в metadata
    if metadata and 'error' in metadata:
        return True

    # Проверка 2: Ключевые фразы "no answer"
    no_answer_patterns = [
        'к сожалению',
        'не нашел информации',
        'не нашёл информации',
        'нет информации',
        'не знаю',
        'не могу ответить',
        'информации нет',
        'в базе знаний нет',
        'извините',
        'я не знаю'
    ]

    answer_lower = answer_text.lower()
    for pattern in no_answer_patterns:
        if pattern in answer_lower:
            return True

    return False


def handle_search_faq(event: Bitrix24Event, api: Bitrix24API, is_faq_view: bool = False):
    """
    Поиск ответа на вопрос пользователя через каскадную систему

    Args:
        event: Событие от Bitrix24
        api: API клиент
        is_faq_view: True если это просмотр FAQ через кнопку
    """
    query_text = event.message_text
    user_id = event.user_id

    # Показываем индикатор печатания
    api.send_typing(event.dialog_id)

    # Текст для логирования
    log_query_text = f"[Просмотр FAQ] {query_text}" if is_faq_view else query_text

    # Логирование запроса
    query_log_id = database.add_query_log(
        user_id=user_id,
        username=event.username,
        query_text=log_query_text,
        platform='bitrix24'
    )

    # === КАСКАДНЫЙ ПОИСК ===
    result = find_answer(query_text, collection)

    if result.found:
        # Проверяем на неоднозначность (disambiguation)
        # ВАЖНО: При включенном RAG используем лучший результат без disambiguation
        # RAG может объединить информацию из нескольких FAQ и дать более качественный ответ
        if result.ambiguous and result.alternatives and not RAG_ENABLED:
            logger.info(f"⚠️ Обнаружена неоднозначность! Найдено {len(result.alternatives)} альтернатив")

            # Логируем показ вариантов (с процентами confidence)
            questions_shown = "\n".join([f"- [{alt['confidence']:.1f}%] {alt['question']}" for alt in result.alternatives])
            database.add_answer_log(
                query_log_id=query_log_id,
                faq_id=None,  # Конкретный FAQ еще не выбран
                similarity_score=result.confidence,
                answer_shown=f"Показаны варианты для выбора ({len(result.alternatives)} шт.):\n{questions_shown}",
                search_level='disambiguation_shown'
            )

            send_disambiguation(event, api, result.alternatives, query_log_id)
            return
        elif result.ambiguous and result.alternatives and RAG_ENABLED:
            logger.info(f"⚠️ Неоднозначность обнаружена, но RAG включен - используем лучший результат + контекст из {len(result.alternatives)} альтернатив")

        # Нашли однозначный ответ!
        logger.info(f"✅ Ответ найден через {result.search_level} (confidence: {result.confidence:.1f}%)")

        # === RAG ГЕНЕРАЦИЯ (если включена) ===
        final_answer = result.answer
        rag_metadata = None
        is_rag_generated = False  # Флаг для отслеживания RAG генерации
        llm_chunks_data = []  # Для логирования chunks

        if RAG_ENABLED and result.confidence >= RAG_MIN_RELEVANCE_SCORE:
            try:
                logger.info("🤖 Запуск RAG генерации...")
                service = get_llm_service()

                if service:
                    # Подготавливаем chunks для LLM
                    db_chunks = []

                    # ПРИОРИТЕТ 1: Если есть alternatives (несколько похожих FAQ) - используем их ВСЕ
                    if result.alternatives and len(result.alternatives) > 0:
                        try:
                            logger.debug(f"  Используем {len(result.alternatives)} альтернативных FAQ для контекста")
                            for alt in result.alternatives[:RAG_MAX_CHUNKS]:  # Берем ВСЕ альтернативы (до max)
                                if alt['confidence'] >= RAG_MIN_RELEVANCE_SCORE:
                                    db_chunks.append({
                                        'question': alt['question'],
                                        'answer': alt['answer'],
                                        'confidence': alt['confidence']
                                    })
                                    # Сохраняем для логирования
                                    llm_chunks_data.append({
                                        'faq_id': alt.get('faq_id'),
                                        'question': alt['question'],
                                        'confidence': alt['confidence']
                                    })
                                    logger.debug(f"  [{len(db_chunks)}] {alt['question'][:50]}... ({alt['confidence']:.1f}%)")
                        except Exception as e:
                            logger.warning(f"Ошибка при добавлении альтернативных chunks: {e}")
                    else:
                        # Если alternatives нет - добавляем только основной результат
                        db_chunks.append({
                            'question': result.question,
                            'answer': result.answer,
                            'confidence': result.confidence
                        })
                        # Сохраняем для логирования
                        llm_chunks_data.append({
                            'faq_id': result.faq_id,
                            'question': result.question,
                            'confidence': result.confidence
                        })

                    # ПРИОРИТЕТ 2: Добавляем дополнительные результаты из semantic search (если нет alternatives)
                    if not result.alternatives and result.search_level == 'semantic' and result.all_results:
                        try:
                            for i in range(1, min(RAG_MAX_CHUNKS, len(result.all_results.get("documents", [[]])[0]))):
                                dist = result.all_results["distances"][0][i]
                                sim = max(0.0, 1.0 - dist) * 100.0
                                if sim >= RAG_MIN_RELEVANCE_SCORE:
                                    metadata = result.all_results["metadatas"][0][i]
                                    db_chunks.append({
                                        'question': metadata["question"],
                                        'answer': metadata["answer"],
                                        'confidence': sim
                                    })
                                    # Сохраняем для логирования
                                    llm_chunks_data.append({
                                        'faq_id': metadata.get("id"),
                                        'question': metadata["question"],
                                        'confidence': sim
                                    })
                        except Exception as e:
                            logger.warning(f"Ошибка при добавлении дополнительных chunks: {e}")

                    logger.debug(f"Подготовлено {len(db_chunks)} chunks для RAG")

                    # Засекаем время
                    start_time = time.time()

                    # Генерируем ответ через LLM
                    rag_answer, rag_metadata = service.generate_answer(
                        user_question=query_text,
                        db_chunks=db_chunks,
                        max_tokens=RAG_MAX_TOKENS,
                        temperature=RAG_TEMPERATURE
                    )

                    # Вычисляем latency
                    generation_time_ms = int((time.time() - start_time) * 1000)

                    # Используем сгенерированный ответ
                    if rag_answer and 'error' not in rag_metadata:
                        final_answer = rag_answer
                        is_rag_generated = True  # Помечаем что ответ от RAG
                        rag_metadata['generation_time_ms'] = generation_time_ms
                        rag_metadata['chunks_data'] = llm_chunks_data
                        logger.info(f"✅ RAG ответ сгенерирован. Токенов: {rag_metadata.get('tokens_used', {}).get('total', 'N/A')}")

                        # Проверяем тип RAG ответа
                        # 1. Проверяем, является ли это просьбой уточнить (приоритет выше)
                        if is_rag_clarification(rag_answer):
                            logger.info("RAG просит уточнить вопрос, помечаем как search_level='clarification'")
                            result = SearchResult(
                                found=False,
                                faq_id=None,
                                question='',
                                answer=final_answer,
                                confidence=0.0,
                                search_level='clarification',
                                all_results=None,
                                message=final_answer
                            )
                        # 2. Проверяем, является ли это фактическим "no answer"
                        elif is_rag_no_answer(rag_answer, rag_metadata):
                            logger.info("RAG вернул 'no answer', помечаем как search_level='no_answer'")
                            result = SearchResult(
                                found=False,
                                faq_id=None,
                                question='',
                                answer=final_answer,
                                confidence=0.0,
                                search_level='no_answer',
                                all_results=None,
                                message=final_answer
                            )
                    else:
                        logger.warning("RAG генерация вернула ошибку, используем обычный ответ")
                        # Сохраняем ошибку для логирования
                        rag_metadata['generation_time_ms'] = generation_time_ms
                        rag_metadata['chunks_data'] = llm_chunks_data

            except Exception as e:
                logger.error(f"❌ Ошибка RAG генерации: {e}", exc_info=True)
                # Fallback на обычный ответ
                logger.info("Используем обычный ответ из базы данных")
                # Сохраняем ошибку для логирования
                rag_metadata = {
                    'error': str(e),
                    'generation_time_ms': 0,
                    'chunks_data': llm_chunks_data
                }

        # Создаем копию result с финальным ответом (для send_answer)
        final_result = SearchResult(
            found=result.found,
            faq_id=result.faq_id,
            question=result.question,
            answer=final_answer,  # Используем RAG ответ или обычный
            confidence=result.confidence,
            search_level=result.search_level,
            all_results=result.all_results,
            message=result.message,
            ambiguous=result.ambiguous,
            alternatives=result.alternatives
        )

        # Логируем показанный ответ (реальный ответ, который будет показан пользователю)
        answer_log_id = database.add_answer_log(
            query_log_id=query_log_id,
            faq_id=result.faq_id,
            similarity_score=result.confidence,
            answer_shown=final_answer,  # Логируем финальный ответ (RAG или обычный)
            search_level=result.search_level
        )

        # Логируем RAG метаданные (если были)
        if answer_log_id and rag_metadata and is_rag_generated:
            database.add_llm_generation_log(
                answer_log_id=answer_log_id,
                model=rag_metadata.get('model', 'unknown'),
                chunks_used=rag_metadata.get('chunks_used', 0),
                chunks_data=rag_metadata.get('chunks_data', []),
                pii_detected=rag_metadata.get('pii_found', 0),
                tokens_prompt=rag_metadata.get('tokens_used', {}).get('prompt', 0),
                tokens_completion=rag_metadata.get('tokens_used', {}).get('completion', 0),
                tokens_total=rag_metadata.get('tokens_used', {}).get('total', 0),
                finish_reason=rag_metadata.get('finish_reason', 'unknown'),
                generation_time_ms=rag_metadata.get('generation_time_ms', 0),
                error_message=rag_metadata.get('error')
            )

        # Отправляем ответ
        send_answer(event, api, final_result, answer_log_id, is_rag_generated)

    else:
        # Ответ не найден
        logger.warning(f"❌ Ответ не найден для запроса: '{query_text}'")

        database.add_answer_log(
            query_log_id=query_log_id,
            faq_id=None,
            similarity_score=0.0,
            answer_shown=result.message or "Ответ не найден",
            search_level='none'
        )

        send_no_answer(event, api, result.message)


def send_disambiguation(event: Bitrix24Event, api: Bitrix24API, alternatives: List[Dict], query_log_id: int):
    """Отправка уточняющего вопроса с кнопками выбора"""
    message = "Найдено несколько подходящих вопросов. Выберите нужный:"

    # Формируем кнопки для каждой альтернативы
    # Передаем confidence для логирования реального процента
    buttons = []
    for alt in alternatives:
        buttons.append([{
            'text': alt['question'],
            'action': 'disambig',
            'params': f"{alt['faq_id']}_{query_log_id}_{alt['confidence']:.1f}"
        }])

    keyboard = api.create_keyboard(buttons)
    result = api.send_message(event.dialog_id, message, keyboard=keyboard)

    # Сохраняем ID сообщения для последующего удаления
    disambiguation_msg_id = None
    if result.get('result') and isinstance(result['result'], dict):
        disambiguation_msg_id = result['result'].get('MESSAGE_ID')
        # Сохраняем в глобальный словарь для доступа при выборе
        if not hasattr(send_disambiguation, 'message_ids'):
            send_disambiguation.message_ids = {}
        if query_log_id:
            send_disambiguation.message_ids[query_log_id] = disambiguation_msg_id

    logger.info(f"Отправлено disambiguation (msg_id={disambiguation_msg_id}) с {len(alternatives)} вариантами пользователю {event.user_id}")


def send_answer(event: Bitrix24Event, api: Bitrix24API, result: SearchResult, answer_log_id: int, is_rag_generated: bool = False):
    """Отправка найденного ответа с кнопками обратной связи"""

    # Конвертируем ответ из HTML в BB коды для Битрикс24
    answer_bbcode = convert_html_to_bbcode(result.answer)
    question_bbcode = convert_html_to_bbcode(result.question)

    # Формируем сообщение с BB кодами
    # При RAG генерации не показываем заголовок одного FAQ (ответ объединенный из нескольких)
    if is_rag_generated:
        message = answer_bbcode  # Только ответ, без заголовка
    else:
        message = f"✅ [b]{question_bbcode}[/b]\n\n{answer_bbcode}"

    # Добавляем процент схожести если включено в настройках
    show_similarity = bot_settings_cache.get("show_similarity", "true") == "true"
    if show_similarity:
        search_level_icons = {
            'exact': '🎯',
            'keyword': '🔑',
            'semantic': '🧠',
            'direct': '📄',
        }
        icon = search_level_icons.get(result.search_level, '🔍')
        message += f"\n\n{icon} Схожесть: {result.confidence:.1f}%"

    # Кнопки обратной связи
    yes_text = bot_settings_cache.get("feedback_button_yes", database.DEFAULT_BOT_SETTINGS["feedback_button_yes"])
    no_text = bot_settings_cache.get("feedback_button_no", database.DEFAULT_BOT_SETTINGS["feedback_button_no"])

    feedback_buttons = [[
        {
            'text': yes_text,
            'action': 'helpful_yes',
            'params': str(answer_log_id)
        },
        {
            'text': no_text,
            'action': 'helpful_no',
            'params': str(answer_log_id)
        }
    ]]

    # Похожие вопросы (только для semantic search)
    similar_questions_buttons = []
    if result.search_level == 'semantic' and result.all_results:
        semantic_threshold = float(bot_settings_cache.get('semantic_match_threshold', 45))
        if result.all_results and len(result.all_results.get('metadatas', [[]])[0]) > 1:
            for i in range(1, min(4, len(result.all_results['metadatas'][0]))):
                sim = (1.0 - result.all_results['distances'][0][i]) * 100.0
                if sim >= semantic_threshold:
                    meta = result.all_results['metadatas'][0][i]
                    question_text = meta['question']
                    # Обрезаем текст кнопки если слишком длинный
                    button_text = question_text if len(question_text) <= 60 else question_text[:57] + "..."
                    similar_questions_buttons.append([{
                        'text': f"❓ {button_text}",
                        'action': 'similar_question',
                        'params': question_text  # Полный текст вопроса в параметрах
                    }])

    # Объединяем кнопки: сначала feedback, потом похожие вопросы
    all_buttons = feedback_buttons
    if similar_questions_buttons:
        all_buttons.extend(similar_questions_buttons)
        message += "\n\n📌 Возможно, вас также интересует:"

    keyboard = api.create_keyboard(all_buttons)
    attach = None  # Пока не используем attach

    # Отправка
    api.send_message(event.dialog_id, message, keyboard=keyboard, attach=attach)
    logger.info(f"Отправлен ответ пользователю {event.user_id}, {result.search_level}, similarity={result.confidence:.1f}%")


def send_no_answer(event: Bitrix24Event, api: Bitrix24API, fallback_message: str):
    """Отправка сообщения когда ответ не найден"""
    # Используем переданное сообщение из fallback
    message = fallback_message or (
        "😔 Извините, я не нашел точного ответа на ваш вопрос.\n\n"
        "Попробуйте:\n"
        "• Переформулировать вопрос\n"
        "• Написать 'категории' для просмотра всех тем"
    )

    api.send_message(event.dialog_id, message)
    logger.info(f"Отправлено 'не найдено' пользователю {event.user_id}")


def handle_rating(event: Bitrix24Event, api: Bitrix24API,
                  answer_log_id: int, is_helpful: bool,
                  command_id: int = None, message_id: int = None):
    """Обработка оценки ответа"""
    rating = 'helpful' if is_helpful else 'not_helpful'

    success = database.add_rating_log(
        answer_log_id=answer_log_id,
        user_id=event.user_id,
        rating=rating
    )

    if success:
        if is_helpful:
            message = bot_settings_cache.get("feedback_response_yes", database.DEFAULT_BOT_SETTINGS["feedback_response_yes"])
        else:
            message = bot_settings_cache.get("feedback_response_no", database.DEFAULT_BOT_SETTINGS["feedback_response_no"])
    else:
        message = "❌ Ошибка сохранения отзыва"

    # Если вызвано из команды (кнопки), используем answer_command и обновляем сообщение
    if command_id and message_id:
        # Отправляем ответ на команду
        api.answer_command(command_id, message_id, message)

        # Удаляем кнопки из исходного сообщения
        logger.debug(f"🔄 Удаление кнопок из сообщения {message_id}")
        api.update_message(message_id, remove_keyboard=True)
    else:
        api.send_message(event.dialog_id, message)

    logger.info(f"Получена оценка от пользователя {event.user_id}: {rating}")


# ========== WEBHOOK ENDPOINT ==========

@app.route('/', methods=['POST'])
@app.route('/webhook/bitrix24', methods=['POST'])
def webhook_handler():
    """Обработчик вебхуков от Bitrix24"""
    try:
        logger.info(f"📥 Получен POST запрос на {request.path}")

        # Получаем данные от Bitrix24
        if request.is_json:
            event_data = request.get_json()
        else:
            event_data = request.form.to_dict()

        logger.info(f"📩 Получено событие от Bitrix24: {event_data.get('event')}")
        logger.debug(f"🔍 Полные данные события: {json.dumps(event_data, ensure_ascii=False, indent=2)}")

        # Парсим событие
        event = Bitrix24Event(event_data)

        logger.debug(f"🔧 Распарсенные данные:")
        logger.debug(f"   User ID: {event.user_id}")
        logger.debug(f"   Dialog ID: {event.dialog_id}")
        logger.debug(f"   Domain: {event.domain}")
        logger.debug(f"   Message: '{event.message_text}'")

        # Инициализируем API с вебхуком из .env
        global b24_api
        if not b24_api and BITRIX24_WEBHOOK:
            logger.debug(f"🔧 Инициализация Bitrix24 API с вебхуком: {BITRIX24_WEBHOOK[:50]}...")
            logger.debug(f"🔧 CLIENT_ID: {BITRIX24_BOT_CLIENT_ID}")
            logger.debug(f"🔧 BOT_ID: {BITRIX24_BOT_ID}")

            # Преобразуем BOT_ID в число
            bot_id = None
            if BITRIX24_BOT_ID:
                try:
                    bot_id = int(BITRIX24_BOT_ID)
                except ValueError:
                    logger.warning(f"⚠️ BITRIX24_BOT_ID '{BITRIX24_BOT_ID}' не является числом")

            # Используем CLIENT_ID для API запросов
            b24_api = Bitrix24API(BITRIX24_WEBHOOK, BITRIX24_BOT_CLIENT_ID, bot_id)

            # Регистрируем команды для кнопок (один раз при старте)
            logger.info("📝 Регистрация команд для кнопок...")
            register_bot_commands(b24_api)

        if not b24_api:
            logger.error("❌ Bitrix24 API не инициализирован - проверьте BITRIX24_WEBHOOK в .env")
            return jsonify({'success': False, 'error': 'API not initialized'}), 500

        # Роутинг событий
        if event.is_message:
            logger.debug(f"➡️ Роутинг: обработка сообщения")
            handle_message_event(event, b24_api)
        elif event.is_command:
            logger.debug(f"➡️ Роутинг: обработка команды")
            handle_command_event(event, b24_api)
        elif event.is_join_chat:
            logger.debug(f"➡️ Роутинг: обработка присоединения к чату")
            handle_start(event, b24_api)
        elif event.is_bot_delete:
            logger.info(f"🗑️ Бот удален из портала {event.domain}")
        elif event.is_app_install:
            logger.info(f"📦 Приложение установлено на портал {event.domain}")
        elif event.is_user_add:
            logger.info(f"👤 Новый пользователь добавлен: {event.new_user_name} (ID: {event.new_user_id})")
            handle_new_user_welcome(event, b24_api)
        else:
            logger.warning(f"⚠️ Неизвестный тип события: {event_data.get('event')}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"❌ Ошибка обработки вебхука: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def handle_message_event(event: Bitrix24Event, api: Bitrix24API):
    """Обработка события нового сообщения"""
    message = event.message_text

    logger.info(f"💬 Получено сообщение от User ID {event.user_id}: '{message}'")

    if not message:
        logger.warning("⚠️ Получено пустое сообщение")
        return

    # Обработка команд
    message_lower = message.lower().strip()
    logger.debug(f"🔍 Обработка команды: '{message_lower}'")

    # Команды помощи
    if message_lower in ['/start', '/помощь', 'помощь', 'help', 'старт']:
        logger.debug(f"✅ Распознана команда: help/start")
        handle_start(event, api)
    # Команда категории
    elif message_lower in ['/категории', 'категории', 'категория']:
        logger.debug(f"✅ Распознана команда: категории")
        handle_categories(event, api)
    # Обработка текстовых команд от кнопок (fallback если команды не зарегистрированы)
    elif message_lower.startswith('helpful_yes_') or message_lower.startswith('👍'):
        try:
            # Пытаемся извлечь ID из сообщения
            if '_' in message_lower:
                answer_log_id = int(message_lower.split('_')[-1])
                handle_rating(event, api, answer_log_id, is_helpful=True)
            else:
                logger.debug("⚠️ Не удалось извлечь answer_log_id из сообщения")
        except (ValueError, IndexError):
            logger.error(f"Ошибка парсинга answer_log_id из {message_lower}")
    elif message_lower.startswith('helpful_no_') or message_lower.startswith('👎'):
        try:
            if '_' in message_lower:
                answer_log_id = int(message_lower.split('_')[-1])
                handle_rating(event, api, answer_log_id, is_helpful=False)
            else:
                logger.debug("⚠️ Не удалось извлечь answer_log_id из сообщения")
        except (ValueError, IndexError):
            logger.error(f"Ошибка парсинга answer_log_id из {message_lower}")
    # Обычный поиск по FAQ
    else:
        handle_search_faq(event, api)


def handle_command_event(event: Bitrix24Event, api: Bitrix24API):
    """Обработка события команды (нажатие на кнопку)"""
    command = event.command_name
    params = event.command_params
    command_id = event.command_data.get('COMMAND_ID')
    message_id = event.command_data.get('MESSAGE_ID')

    logger.info(f"🔘 Получена команда от User ID {event.user_id}: '{command}' (params: '{params}')")
    logger.debug(f"   Command ID: {command_id}, Message ID: {message_id}")
    logger.debug(f"   Context: {event.command_context}")

    if not command:
        logger.warning("⚠️ Получена команда без названия")
        return

    command_lower = command.lower().strip()

    # Обработка выбора категории из кнопки
    if command_lower.startswith('cat'):
        # Если есть params, это ID категории, иначе берем из самой команды
        if params:
            category = params
        else:
            category = command_lower[4:] if command_lower.startswith('cat_') else ''
        if category:
            handle_category_select(event, api, category)
    # Положительная оценка
    elif command_lower == 'helpful_yes':
        try:
            answer_log_id = int(params) if params else 0
            if answer_log_id > 0:
                handle_rating(event, api, answer_log_id, is_helpful=True,
                             command_id=command_id, message_id=message_id)
            else:
                logger.error(f"⚠️ Нет answer_log_id в параметрах команды")
        except (ValueError, TypeError):
            logger.error(f"Ошибка парсинга answer_log_id из params: {params}")
    # Отрицательная оценка
    elif command_lower == 'helpful_no':
        try:
            answer_log_id = int(params) if params else 0
            if answer_log_id > 0:
                handle_rating(event, api, answer_log_id, is_helpful=False,
                             command_id=command_id, message_id=message_id)
            else:
                logger.error(f"⚠️ Нет answer_log_id в параметрах команды")
        except (ValueError, TypeError):
            logger.error(f"Ошибка парсинга answer_log_id из params: {params}")
    # Нажатие на похожий вопрос
    elif command_lower == 'similar_question':
        if params:
            # Создаем новый event с текстом вопроса и вызываем поиск
            logger.info(f"🔍 Поиск по похожему вопросу: {params}")
            event.message_text = params  # Подменяем текст сообщения на вопрос из кнопки
            # Передаем is_faq_view=True для добавления префикса в логи
            handle_search_faq(event, api, is_faq_view=True)
            # answer_command не нужен - ответ уже отправлен через handle_search_faq
        else:
            logger.error(f"⚠️ Нет текста вопроса в параметрах команды similar_question")
    # Выбор FAQ из disambiguation
    elif command_lower == 'disambig':
        if params:
            # Парсим params: faq_id_query_log_id_confidence
            # faq_id имеет формат "faq_XXXXXXXX", поэтому используем rsplit с конца
            try:
                parts = params.rsplit('_', 2)  # Разделяем с конца: faq_id, query_log_id, confidence
                faq_id = parts[0]  # "faq_26ba5775"
                original_query_log_id = int(parts[1]) if len(parts) > 1 else None
                real_confidence = float(parts[2]) if len(parts) > 2 else 100.0  # Реальный confidence из поиска

                # Получаем FAQ по ID
                faq = database.get_faq_by_id(faq_id)
                if faq:
                    # Логируем выбранный ответ (используем реальный confidence)
                    answer_log_id = None
                    if original_query_log_id:
                        answer_log_id = database.add_answer_log(
                            query_log_id=original_query_log_id,
                            faq_id=faq_id,
                            similarity_score=real_confidence,  # Реальный confidence из поиска
                            answer_shown=faq['answer'],
                            search_level='disambiguation'
                        )

                    # Получаем ID сообщения с вариантами из словаря
                    disambiguation_msg_id = None
                    if hasattr(send_disambiguation, 'message_ids') and original_query_log_id:
                        disambiguation_msg_id = send_disambiguation.message_ids.pop(original_query_log_id, None)

                    # Редактируем сообщение с вариантами вместо удаления
                    msg_id_to_update = disambiguation_msg_id or message_id
                    if msg_id_to_update:
                        # Конвертируем ответ в BB коды
                        answer_bbcode = convert_html_to_bbcode(faq['answer'])
                        question_bbcode = convert_html_to_bbcode(faq['question'])

                        # Формируем новое сообщение
                        updated_message = f"✅ [b]{question_bbcode}[/b]\n\n{answer_bbcode}"

                        # Добавляем процент схожести если включено
                        show_similarity = bot_settings_cache.get("show_similarity", "true") == "true"
                        if show_similarity:
                            icon = '🔀'  # Иконка для disambiguation
                            updated_message += f"\n\n{icon} Схожесть: {real_confidence:.1f}%"

                        # Кнопки обратной связи
                        yes_text = bot_settings_cache.get("feedback_button_yes", database.DEFAULT_BOT_SETTINGS["feedback_button_yes"])
                        no_text = bot_settings_cache.get("feedback_button_no", database.DEFAULT_BOT_SETTINGS["feedback_button_no"])

                        feedback_buttons = [[
                            {'text': yes_text, 'action': 'helpful_yes', 'params': str(answer_log_id)},
                            {'text': no_text, 'action': 'helpful_no', 'params': str(answer_log_id)}
                        ]]

                        keyboard = api.create_keyboard(feedback_buttons)

                        # Обновляем сообщение
                        api.update_message(msg_id_to_update, message=updated_message, keyboard=keyboard)
                        logger.info(f"✏️ Обновлено сообщение {msg_id_to_update} с выбранным вариантом")
                    else:
                        # Если не нашли ID старого сообщения, отправляем новое
                        from src.core.search import SearchResult
                        result = SearchResult(
                            found=True,
                            faq_id=faq_id,
                            question=faq['question'],
                            answer=faq['answer'],
                            confidence=real_confidence,
                            search_level='disambiguation',
                            all_results=None,
                            message=None
                        )
                        send_answer(event, api, result, answer_log_id)
                else:
                    logger.error(f"❌ FAQ с ID {faq_id} не найден")
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка парсинга params для disambig: {params}, error: {e}")
        else:
            logger.error(f"⚠️ Нет params в команде disambig")
    else:
        logger.warning(f"⚠️ Неизвестная команда: {command_lower}")


# ========== УПРАВЛЕНИЕ (для web_admin.py) ==========

@app.route('/api/reload-chromadb', methods=['POST'])
def reload_chromadb_endpoint():
    """Endpoint для перезагрузки ChromaDB (вызывается из web_admin.py)"""
    success = reload_chromadb()
    return jsonify({'success': success})


@app.route('/api/reload-settings', methods=['POST'])
def reload_settings_endpoint():
    """Endpoint для перезагрузки настроек бота (вызывается из web_admin.py)"""
    success = reload_bot_settings()

    # Перезагружаем промпт LLM сервиса (если он инициализирован)
    global llm_service
    if llm_service is not None:
        try:
            llm_service.reload_prompt()
            logger.info("✅ Промпт LLM сервиса перезагружен")
        except Exception as e:
            logger.error(f"❌ Ошибка перезагрузки промпта LLM: {e}")

    return jsonify({'success': success})


@app.route('/', methods=['GET'])
def index():
    """Информация о боте (для GET запросов)"""
    return jsonify({
        'bot': 'FAQ Bot for Bitrix24',
        'status': 'running',
        'webhook_path': '/ или /webhook/bitrix24',
        'health_check': '/health',
        'chromadb_records': collection.count() if collection else 0
    })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'chromadb_records': collection.count() if collection else 0,
        'webhook_configured': bool(BITRIX24_WEBHOOK)
    })


# ========== ЗАПУСК ==========

if __name__ == '__main__':
    logger.info("🚀 Запуск FAQ Бота для Bitrix24...")

    # Инициализация БД
    try:
        database.init_database()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

    # Инициализация ChromaDB
    init_chromadb()

    # Загрузка настроек бота
    reload_bot_settings()

    # Проверка конфигурации
    if not BITRIX24_WEBHOOK:
        logger.warning("⚠️ BITRIX24_WEBHOOK не настроен в .env!")
        logger.warning("⚠️ Бот не сможет отправлять сообщения в Bitrix24")
        logger.warning("⚠️ Добавьте BITRIX24_WEBHOOK=https://your-domain.bitrix24.ru/rest/1/webhook_key/ в .env")

    # Запуск Flask сервера
    port = int(os.getenv('BITRIX24_PORT', 5002))
    host = os.getenv('BITRIX24_HOST', '0.0.0.0')

    logger.info(f"📡 Сервер запускается на {host}:{port}")
    logger.info(f"📍 Webhook URL: http://your-server.com:{port}/webhook/bitrix24")
    logger.info(f"📊 Health check: http://your-server.com:{port}/health")
    logger.info("=" * 60)

    app.run(host=host, port=port, debug=False)
