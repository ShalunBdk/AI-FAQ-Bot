# CLAUDE.md - AI Assistant Guide for AI-FAQ-Bot

> **Purpose**: Comprehensive context about the AI-FAQ-Bot codebase for AI assistants.

**Last Updated**: 2025-12-18
**Language**: Python 3.11
**Stack**: python-telegram-bot, ChromaDB, sentence-transformers, pymorphy3, Flask, SQLite, OpenRouter API
**Semantic Model**: deepvk/USER2-base (Russian-optimized, 8K context, with task-specific prefixes)
**RAG**: OpenRouter API (GPT-4, Claude, Gemini) with Privacy First anonymization

---

## Project Overview

Multi-platform FAQ bot with **cascading search system** (4 levels) and semantic understanding.

### Key Features

- **Cascading Search (4 levels) + RAG**:
  - 🎯 Exact Match (100%) → 🔑 Keyword Search with Lemmatization (70-95%) → 🧠 Semantic Search (45-70%) → ❌ Fallback
  - Automatic word form recognition (претензию, претензии → претензия)
  - 🤖 **RAG Generation** (optional): Smart answer generation via LLM after search
- **Privacy First RAG**:
  - 🔒 PII Anonymization before sending to LLM (emails, phones, names, orgs, locations)
  - 🤖 Answer generation via OpenRouter API (GPT-4, Claude, Gemini, etc.)
  - 🔓 Deanonymization of LLM responses back to original data
  - 📊 Combining information from multiple FAQs into coherent answer
- **Disambiguation (Уточнение)**:
  - 🔀 Automatic detection of ambiguous queries (when multiple FAQs have similar confidence)
  - ✅ User selects the correct FAQ from presented options
  - Full logging: both the display of options and user selection
- **Multi-Platform**: Telegram + Bitrix24
- **Web Admin Panel**: FAQ management, analytics, settings, keyword optimization
- **Bitrix24 Integration**: OAuth 2.0, iframe embedding, role-based access
- **Hot Reload**: Update FAQ without restarting bots
- **Analytics**: Query logs, similarity scores, search levels, user feedback

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              User Interfaces                            │
├─────────────┬─────────────┬────────────────────────────┤
│ Telegram    │ Bitrix24    │ Web Admin                  │
│ (port 5001) │ (port 5002) │ (port 5000)                │
└──────┬──────┴──────┬──────┴─────────┬──────────────────┘
       └─────────────┴────────────────┘
                     │
       ┌─────────────┴─────────────────┐
       │   Core Search & RAG Layer     │
       │  Cascading Search → LLM       │
       │  Privacy First (Anonymization)│
       └─────────────┬─────────────────┘
                     │
       ┌─────────────┴─────────────────┐
       │     Shared Data Layer         │
       │  SQLite + ChromaDB            │
       └─────────────┬─────────────────┘
                     │
       ┌─────────────┴─────────────────┐
       │   External Services           │
       │  OpenRouter API (LLM)         │
       └───────────────────────────────┘
