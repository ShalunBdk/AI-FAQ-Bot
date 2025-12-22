# Changelog: Clarification & No Answer Detection

## [1.0.1] - 2025-12-19 (Bugfix)

### 🐛 Исправлено

**SearchResult.__init__() missing argument 'all_results'**
- **Проблема**: При создании `SearchResult` для `clarification` и `no_answer` не передавался обязательный параметр `all_results`
- **Ошибка**: `SearchResult.__init__() missing 1 required positional argument: 'all_results'`
- **Файлы**:
  - `src/bots/bot.py` (lines 700, 714)
  - `src/bots/b24_bot.py` (lines 650, 663)
- **Решение**: Добавлен `all_results=None` к конструкторам `SearchResult`

---

## [1.0.0] - 2025-12-19

### ✨ Добавлено

#### Новые Search Levels

**1. Clarification (Просьба уточнить)**
- `search_level='clarification'`
- Детектирует когда RAG просит уточнить слишком широкий вопрос
- Функция `is_rag_clarification()` проверяет ключевые фразы
- **НЕ считается** failed query
- Badge: `❓ Уточнение` (оранжевый)

**2. No Answer (Информация не найдена)**
- `search_level='no_answer'`
- Детектирует когда RAG не нашел информации в базе знаний
- Функция `is_rag_no_answer()` проверяет ключевые фразы + metadata.error
- **Считается** failed query
- Badge: `🚫 Не найдено` (красный)

#### Backend

**Боты** (`bot.py`, `b24_bot.py`):
- Новая функция `is_rag_clarification(answer_text: str) -> bool`
- Обновлённая функция `is_rag_no_answer(answer_text: str, metadata: dict) -> bool`
- Проверка типа RAG ответа с приоритетом (clarification > no_answer)

**База данных** (`database.py`):
- Обновлены SQL запросы для исключения `clarification` из failed queries:
  - `get_logs()` - line 725
  - `get_statistics()` - line 844
  - `get_period_statistics()` - line 1519
  - `get_failed_queries_for_period()` - line 1660
- Фильтр: `NOT IN ('disambiguation_shown', 'disambiguation', 'clarification')`

#### Frontend

**UI** (`logs.html`):
- Новые badges:
  - `❓ Уточнение` (оранжевый) для clarification
  - `🚫 Не найдено` (красный) для no_answer
- Обновлённая логика определения "no answer"
- Исключение clarification из failed queries фильтра

#### Документация

- **`CLAUDE.md`**: Добавлен раздел "Clarification & No Answer"
- **`docs/CLARIFICATION_NO_ANSWER_GUIDE.md`**: Полное руководство с примерами

---

## Примеры

### Clarification (Уточнение)

**Вход:**
```
Пользователь: "письмо"
```

**Выход:**
```
Бот: "Пожалуйста, уточните, какой именно вопрос у вас связан с письмом?
Например, вас интересует отправка письма, составление письма,
проблемы с получением писем или что-то другое?"
```

**Логирование:**
```sql
search_level = 'clarification'
faq_id = NULL
```

**UI:**
```
❓ Уточнение 🤖 RAG
```

---

### No Answer (Не найдено)

**Вход:**
```
Пользователь: "Как получить визу в Антарктиду?"
```

**Выход:**
```
Бот: "К сожалению, я не нашел информации о визе в Антарктиду.
Пожалуйста, обратитесь в отдел HR."
```

**Логирование:**
```sql
search_level = 'no_answer'
faq_id = NULL
```

**UI:**
```
🚫 Не найдено 🤖 RAG
```

---

## Изменённые файлы

### Боты
- `src/bots/bot.py`
  - Lines 426-451: Новая `is_rag_clarification()`
  - Lines 454-488: Обновлённая `is_rag_no_answer()`
  - Lines 697-723: Проверка типа RAG ответа

- `src/bots/b24_bot.py`
  - Lines 432-457: Новая `is_rag_clarification()`
  - Lines 460-494: Обновлённая `is_rag_no_answer()`
  - Lines 648-672: Проверка типа RAG ответа

### База данных
- `src/core/database.py`
  - Line 725: `get_logs()` - исключение clarification
  - Line 844: `get_statistics()` - исключение clarification
  - Line 1519: `get_period_statistics()` - исключение clarification
  - Line 1660: `get_failed_queries_for_period()` - исключение clarification

### Frontend
- `src/web/templates/admin/logs.html`
  - Lines 566-568: Новые badges для clarification и no_answer
  - Lines 614-622: Обновлённая логика "no answer"

### Документация
- `CLAUDE.md` (lines 172, 215-246)
- `docs/CLARIFICATION_NO_ANSWER_GUIDE.md` [NEW]

---

## SQL для проверки

```sql
-- Количество clarification
SELECT COUNT(*) as clarification_count
FROM answer_logs
WHERE search_level = 'clarification'
  AND period_id IS NULL;

-- Количество no_answer
SELECT COUNT(*) as no_answer_count
FROM answer_logs
WHERE search_level = 'no_answer'
  AND period_id IS NULL;

-- Распределение типов
SELECT
    search_level,
    COUNT(*) as count
FROM answer_logs
WHERE search_level IN ('clarification', 'no_answer', 'none')
  AND period_id IS NULL
GROUP BY search_level;
```

---

## Breaking Changes

**Нет.** Изменения обратно совместимы:
- Существующие search levels работают как прежде
- Новые levels добавлены, не заменяют старые
- SQL фильтры обновлены с обратной совместимостью

---

## Migration

**Не требуется.** Новые search levels появятся автоматически при следующих RAG генерациях.

---

**Версия**: 1.0.1
**Дата**: 2025-12-19
**Статус**: ✅ Production Ready
