# -*- coding: utf-8 -*-
"""
Локальное переобучение ChromaDB
"""

import sys
import os
import logging

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from chromadb.utils import embedding_functions
from src.core import database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
MODEL_NAME = os.getenv("MODEL_NAME", "deepvk/USER2-base")
CHROMA_PATH = os.getenv('CHROMA_PATH', './data/chroma_db')


def retrain_chromadb():
    """
    Переобучение ChromaDB на основе данных из базы
    """
    logger.info("="*80)
    logger.info("🔄 ПЕРЕОБУЧЕНИЕ CHROMADB")
    logger.info("="*80)
    logger.info(f"   Модель: {MODEL_NAME}")
    logger.info(f"   Путь: {CHROMA_PATH}")

    try:
        # Инициализируем ChromaDB
        chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=MODEL_NAME
        )

        # Удаляем старую коллекцию
        try:
            chroma_client.delete_collection(name="faq_collection")
            logger.info("✅ Старая коллекция удалена")
        except Exception as e:
            logger.info(f"⚠️ Коллекции не было или ошибка удаления: {e}")

        # Создаем новую коллекцию
        collection = chroma_client.create_collection(
            name="faq_collection",
            embedding_function=embedding_func,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("✅ Создана новая коллекция")

        # Получаем все FAQ из базы
        all_faqs = database.get_all_faqs()
        if not all_faqs:
            logger.error("❌ В базе нет данных для обучения")
            return False

        logger.info(f"📥 Загружено {len(all_faqs)} FAQ из базы")

        # Подготавливаем данные для ChromaDB
        documents, metadatas, ids = [], [], []
        for faq in all_faqs:
            # Обрабатываем ключевые слова
            keywords = faq.get('keywords', [])
            if isinstance(keywords, list):
                keywords_str = ' '.join(keywords)
            elif isinstance(keywords, str):
                keywords_str = keywords.replace(',', ' ')
            else:
                keywords_str = ''

            # Формируем текст документа с префиксом
            text = f"{faq['question']} {keywords_str}"
            documents.append(f"search_document: {text}")

            metadatas.append({
                "category": faq["category"],
                "question": faq["question"],
                "answer": faq["answer"]
            })
            ids.append(str(faq["id"]))

        # Добавляем в ChromaDB
        collection.add(documents=documents, metadatas=metadatas, ids=ids)

        logger.info(f"✅ ChromaDB переобучена: {len(all_faqs)} записей")
        logger.info(f"✅ Коллекция содержит {collection.count()} документов")

        # Проверяем, что коллекция доступна
        test_results = collection.query(
            query_texts=["search_query: тест"],
            n_results=1
        )
        if test_results and test_results['ids']:
            logger.info("✅ Коллекция работает корректно")
        else:
            logger.warning("⚠️ Коллекция пустая или недоступна")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при переобучении: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Главная функция"""
    success = retrain_chromadb()

    if success:
        logger.info("\n" + "="*80)
        logger.info("🎉 ПЕРЕОБУЧЕНИЕ ЗАВЕРШЕНО УСПЕШНО!")
        logger.info("="*80)
        logger.info("\nТеперь можно запустить:")
        logger.info("  python scripts/test_keyword_ranking.py")
    else:
        logger.error("\n" + "="*80)
        logger.error("❌ ОШИБКА ПЕРЕОБУЧЕНИЯ")
        logger.error("="*80)


if __name__ == "__main__":
    main()