```

---

## Directory Structure

```
FAQBot/
├── Dockerfile                     # Docker образ (Python 3.11 + Node.js)
├── docker-compose.dev.yml         # Development конфигурация
├── docker-compose.production.yml  # Production конфигурация (Bitrix24)
├── nginx.conf.example             # Nginx конфиг для Bitrix24
├── docker.env.production          # Шаблон .env для продакшена
├── README.md                      # Основная документация
├── CLAUDE.md                      # AI-инструкции (этот файл)
├── DEPLOY-BITRIX24.md            # Гайд по развертыванию
├── PRODUCTION-CHECKLIST.md       # Чеклист перед деплоем
│
├── src/
│   ├── core/
│   │   ├── database.py        # SQLite ORM, settings, logging
│   │   ├── search.py          # Cascading search (4 levels)
│   │   ├── llm_service.py     # RAG: LLM generation via OpenRouter
│   │   ├── pii_anonymizer.py  # RAG: Privacy First anonymization
│   │   └── logging_config.py  # UTC+7 logging
│   ├── bots/
│   │   ├── bot.py             # Telegram bot (опциональный)
│   │   └── b24_bot.py         # Bitrix24 bot (основной)
│   ├── api/
│   │   └── b24_api.py         # Bitrix24 REST client
│   └── web/
│       ├── web_admin.py       # Flask admin panel
│       ├── middleware.py      # Auth & CORS
│       ├── bitrix24_*.py      # OAuth, permissions
│       └── templates/admin/   # HTML templates
│
├── scripts/
│   ├── migrate_*.py           # Database migrations
│   ├── test_cascade_search.py # Search system tests
│   ├── test_rag_pipeline.py   # RAG pipeline tests
│   ├── demo_faq.py            # Demo data (21 FAQs)
│   └── register_bot.py        # Регистрация в Bitrix24
│
├── docs/                      # Техническая документация
│   ├── RAG_GUIDE.md           # RAG (Privacy First) guide
│   ├── QUICKSTART_RAG.md      # RAG quick start
│   ├── DEPLOYMENT.md
│   ├── DOCKER.md
│   ├── QUICKSTART.md
│   ├── DOCKER-CPU-OPTIMIZATION.md
│   ├── REVERSE-PROXY-SETUP.md
│   └── migrations/            # История миграций БД
│
├── nginx/                     # Альтернативные nginx конфиги
│   └── README.md
│
├── .dockerignore              # Docker build ignore rules
└── docker-compose.override.yml.example  # Пример для кастомизации
```

---

## Core Components

### 1. Cascading Search (`src/core/search.py`)

**4-level search with automatic fallback:**

```
Level 1: EXACT MATCH    → 100% (normalized text comparison)
Level 2: KEYWORD SEARCH → 70-95% (short queries ≤5 words, with lemmatization)
Level 3: SEMANTIC SEARCH → 45-70% (ChromaDB vectors with deepvk/USER2-base)
Level 4: FALLBACK       → 0% (polite refusal)
```

**Semantic Model (deepvk/USER2-base):**
- **Russian-optimized** transformer (149M parameters) from deepvk
- **Long context support**: 8,192 tokens (vs 512 in old model)
- **Task-specific prefixes**: Uses `search_query:` and `search_document:` for optimal retrieval
- **Improved accuracy**: Better understanding of rephrased questions and typos
- **Usage**:
  - Queries: `collection.query(query_texts=[f"search_query: {text}"])`
  - Documents: `documents.append(f"search_document: {text}")`
- **Note**: All documents in ChromaDB must be re-indexed after model change

**Lemmatization (pymorphy3):**
- Automatic word form normalization (претензию, претензии → претензия)
- Applied to both user queries and FAQ keywords
- Functions: `lemmatize_word()`, `lemmatize_text()`, `extract_keywords()`
- Reduces need for manual word form variants

**Main function:**
```python
from src.core.search import find_answer, SearchResult

result = find_answer(query_text, collection, settings)
# Returns: SearchResult(found, faq_id, question, answer, confidence, search_level, ...)
```

**Settings** (in `bot_settings` table):
- `exact_match_threshold`: "95"
- `keyword_match_threshold`: "70"
- `semantic_match_threshold`: "45"
- `keyword_search_max_words`: "5"
- `fallback_message`: "..."

**Icons**: 🎯 exact, 🔑 keyword, 🧠 semantic, 🔀 disambiguation_shown, ✅ disambiguation, 📄 direct, ❌ none

**Disambiguation (Разрешение неоднозначностей):**

When multiple FAQs have similar confidence scores (difference < 7%), the system enters disambiguation mode:

1. **Detection Logic** (`src/core/search.py`):
   - Triggered when top-2 results have confidence difference < 7%
   - Returns `SearchResult` with `ambiguous=True` and `alternatives` list
   - Works for both keyword search and semantic search levels
   - **Limits**: Max 3 alternatives, only variants within 12% from top result

2. **User Interaction** (both platforms):
   - Bot sends message: "Найдено несколько подходящих вопросов. Выберите нужный:"
   - Shows buttons with FAQ questions (without confidence %) for clean UX
   - User clicks button to select the correct FAQ

3. **Logging** (with real confidence):
   - **Step 1**: `search_level='disambiguation_shown'`, `faq_id=NULL` - options presented with confidence %
     - Example: `- [83.6%] Проблема с картриджем\n- [74.3%] Проблемы с принтером`
   - **Step 2**: `search_level='disambiguation'`, `faq_id=selected`, `confidence=real_value` - user choice
     - **Important**: Uses REAL confidence from search (not 100%), e.g., 83.6%
   - Both steps linked via `query_log_id`

4. **UI Behavior**:
   - **Bitrix24**: Message is EDITED to show selected FAQ (no "Message deleted" stub)
   - **Telegram**: Message is edited to show selected FAQ (removes buttons)
   - **Admin logs**:
     - `disambiguation_shown` hidden if user selected
     - Click on "🔀 Показаны варианты для выбора" expands details with confidence %

5. **Analytics**:
   - Disambiguation is **excluded** from "no answer" / "failed queries" statistics
   - Tracked separately in search level distribution
   - Functions updated: `get_logs()`, `get_statistics()`, `get_period_statistics()`, `get_failed_queries_for_period()`

**Implementation Files**:
- `src/core/search.py`: Detection logic (lines 327-566)
- `src/bots/bot.py`: Telegram UI (lines 467-500, 671-731)
- `src/bots/b24_bot.py`: Bitrix24 UI (lines 484-516, 815-868)
- `src/web/templates/admin/logs.html`: Frontend filtering (lines 441-464)
- `src/core/database.py`: SQL exclusions (lines 626, 717-724, 1373-1381, 1518-1520)

### 2. RAG (Retrieval-Augmented Generation) (`src/core/llm_service.py` + `src/core/pii_anonymizer.py`)

**Privacy First RAG architecture with PII anonymization:**

```
User Query → Cascading Search → [RAG ENABLED?]
                                      ↓
                         1. Prepare context from found FAQs
                         2. Anonymize PII (PiiAnonymizer)
                         3. Send to LLM (OpenRouter API)
                         4. Deanonymize response
                         5. Return to user
