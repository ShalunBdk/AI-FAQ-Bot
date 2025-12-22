# RAG Logging - Быстрый старт

## Что это?

RAG Logging - система автоматического логирования всех RAG (Retrieval-Augmented Generation) генераций с детальными метаданными:
- Какие FAQ статьи были отправлены в LLM
- Сколько токенов использовано
- Время генерации ответа
- Обнаруженные PII сущности
- Ошибки (если возникли)

## Как использовать

### 1️⃣ Запуск миграции (первый раз)

```bash
python scripts/migrate_add_llm_generations.py
```

**Результат**: Создается таблица `llm_generations` в базе данных.

### 2️⃣ Просмотр RAG данных в Admin Panel

#### Открыть страницу логов
http://localhost:5000/admin/logs

#### Что вы увидите:

1. **🤖 RAG Badge** - рядом с уровнем поиска (🎯/🔑/🧠)
   - Появляется, когда ответ был сгенерирован через RAG

2. **ℹ️ Info кнопка** - нажмите для деталей
   - Открывает expandable секцию с метаданными:
     - Model (например, `openai/gpt-4o-mini`)
     - Tokens (Prompt / Completion / Total)
     - PII Detected
     - Generation Time (ms)
     - **FAQ Chunks** - список вопросов с confidence %

3. **📊 RAG Statistics Card** (вверху страницы)
   - Всего RAG ответов
   - Использовано токенов
   - Success Rate (%)
   - Среднее время генерации

### 3️⃣ SQL запросы для анализа

#### Просмотр всех RAG записей
```bash
sqlite3 faq_bot.db < scripts/test_rag_logging.sql
```

#### Ручной SQL
```sql
-- Последние 10 RAG генераций
SELECT
    lg.id,
    lg.model,
    lg.chunks_used,
    lg.tokens_total,
    lg.generation_time_ms,
    lg.error_message,
    ql.query_text
FROM llm_generations lg
LEFT JOIN answer_logs al ON lg.answer_log_id = al.id
LEFT JOIN query_logs ql ON al.query_log_id = ql.id
ORDER BY lg.created_at DESC
LIMIT 10;
```

### 4️⃣ Тестирование интеграции

```bash
python scripts/test_rag_integration.py
```

**Что проверяется**:
- ✅ Таблица llm_generations существует
- ✅ Функция add_llm_generation_log() работает
- ✅ Данные корректно сохраняются
- ✅ get_logs() возвращает llm_metadata
- ✅ Статистика RAG вычисляется

## Структура данных

### Таблица llm_generations

| Колонка | Тип | Описание |
|---------|-----|----------|
| id | INTEGER | Primary key |
| answer_log_id | INTEGER | FK to answer_logs |
| model | TEXT | LLM модель (openai/gpt-4o-mini) |
| chunks_used | INTEGER | Количество FAQ chunks |
| chunks_data | TEXT | JSON список chunks с вопросами |
| pii_detected | INTEGER | Количество PII сущностей |
| tokens_prompt | INTEGER | Токены в prompt |
| tokens_completion | INTEGER | Токены в response |
| tokens_total | INTEGER | Всего токенов |
| finish_reason | TEXT | Причина завершения (stop, etc.) |
| generation_time_ms | INTEGER | Время генерации (мс) |
| error_message | TEXT | Ошибка (NULL если успех) |
| created_at | TIMESTAMP | Время создания |

### Пример chunks_data (JSON)

```json
[
  {
    "faq_id": "42",
    "question": "Как вернуть товар?",
    "confidence": 85.5
  },
  {
    "faq_id": "17",
    "question": "Условия возврата",
    "confidence": 72.3
  }
]
```

## API Endpoints

### GET /admin/api/logs/rag-statistics

Возвращает статистику RAG:

```json
{
  "total_rag_answers": 150,
  "avg_tokens_per_answer": 245.3,
  "total_tokens_used": 36795,
  "rag_errors": 3,
  "rag_success_rate": 98.0,
  "models_used": {
    "openai/gpt-4o-mini": 145,
    "openai/gpt-4o": 5
  },
  "avg_chunks_per_query": 2.8,
  "avg_generation_time_ms": 1250
}
```

## Troubleshooting

### ❌ Таблица llm_generations не существует

**Решение**: Запустите миграцию
```bash
python scripts/migrate_add_llm_generations.py
```

### ❌ LLM metadata not found for...

**Решение**: Уже исправлено в `logs.html:708`
- Обновите до последней версии
- Проблема была в несоответствии ключей (`'null'` vs `logIndex`)

### ❌ NameError: require_auth_in_production

**Решение**: Уже исправлено в `web_admin.py:1238`
- Удалены неиспользуемые декораторы
- Endpoint работает без auth в dev режиме

### ⚠️ RAG badge не появляется

**Проверьте**:
1. RAG включен в `.env`: `RAG_ENABLED=True`
2. OPENROUTER_API_KEY настроен
3. Запрос действительно прошел через RAG (confidence >= threshold)
4. `add_llm_generation_log()` вызывается после генерации

## Дополнительная документация

- **Полный гайд по RAG**: `docs/RAG_GUIDE.md`
- **Общие инструкции**: `CLAUDE.md`
- **План реализации**: `.claude/plans/splendid-snacking-stonebraker.md`

---

**Версия**: 1.0
**Дата**: 2025-12-19
**Статус**: ✅ Production Ready
