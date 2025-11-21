# CLAUDE.md - AI Assistant Guide for AI-FAQ-Bot

> **Purpose**: Comprehensive context about the AI-FAQ-Bot codebase for AI assistants.

**Last Updated**: 2025-01-21
**Language**: Python 3.11
**Stack**: python-telegram-bot, ChromaDB, sentence-transformers, Flask, SQLite

---

## Project Overview

Multi-platform FAQ bot with **cascading search system** (4 levels) and semantic understanding.

### Key Features

- **Cascading Search (4 levels)**:
  - 🎯 Exact Match (100%) → 🔑 Keyword Search (70-95%) → 🧠 Semantic Search (45-70%) → ❌ Fallback
- **Multi-Platform**: Telegram + Bitrix24
- **Web Admin Panel**: FAQ management, analytics, settings
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
src/
├── core/
│   ├── database.py        # SQLite ORM, settings, logging
│   ├── search.py          # 🆕 Cascading search (4 levels)
│   └── logging_config.py  # UTC+7 logging
├── bots/
│   ├── bot.py             # Telegram bot (polling)
│   └── b24_bot.py         # Bitrix24 bot (webhook)
├── api/
│   └── b24_api.py         # Bitrix24 REST client
└── web/
    ├── web_admin.py       # Flask admin panel
    ├── middleware.py      # Auth & CORS
    ├── bitrix24_*.py      # OAuth, permissions
    └── templates/admin/   # HTML templates

scripts/
├── migrate_*.py           # Database migrations
├── test_cascade_search.py # Search system tests
└── demo_faq.py            # Demo data (21 FAQs)
```

---

## Core Components

### 1. Cascading Search (`src/core/search.py`)

**4-level search with automatic fallback:**

```
Level 1: EXACT MATCH    → 100% (normalized text comparison)
Level 2: KEYWORD SEARCH → 70-95% (short queries ≤5 words)
Level 3: SEMANTIC SEARCH → 45-70% (ChromaDB vectors)
Level 4: FALLBACK       → 0% (polite refusal)
```

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

**Icons**: 🎯 exact, 🔑 keyword, 🧠 semantic, 📄 direct

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
```

**Tables:**
- `faq` (id, category, question, answer, keywords)
- `query_logs` (user_id, username, query_text, platform, timestamp)
- `answer_logs` (query_log_id, faq_id, similarity_score, answer_shown, search_level)
- `rating_logs` (answer_log_id, user_id, rating)
- `bot_settings` (key, value)
- `bitrix24_permissions` (domain, user_id, role)

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
- `GET/POST /admin/settings` - Bot settings
- `POST /admin/retrain` - Rebuild ChromaDB + notify bots
- `GET /admin/api/search-level-stats` - Cascade search statistics

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

### Add new setting
1. Add to `DEFAULT_BOT_SETTINGS` in `database.py`
2. Add UI field in `settings.html`
3. Use: `get_bot_setting("key")`

### Run cascade search tests
```bash
source venv/Scripts/activate
python scripts/test_cascade_search.py
```

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
docker-compose --profile telegram up -d        # Telegram
docker-compose --profile bitrix24 up -d        # Bitrix24
docker-compose --profile telegram --profile bitrix24 up -d  # All
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

**DON'T:**
- ❌ Store UTC+7 directly (store UTC)
- ❌ Modify schema without migration script
- ❌ Update FAQs without retraining ChromaDB
- ❌ Use `time.sleep()` in async functions

---

**Document Version**: 2.0 (Cascading Search)