```

**Key Components:**

#### PiiAnonymizer (`src/core/pii_anonymizer.py`)

**Purpose:** Protect personal data before sending to cloud LLM.

**Anonymization layers:**
1. **BB-code URLs** (regex) - `[URL=...]text[/URL]` → `[URL_1]` (protects employee profiles)
2. **Emails** (regex) - `ivan@example.com` → `[EMAIL_1]`
3. **Phones** (regex) - `+7 (999) 123-45-67` → `[PHONE_1]`
4. **NER (natasha)** - DISABLED (too many false positives, protected via BB URL anonymization)

**Usage:**
```python
from src.core.pii_anonymizer import PiiAnonymizer

anonymizer = PiiAnonymizer()
anonymized, mapping = anonymizer.anonymize("Звоните Ивану: ivan@corp.com")
# anonymized: "Звоните [PER_1]: [EMAIL_1]"
# mapping: {"[PER_1]": "Ивану", "[EMAIL_1]": "ivan@corp.com"}

original = anonymizer.deanonymize(anonymized, mapping)
# original: "Звоните Ивану: ivan@corp.com"
```

#### LLMService (`src/core/llm_service.py`)

**Purpose:** Generate smart answers via LLM with anonymization.

**Features:**
- OpenRouter API integration (access to GPT-4, Claude, Gemini, etc.)
- Automatic PII anonymization/deanonymization
- Context preparation from multiple FAQs
- Customizable system prompt with department routing
- Token usage tracking

**Main method:**
```python
from src.core.llm_service import LLMService

service = LLMService()
answer, metadata = service.generate_answer(
    user_question="Как связаться с бухгалтерией?",
    db_chunks=[
        {
            'question': 'Контакты бухгалтерии',
            'answer': 'Бухгалтерия: Мария, тел. +7 495 123-45-67',
            'confidence': 92.3
        }
    ],
    max_tokens=1024,
    temperature=0.3
)
# Returns: (generated_answer, metadata with tokens/pii info)
```

**System Prompt highlights:**
- Uses department routing knowledge base (23 departments)
- Strict rules: answer only from context, don't hallucinate
- Preserves placeholders (`[PER_1]`, `[EMAIL_1]`) as-is
- Builds logical conclusions from context

**Integration in bots:**
- `src/bots/bot.py` (Telegram): lines 527-596
- `src/bots/b24_bot.py` (Bitrix24): lines 481-559
- Triggered AFTER cascading search finds results
- Automatic fallback to regular answer on LLM errors
- When RAG enabled, disambiguation bypassed (LLM combines multiple FAQs)

**Configuration (.env):**
```env
RAG_ENABLED=true                     # enable/disable RAG
OPENROUTER_API_KEY=sk-or-v1-xxx     # OpenRouter API key
OPENROUTER_MODEL=openai/gpt-4o-mini # LLM model
RAG_MAX_TOKENS=1024                  # max tokens in response
RAG_TEMPERATURE=0.3                  # generation temperature (0.0-1.0)
RAG_MIN_RELEVANCE_SCORE=45.0         # min confidence to use RAG
RAG_MAX_CHUNKS=5                     # max FAQs in context
```

**Recommended models:**
- `google/gemini-2.0-flash-001` - FREE, good quality
- `openai/gpt-4o-mini` - $0.15/$0.60 per 1M tokens (production recommended)
- `openai/gpt-4o` - $2.50/$10.00 per 1M tokens (high quality)
- `anthropic/claude-3.5-sonnet` - $3.00/$15.00 per 1M tokens

**Testing:**
```bash
python scripts/test_rag_pipeline.py
```

See `docs/RAG_GUIDE.md` for complete documentation.

### 3. Database (`src/core/database.py`)

**Key functions:**
```python
# FAQ
get_all_faqs(), get_faq_by_id(id), add_faq(...), update_faq(...), delete_faq(id)

