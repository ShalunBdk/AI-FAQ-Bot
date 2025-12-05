# CLAUDE.md - AI Assistant Guide for AI-FAQ-Bot

> **Purpose**: Comprehensive context about the AI-FAQ-Bot codebase for AI assistants.

**Last Updated**: 2025-01-05
**Language**: Python 3.11
**Stack**: python-telegram-bot, ChromaDB, sentence-transformers, pymorphy3, Flask, SQLite

---

## Project Overview

Multi-platform FAQ bot with **cascading search system** (4 levels) and semantic understanding.

### Key Features

- **Cascading Search (4 levels)**:
  - 🎯 Exact Match (100%) → 🔑 Keyword Search with Lemmatization (70-95%) → 🧠 Semantic Search (45-70%) → ❌ Fallback
  - Automatic word form recognition (претензию, претензии → претензия)
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
       ┌─────────────┴─────────────┐
       │     Shared Data Layer     │
       │  SQLite + ChromaDB        │
       └───────────────────────────┘
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
│   ├── demo_faq.py            # Demo data (21 FAQs)
│   └── register_bot.py        # Регистрация в Bitrix24
│
├── docs/                      # Техническая документация
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
Level 3: SEMANTIC SEARCH → 45-70% (ChromaDB vectors)
Level 4: FALLBACK       → 0% (polite refusal)
```

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

When multiple FAQs have similar confidence scores (difference < 15%), the system enters disambiguation mode:

1. **Detection Logic** (`src/core/search.py`):
   - Triggered when top-2 results have confidence difference < 15%
   - Returns `SearchResult` with `ambiguous=True` and `alternatives` list
   - Works for both keyword search and semantic search levels

2. **User Interaction** (both platforms):
   - Bot sends message: "Найдено несколько подходящих вопросов. Выберите нужный:"
   - Shows buttons with FAQ questions (up to 5 alternatives)
   - User clicks button to select the correct FAQ

3. **Logging**:
   - **Step 1**: `search_level='disambiguation_shown'`, `faq_id=NULL` - options presented
   - **Step 2**: `search_level='disambiguation'`, `faq_id=selected`, `confidence=100.0` - user choice
   - Both steps linked via `query_log_id`

4. **UI Behavior**:
   - **Bitrix24**: Original message with buttons is deleted after selection
   - **Telegram**: Message is edited to show selected FAQ (removes buttons)
   - **Admin logs**: Only final selection shown (disambiguation_shown hidden if user chose)

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

### 2. Database (`src/core/database.py`)

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

### 3. Bots

**Telegram** (`src/bots/bot.py`):
- Long-polling + Flask reload server (port 5001)
- User-level rate limiting, callback debouncing
- `POST /reload` - hot reload ChromaDB

**Bitrix24** (`src/bots/b24_bot.py`):
- Webhook-based Flask app (port 5002)
- Events: `ONIMBOTMESSAGEADD`, `ONIMCOMMANDADD`, `ONIMBOTJOINCHAT`
- BB-code formatting for messages

### 4. Web Admin (`src/web/web_admin.py`)

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

# Optional
MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
SIMILARITY_THRESHOLD=45

# Bitrix24
BITRIX24_WEBHOOK=https://...
BITRIX24_BOT_ID=62
BITRIX24_CLIENT_ID=...
```

### Cascade Search Settings (bot_settings table)
| Key | Default | Description |
|-----|---------|-------------|
| exact_match_threshold | 95 | Exact match minimum |
| keyword_match_threshold | 70 | Keyword search minimum |
| semantic_match_threshold | 45 | Semantic search minimum |
| keyword_search_max_words | 5 | Max words for keyword search |
| fallback_message | ... | Custom fallback text |

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

**DON'T:**
- ❌ Store UTC+7 directly (store UTC)
- ❌ Modify schema without migration script
- ❌ Update FAQs without retraining ChromaDB
- ❌ Use `time.sleep()` in async functions
- ❌ Add all word forms manually (use lemmatization)
- ❌ Count disambiguation as failed queries in statistics

---

**Document Version**: 2.2 (Cascading Search + Lemmatization + Disambiguation)
