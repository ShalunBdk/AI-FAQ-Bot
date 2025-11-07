"""
FastAPI Backend для production версии
Демонстрация REST API для интеграции с Telegram и Битрикс24
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import chromadb
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================================
# ИНИЦИАЛИЗАЦИЯ
# ===============================================

app = FastAPI(
    title="FAQ Bot API",
    description="API для корпоративного бота с векторным поиском",
    version="1.0.0"
)

# CORS для доступа из админки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модель векторизации
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# ChromaDB клиент
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(name="faq_collection")

# ===============================================
# МОДЕЛИ ДАННЫХ
# ===============================================

class SearchQuery(BaseModel):
    """Запрос на поиск"""
    query: str
    user_id: Optional[str] = None
    category: Optional[str] = None
    limit: int = 3

class SearchResult(BaseModel):
    """Результат поиска"""
    id: str
    question: str
    answer: str
    category: str
    similarity: float
    
class SearchResponse(BaseModel):
    """Ответ на запрос поиска"""
    results: List[SearchResult]
    total: int
    query: str
    processing_time: float

class FAQCreate(BaseModel):
    """Создание нового FAQ"""
    question: str
    answer: str
    category: str
    keywords: List[str]
    alternative_questions: Optional[List[str]] = []

class FAQUpdate(BaseModel):
    """Обновление FAQ"""
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    keywords: Optional[List[str]] = None

class FeedbackCreate(BaseModel):
    """Обратная связь от пользователя"""
    query: str
    result_id: str
    is_helpful: bool
    user_id: Optional[str] = None
    comment: Optional[str] = None

class Statistics(BaseModel):
    """Статистика использования"""
    total_queries: int
    total_faqs: int
    avg_similarity: float
    helpful_rate: float
    top_queries: List[dict]

# ===============================================
# ENDPOINTS - ПОИСК
# ===============================================

@app.post("/api/search", response_model=SearchResponse)
async def search_faq(query: SearchQuery):
    """
    Поиск ответа в базе знаний
    
    Пример запроса:
    ```json
    {
        "query": "можно ли в шортах на работу?",
        "user_id": "telegram_123456",
        "limit": 3
    }
    ```
    """
    start_time = datetime.now()
    
    try:
        # Векторизация запроса
        query_embedding = model.encode(query.query).tolist()
        
        # Поиск
        search_params = {
            "query_embeddings": [query_embedding],
            "n_results": query.limit
        }
        
        # Фильтр по категории, если указана
        if query.category:
            search_params["where"] = {"category": query.category}
        
        results = collection.query(**search_params)
        
        # Формирование ответа
        search_results = []
        
        if results['documents'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                
                # Конвертация distance в similarity (0-100%)
                similarity = max(0, (1 - distance) * 100)
                
                search_results.append(SearchResult(
                    id=doc_id,
                    question=metadata['question'],
                    answer=metadata['answer'],
                    category=metadata['category'],
                    similarity=round(similarity, 2)
                ))
        
        # Логирование
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Search: query='{query.query}', user={query.user_id}, "
            f"results={len(search_results)}, time={processing_time:.3f}s"
        )
        
        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=query.query,
            processing_time=round(processing_time, 3)
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===============================================
# ENDPOINTS - УПРАВЛЕНИЕ FAQ
# ===============================================

@app.post("/api/faq", status_code=201)
async def create_faq(faq: FAQCreate):
    """
    Создание нового FAQ
    
    Используется Strapi через webhook при создании статьи
    """
    try:
        # Генерация ID
        faq_id = f"faq_{datetime.now().timestamp()}"
        
        # Текст для векторизации
        search_text = f"{faq.question} {' '.join(faq.keywords)}"
        if faq.alternative_questions:
            search_text += " " + " ".join(faq.alternative_questions)
        
        # Векторизация
        embedding = model.encode(search_text).tolist()
        
        # Добавление в ChromaDB
        collection.add(
            embeddings=[embedding],
            documents=[search_text],
            metadatas=[{
                "question": faq.question,
                "answer": faq.answer,
                "category": faq.category
            }],
            ids=[faq_id]
        )
        
        logger.info(f"FAQ created: id={faq_id}, category={faq.category}")
        
        return {"id": faq_id, "status": "created"}
        
    except Exception as e:
        logger.error(f"Create FAQ error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/faq/{faq_id}")
async def update_faq(faq_id: str, faq: FAQUpdate):
    """
    Обновление существующего FAQ
    """
    try:
        # Получение текущих данных
        existing = collection.get(ids=[faq_id])
        
        if not existing['ids']:
            raise HTTPException(status_code=404, detail="FAQ not found")
        
        # Обновление метаданных
        metadata = existing['metadatas'][0]
        
        if faq.question:
            metadata['question'] = faq.question
        if faq.answer:
            metadata['answer'] = faq.answer
        if faq.category:
            metadata['category'] = faq.category
        
        # Ре-векторизация если изменился вопрос
        if faq.question or faq.keywords:
            search_text = metadata['question']
            if faq.keywords:
                search_text += " " + " ".join(faq.keywords)
            
            embedding = model.encode(search_text).tolist()
            
            # Удаление старого и добавление нового
            collection.delete(ids=[faq_id])
            collection.add(
                embeddings=[embedding],
                documents=[search_text],
                metadatas=[metadata],
                ids=[faq_id]
            )
        
        logger.info(f"FAQ updated: id={faq_id}")
        
        return {"id": faq_id, "status": "updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update FAQ error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/faq/{faq_id}")
async def delete_faq(faq_id: str):
    """
    Удаление FAQ
    """
    try:
        collection.delete(ids=[faq_id])
        logger.info(f"FAQ deleted: id={faq_id}")
        return {"id": faq_id, "status": "deleted"}
        
    except Exception as e:
        logger.error(f"Delete FAQ error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/faq")
async def list_faqs(category: Optional[str] = None, limit: int = 50):
    """
    Получение списка всех FAQ
    """
    try:
        if category:
            results = collection.get(
                where={"category": category},
                limit=limit
            )
        else:
            results = collection.get(limit=limit)
        
        faqs = []
        for i, faq_id in enumerate(results['ids']):
            metadata = results['metadatas'][i]
            faqs.append({
                "id": faq_id,
                "question": metadata['question'],
                "answer": metadata['answer'][:100] + "...",  # Краткое описание
                "category": metadata['category']
            })
        
        return {"faqs": faqs, "total": len(faqs)}
        
    except Exception as e:
        logger.error(f"List FAQs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===============================================
# ENDPOINTS - ОБРАТНАЯ СВЯЗЬ И АНАЛИТИКА
# ===============================================

@app.post("/api/feedback")
async def submit_feedback(feedback: FeedbackCreate):
    """
    Отправка обратной связи от пользователя
    
    В production сохраняется в PostgreSQL для аналитики
    """
    try:
        # В реальности сохраняем в БД
        logger.info(
            f"Feedback: query='{feedback.query}', result={feedback.result_id}, "
            f"helpful={feedback.is_helpful}, user={feedback.user_id}"
        )
        
        # Здесь можно добавить логику:
        # - Если много негативных отзывов на FAQ → уведомить менеджера
        # - Если вопрос без ответа → добавить в очередь на создание FAQ
        
        return {"status": "feedback_received"}
        
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/statistics", response_model=Statistics)
async def get_statistics():
    """
    Статистика использования бота
    
    В production данные из PostgreSQL
    """
    try:
        # Демо-данные
        # В реальности - SQL запросы к базе логов
        
        total_faqs = collection.count()
        
        return Statistics(
            total_queries=1234,  # Из таблицы logs
            total_faqs=total_faqs,
            avg_similarity=78.5,  # Средний similarity score
            helpful_rate=0.82,    # 82% положительных отзывов
            top_queries=[
                {"query": "зарплата", "count": 45},
                {"query": "отпуск", "count": 38},
                {"query": "спецодежда", "count": 32},
            ]
        )
        
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/unanswered")
async def get_unanswered_queries(limit: int = 20):
    """
    Вопросы без хороших ответов (similarity < 70%)
    
    Помогает менеджерам понять, какие FAQ нужно добавить
    """
    try:
        # В production - из таблицы логов с фильтром
        # SELECT query, COUNT(*) as count
        # FROM query_logs
        # WHERE best_similarity < 0.7
        # GROUP BY query
        # ORDER BY count DESC
        # LIMIT {limit}
        
        unanswered = [
            {"query": "как получить пропуск для гостя", "count": 15, "avg_similarity": 0.45},
            {"query": "где парковка для сотрудников", "count": 12, "avg_similarity": 0.52},
            {"query": "можно ли привести собаку в офис", "count": 8, "avg_similarity": 0.38},
        ]
        
        return {"unanswered": unanswered, "total": len(unanswered)}
        
    except Exception as e:
        logger.error(f"Unanswered queries error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===============================================
# ENDPOINTS - СЛУЖЕБНЫЕ
# ===============================================

@app.get("/health")
async def health_check():
    """Проверка работоспособности"""
    try:
        # Проверка ChromaDB
        count = collection.count()
        
        return {
            "status": "healthy",
            "service": "faq-bot-api",
            "database": "connected",
            "faq_count": count,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.post("/api/reindex")
async def reindex_all():
    """
    Полная ре-индексация базы знаний
    
    Вызывается при изменении модели векторизации
    """
    try:
        # Получить все FAQ из Strapi
        # Ре-векторизовать
        # Обновить ChromaDB
        
        logger.info("Reindexing started")
        
        # В реальности:
        # 1. Получить все записи из Strapi API
        # 2. Для каждой записи создать новый embedding
        # 3. Очистить collection
        # 4. Загрузить новые embeddings
        
        return {"status": "reindexing_started"}
        
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===============================================
# ДОКУМЕНТАЦИЯ API
# ===============================================

@app.get("/")
async def root():
    """Главная страница API"""
    return {
        "service": "FAQ Bot API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "search": "POST /api/search",
            "create_faq": "POST /api/faq",
            "update_faq": "PUT /api/faq/{id}",
            "delete_faq": "DELETE /api/faq/{id}",
            "list_faqs": "GET /api/faq",
            "feedback": "POST /api/feedback",
            "statistics": "GET /api/statistics",
            "unanswered": "GET /api/unanswered",
            "health": "GET /health"
        }
    }

# ===============================================
# ЗАПУСК
# ===============================================

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting FAQ Bot API...")
    print("📖 Documentation: http://localhost:8000/docs")
    print("🔍 Health check: http://localhost:8000/health")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload при изменении кода
        log_level="info"
    )