# Logging
add_query_log(user_id, username, query_text, platform) → int
add_answer_log(query_log_id, faq_id, similarity, answer, search_level) → int
add_rating_log(answer_log_id, user_id, rating) → int

# Settings
get_bot_setting(key), update_bot_setting(key, value), get_bot_settings() → Dict

# Analytics
get_logs(filters), get_statistics(filters), get_search_level_statistics()

# Test Periods
create_test_period(name, description) → int
end_test_period(period_id) → bool
get_test_periods() → List[Dict]
get_active_test_period() → Dict
archive_current_logs(period_id) → Dict
clear_unarchived_logs() → Dict
get_period_statistics(period_id) → Dict
get_failed_queries_for_period(period_id, limit) → List[Dict]
```

**Tables:**
- `faq` (id, category, question, answer, keywords)
- `query_logs` (user_id, username, query_text, platform, timestamp, period_id)
- `answer_logs` (query_log_id, faq_id, similarity_score, answer_shown, search_level, period_id)
- `rating_logs` (answer_log_id, user_id, rating, period_id)
- `bot_settings` (key, value)
- `bitrix24_permissions` (domain, user_id, role)
- `test_periods` (id, name, description, start_date, end_date, status)

**Note on RAG:** RAG-generated answers are stored in `answer_logs.answer_shown` field. Search level remains original (exact/keyword/semantic), not "rag".

### 4. Bots

**Telegram** (`src/bots/bot.py`):
- Long-polling + Flask reload server (port 5001)
- User-level rate limiting, callback debouncing
- `POST /reload` - hot reload ChromaDB

**Bitrix24** (`src/bots/b24_bot.py`):
- Webhook-based Flask app (port 5002)
- Events: `ONIMBOTMESSAGEADD`, `ONIMCOMMANDADD`, `ONIMBOTJOINCHAT`
- BB-code formatting for messages

**RAG Integration (both bots):**
- Triggered after cascading search finds result (confidence >= RAG_MIN_RELEVANCE_SCORE)
- Ленивая инициализация LLM сервиса при первом использовании
- Automatic fallback to regular answer on errors
- When disambiguation detected and RAG enabled → uses all alternatives for context

### 5. Web Admin (`src/web/web_admin.py`)

**Routes:**
- `GET/POST /admin/` - FAQ management
- `GET /admin/logs` - Analytics
- `GET /admin/test-periods` - Test periods management & statistics
- `GET/POST /admin/settings` - Bot settings
- `POST /admin/retrain` - Rebuild ChromaDB + notify bots
- `POST /admin/api/optimize-keywords` - Lemmatize and deduplicate keywords
- `GET /admin/api/search-level-stats` - Cascade search statistics
- `GET /admin/api/test-periods/list` - Get all test periods
- `POST /admin/api/test-periods/create` - Create new test period
- `POST /admin/api/test-periods/{id}/end` - End test period
- `POST /admin/api/test-periods/{id}/archive` - Archive logs
- `GET /admin/api/test-periods/{id}/statistics` - Get period statistics
- `GET /admin/api/test-periods/{id}/export?format=excel|json|csv` - Export report
- `GET /admin/api/test-periods/{id}/failed-queries` - Get failed queries

**UI Features:**
- "Optimize" button in FAQ form - automatically removes duplicate word forms
- Toast notifications for user feedback
- Keyword optimization statistics display

**Static Assets:**
- Uses local Tailwind CSS (no CDN)
- Local fonts: Inter, Material Symbols Outlined
- Build: `npm run build:css` → `src/web/static/css/output.css`
- Watch mode: `npm run watch:css`
- See `README_ASSETS.md` for details

---

## Code Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Modules | snake_case | `web_admin.py` |
| Classes | PascalCase | `SearchResult` |
| Functions | snake_case | `find_answer()` |
| Constants | UPPER_SNAKE | `SIMILARITY_THRESHOLD` |
| DB tables | snake_case | `query_logs` |

**Comments**: Russian for business logic, English docstrings.

**Error handling**: Always use `get_db_connection()` context manager, `safe_send_message()` wrapper.

---

## Common Tasks

### Add FAQ
```python
from src.core.database import add_faq
from src.web.web_admin import retrain_chromadb, notify_bot_reload

