# simple_vector_search.py
# -*- coding: utf-8 -*-
"""
Простой векторный поиск без ChromaDB
Использует sklearn для вычисления cosine similarity
"""

import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Optional, Tuple
import os

EMBEDDINGS_FILE = "embeddings_cache.pkl"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class SimpleVectorSearch:
    def __init__(self):
        print("Загрузка модели эмбеддингов...")
        self.model = SentenceTransformer(MODEL_NAME)
        self.documents = []
        self.metadatas = []
        self.ids = []
        self.embeddings = None
        print("Модель загружена!")

    def add_documents(self, documents: List[str], metadatas: List[Dict], ids: List[str]):
        """Добавить документы и создать эмбеддинги"""
        print(f"Создание эмбеддингов для {len(documents)} документов...")

        self.documents = documents
        self.metadatas = metadatas
        self.ids = ids

        # Создаём эмбеддинги
        self.embeddings = self.model.encode(documents, show_progress_bar=True)

        # Сохраняем в кэш
        self._save_cache()
        print(f"✅ Добавлено {len(documents)} документов")

    def query(self, query_text: str, n_results: int = 3) -> Dict:
        """Поиск похожих документов"""
        if self.embeddings is None or len(self.embeddings) == 0:
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
                "ids": [[]]
            }

        # Создаём эмбеддинг для запроса
        query_embedding = self.model.encode([query_text])

        # Вычисляем cosine similarity
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]

        # Преобразуем similarity в distance (1 - similarity для совместимости с ChromaDB)
        distances = 1 - similarities

        # Сортируем по убыванию similarity (по возрастанию distance)
        top_indices = np.argsort(distances)[:n_results]

        # Формируем результат в формате, совместимом с ChromaDB
        result_docs = [self.documents[i] for i in top_indices]
        result_metas = [self.metadatas[i] for i in top_indices]
        result_dists = [float(distances[i]) for i in top_indices]
        result_ids = [self.ids[i] for i in top_indices]

        return {
            "documents": [result_docs],
            "metadatas": [result_metas],
            "distances": [result_dists],
            "ids": [result_ids]
        }

    def get(self, ids: List[str]) -> Dict:
        """Получить документы по ID"""
        result_docs = []
        result_metas = []

        for query_id in ids:
            if query_id in self.ids:
                idx = self.ids.index(query_id)
                result_docs.append(self.documents[idx])
                result_metas.append(self.metadatas[idx])

        return {
            "documents": result_docs,
            "metadatas": result_metas
        }

    def count(self) -> int:
        """Количество документов"""
        return len(self.documents)

    def clear(self):
        """Очистить все данные"""
        self.documents = []
        self.metadatas = []
        self.ids = []
        self.embeddings = None
        if os.path.exists(EMBEDDINGS_FILE):
            os.remove(EMBEDDINGS_FILE)

    def _save_cache(self):
        """Сохранить эмбеддинги в кэш"""
        cache_data = {
            'documents': self.documents,
            'metadatas': self.metadatas,
            'ids': self.ids,
            'embeddings': self.embeddings
        }
        with open(EMBEDDINGS_FILE, 'wb') as f:
            pickle.dump(cache_data, f)
        print(f"Кэш сохранён в {EMBEDDINGS_FILE}")

    def load_cache(self) -> bool:
        """Загрузить эмбеддинги из кэша"""
        if os.path.exists(EMBEDDINGS_FILE):
            try:
                with open(EMBEDDINGS_FILE, 'rb') as f:
                    cache_data = pickle.load(f)
                self.documents = cache_data['documents']
                self.metadatas = cache_data['metadatas']
                self.ids = cache_data['ids']
                self.embeddings = cache_data['embeddings']
                print(f"✅ Загружено из кэша: {len(self.documents)} документов")
                return True
            except Exception as e:
                print(f"❌ Ошибка загрузки кэша: {e}")
                return False
        return False
