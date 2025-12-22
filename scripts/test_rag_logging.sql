-- Скрипт для проверки RAG логирования
-- Запускать через: sqlite3 faq_bot.db < scripts/test_rag_logging.sql

-- 1. Проверить структуру таблицы llm_generations
.headers on
.mode column

SELECT '=== СТРУКТУРА ТАБЛИЦЫ llm_generations ===' as info;
PRAGMA table_info(llm_generations);

-- 2. Проверить индексы
SELECT '=== ИНДЕКСЫ ===' as info;
SELECT name, sql FROM sqlite_master
WHERE type='index' AND tbl_name='llm_generations';

-- 3. Проверить все RAG записи
SELECT '=== ВСЕ RAG ЗАПИСИ ===' as info;
SELECT
    id,
    answer_log_id,
    model,
    chunks_used,
    pii_detected,
    tokens_total,
    generation_time_ms,
    error_message,
    created_at
FROM llm_generations
ORDER BY created_at DESC
LIMIT 10;

-- 4. Проверить JOIN с answer_logs
SELECT '=== JOIN С ANSWER_LOGS (последние 10) ===' as info;
SELECT
    al.id as answer_log_id,
    ql.query_text,
    al.search_level,
    al.similarity_score,
    lg.model,
    lg.chunks_used,
    lg.tokens_total,
    lg.generation_time_ms,
    lg.error_message
FROM answer_logs al
LEFT JOIN llm_generations lg ON al.id = lg.answer_log_id
LEFT JOIN query_logs ql ON al.query_log_id = ql.id
WHERE lg.id IS NOT NULL
ORDER BY al.timestamp DESC
LIMIT 10;

-- 5. Статистика RAG
SELECT '=== СТАТИСТИКА RAG ===' as info;
SELECT
    COUNT(*) as total_rag_answers,
    AVG(tokens_total) as avg_tokens,
    SUM(tokens_total) as total_tokens,
    AVG(chunks_used) as avg_chunks,
    AVG(generation_time_ms) as avg_gen_time_ms,
    COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as errors,
    COUNT(DISTINCT model) as unique_models
FROM llm_generations
WHERE answer_log_id IN (
    SELECT id FROM answer_logs WHERE period_id IS NULL
);

-- 6. Распределение по моделям
SELECT '=== РАСПРЕДЕЛЕНИЕ ПО МОДЕЛЯМ ===' as info;
SELECT
    model,
    COUNT(*) as count,
    ROUND(AVG(tokens_total), 1) as avg_tokens,
    ROUND(AVG(generation_time_ms), 0) as avg_time_ms
FROM llm_generations
WHERE answer_log_id IN (
    SELECT id FROM answer_logs WHERE period_id IS NULL
)
GROUP BY model
ORDER BY count DESC;

-- 7. Проверка chunks_data (первая запись)
SELECT '=== ПРИМЕР CHUNKS_DATA (JSON) ===' as info;
SELECT
    id,
    answer_log_id,
    chunks_data
FROM llm_generations
WHERE chunks_data IS NOT NULL
LIMIT 1;

-- 8. Ошибки RAG (если есть)
SELECT '=== ОШИБКИ RAG ===' as info;
SELECT
    lg.id,
    lg.answer_log_id,
    lg.model,
    lg.error_message,
    lg.created_at,
    ql.query_text
FROM llm_generations lg
LEFT JOIN answer_logs al ON lg.answer_log_id = al.id
LEFT JOIN query_logs ql ON al.query_log_id = ql.id
WHERE lg.error_message IS NOT NULL
ORDER BY lg.created_at DESC
LIMIT 5;