add_faq(category, question, answer, keywords)
retrain_chromadb()
notify_bot_reload()
```

### Optimize keywords programmatically
```python
from src.core.search import lemmatize_word

keywords = ["претензию", "претензии", "товар", "товары"]
optimized = list(dict.fromkeys([lemmatize_word(kw) for kw in keywords]))
# Result: ["претензия", "товар"]
```

Or use the web UI "Optimize" button in FAQ form.

### Test disambiguation behavior
```python
from src.core.search import find_answer

# Create two FAQs with overlapping keywords for testing
# FAQ 1: "Проблемы с электронной почтой" - keywords: "письмо, почта, email"
# FAQ 2: "Как отправить письмо почтой России" - keywords: "письмо, почта, отправка"

# Query that triggers disambiguation
result = find_answer("письмо почтой", collection, settings)

# Check if disambiguation was triggered
if result.ambiguous:
    print(f"Disambiguation triggered! {len(result.alternatives)} alternatives:")
    for alt in result.alternatives:
        print(f"  - {alt['question']} ({alt['confidence']:.1f}%)")
    # Bot will show buttons for user to choose
```

**Note**: Disambiguation is triggered when:
- Top-2 results have confidence difference < 15%
- Applies to both keyword and semantic search levels
- User selection is logged as `search_level='disambiguation'`

### Add new setting
1. Add to `DEFAULT_BOT_SETTINGS` in `database.py`
2. Add UI field in `settings.html`
3. Use: `get_bot_setting("key")`

### Run cascade search tests
```bash
source venv/Scripts/activate
python scripts/test_cascade_search.py
```

### Manage test periods
```python
from src.core.database import (
    create_test_period, end_test_period,
    archive_current_logs, clear_unarchived_logs,
    get_period_statistics
)

# Create test period
period_id = create_test_period("Тестовая группа #1", "Описание")

# During testing, logs are automatically linked to active period

# Archive logs
archive_current_logs(period_id)

# End period
end_test_period(period_id)

# Get statistics
stats = get_period_statistics(period_id)

# Clear unarchived logs (before production launch)
clear_unarchived_logs()
```

See `docs/TEST_PERIODS_GUIDE.md` for detailed workflow.

### Database Migrations
**Все таблицы создаются автоматически** при первом запуске через `init_database()`.

Миграции в `scripts/migrate_*.py` нужны только для:
- Обновления **существующих** баз (добавления новых колонок/таблиц)
- Разработки (history изменений схемы)

При новом развёртывании миграции **не требуются**.

---

## Configuration

### Environment (.env)
```env
# Required
TELEGRAM_TOKEN=...

# Semantic Model (IMPORTANT: Change requires ChromaDB re-indexing)
MODEL_NAME=deepvk/USER2-base
SIMILARITY_THRESHOLD=45

# Bitrix24
BITRIX24_WEBHOOK=https://...
BITRIX24_BOT_ID=62
BITRIX24_CLIENT_ID=...

# RAG (Optional - for smart answer generation)
RAG_ENABLED=true
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_MODEL=openai/gpt-4o-mini
RAG_MAX_TOKENS=1024
RAG_TEMPERATURE=0.3
RAG_MIN_RELEVANCE_SCORE=45.0
RAG_MAX_CHUNKS=5
```

### Cascade Search Settings (bot_settings table)
| Key | Default | Description |
|-----|---------|-------------|
| exact_match_threshold | 95 | Exact match minimum |
| keyword_match_threshold | 70 | Keyword search minimum |
| semantic_match_threshold | 45 | Semantic search minimum |
| keyword_search_max_words | 5 | Max words for keyword search |
| fallback_message | ... | Custom fallback text |

### RAG Settings (.env variables)
| Key | Default | Description |
|-----|---------|-------------|
| RAG_ENABLED | true | Enable/disable RAG generation |
| OPENROUTER_API_KEY | - | OpenRouter API key (REQUIRED if RAG enabled) |
| OPENROUTER_MODEL | openai/gpt-4o-mini | LLM model to use |
| RAG_MAX_TOKENS | 1024 | Max tokens in LLM response |
| RAG_TEMPERATURE | 0.3 | Generation temperature (0.0-1.0) |
| RAG_MIN_RELEVANCE_SCORE | 45.0 | Min confidence to trigger RAG |
| RAG_MAX_CHUNKS | 5 | Max FAQs in context |

---

## Quick Reference

### Ports
| Service | Port | Endpoint |
|---------|------|----------|
| Web Admin | 5000 | http://localhost:5000 |
| Telegram Bot | 5001 | /reload |
| Bitrix24 Bot | 5002 | /webhook/bitrix24 |

### Key Files
| Purpose | File |
|---------|------|
| Cascading search | `src/core/search.py` |
| RAG LLM service | `src/core/llm_service.py` |
| RAG PII anonymization | `src/core/pii_anonymizer.py` |
| Database ORM | `src/core/database.py` |
| Telegram bot | `src/bots/bot.py` |
| Bitrix24 bot | `src/bots/b24_bot.py` |
| Web admin | `src/web/web_admin.py` |

### Docker
```bash
# Development (все сервисы)
docker-compose -f docker-compose.dev.yml up -d

# Production (только Bitrix24)
docker-compose -f docker-compose.production.yml up -d

# Production с Telegram (опционально)
docker-compose -f docker-compose.production.yml --profile telegram up -d
```

---

## Important Constraints

1. **SQLite is single-writer** - use transactions carefully
2. **ChromaDB must be synced** - always call `retrain_chromadb()` + `notify_bot_reload()` after FAQ changes
3. **Timezone**: Store UTC, display UTC+7 via `convert_utc_to_utc7()`
4. **Platform field required**: 'telegram', 'bitrix24', or 'web' in all logs
5. **Keywords are comma-separated strings** (not JSON)

---

## AI Assistant Guidelines

**DO:**
- ✅ Use Russian comments for business logic
- ✅ Call `retrain_chromadb()` + `notify_bot_reload()` after FAQ changes
- ✅ Use `get_db_connection()` context manager
- ✅ Log with `search_level` parameter in `add_answer_log()`
- ✅ Test both Telegram and Bitrix24 after changes
- ✅ Use lemmatized keywords (base forms) instead of listing all variants
- ✅ Exclude `disambiguation_shown` and `disambiguation` from "no answer" / "failed queries" filters
- ✅ Use `search_query:` prefix for queries and `search_document:` for documents (deepvk/USER2-base)
- ✅ Save REAL confidence in disambiguation logs (not 100%)
- ✅ Use RAG for improving answer quality when confidence >= RAG_MIN_RELEVANCE_SCORE
- ✅ Always anonymize PII before sending to LLM (automatic in LLMService)
- ✅ Test RAG pipeline with `scripts/test_rag_pipeline.py`

**DON'T:**
- ❌ Store UTC+7 directly (store UTC)
- ❌ Modify schema without migration script
- ❌ Update FAQs without retraining ChromaDB
- ❌ Use `time.sleep()` in async functions
- ❌ Add all word forms manually (use lemmatization)
- ❌ Count disambiguation as failed queries in statistics
- ❌ Forget prefixes when using deepvk/USER2-base model
- ❌ Send raw PII to LLM (always use LLMService which handles anonymization)
- ❌ Hardcode OpenRouter API key (use environment variable)
- ❌ Use RAG for low-confidence results (< RAG_MIN_RELEVANCE_SCORE)

---

**Document Version**: 3.0 (deepvk/USER2-base + Improved Disambiguation + Enhanced Logging + Privacy First RAG)
