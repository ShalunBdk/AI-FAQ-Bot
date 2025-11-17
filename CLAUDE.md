# CLAUDE.md - AI Assistant Guide for AI-FAQ-Bot

> **Purpose**: This document provides AI assistants with comprehensive context about the AI-FAQ-Bot codebase, including architecture, conventions, workflows, and best practices.

**Last Updated**: 2025-11-14
**Repository**: AI-FAQ-Bot
**Primary Language**: Python 3.11
**Main Technologies**: python-telegram-bot, ChromaDB, sentence-transformers, Flask, SQLite

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Directory Structure](#directory-structure)
4. [Core Components](#core-components)
5. [Development Workflows](#development-workflows)
6. [Code Conventions](#code-conventions)
7. [Common Tasks](#common-tasks)
8. [Database Schema](#database-schema)
9. [Configuration Management](#configuration-management)
10. [Testing & Debugging](#testing--debugging)
11. [Important Constraints](#important-constraints)
12. [Deployment](#deployment)

---

## Project Overview

### What is AI-FAQ-Bot?

A production-ready, multi-platform FAQ bot that uses **semantic search** to answer user questions intelligently. The bot understands the meaning of questions (not just keywords) using vector embeddings.

### Key Features

- **Semantic Search**: Uses sentence-transformers + ChromaDB for understanding question intent
- **Multi-Platform**: Supports Telegram and Bitrix24 simultaneously
- **Web Admin Panel**: Flask-based interface for FAQ management, analytics, and settings
- **Hot Reload**: Update FAQ database without restarting bots
- **Comprehensive Analytics**: Tracks queries, responses, similarity scores, and user feedback
- **Anti-Spam Protection**: User-level rate limiting, callback debouncing, global bot protection
- **Timezone Support**: All logs displayed in UTC+7, stored in UTC

### Architecture Principles

1. **Separation of Concerns**: Core logic, bots, API clients, and web interface are isolated
2. **Shared Data Layer**: SQLite + ChromaDB shared across all services
3. **Hot-Reload Mechanism**: Web admin can trigger bots to reload knowledge base via HTTP
4. **Event-Driven**: Bots operate independently, reacting to platform events
5. **Defensive Programming**: Extensive error handling, retries, and graceful degradation

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                         │
├────────────────┬──────────────────┬────────────────────────┤
│  Telegram Bot  │  Bitrix24 Bot   │   Web Admin Panel      │
│   (port 5001)  │   (port 5002)   │      (port 5000)       │
└────────┬───────┴────────┬─────────┴──────────┬─────────────┘
         │                │                    │
         └────────────────┴────────────────────┘
                          │
         ┌────────────────┴────────────────────┐
         │         Shared Data Layer           │
         │  ┌──────────────┬────────────────┐  │
         │  │ SQLite DB    │   ChromaDB     │  │
         │  │ (metadata,   │   (vector      │  │
         │  │  logs,       │    embeddings) │  │
         │  │  settings)   │                │  │
         │  └──────────────┴────────────────┘  │
         └─────────────────────────────────────┘
```

### Service Communication

```
Web Admin (Flask)
    │
    ├─── Direct DB Access ──→ SQLite + ChromaDB
    │
    └─── Hot Reload ──→ POST /reload ──→ Telegram Bot
                   └──→ POST /api/reload-chromadb ──→ Bitrix24 Bot

User Query Flow:
User → Bot → ChromaDB.query() → Calculate Similarity → Apply Threshold → Log to SQLite → Response
                                                              │
                                                              └──→ Analytics Dashboard
```

---

## Directory Structure

```
AI-FAQ-Bot/
├── src/                          # Main source code
│   ├── core/                     # Core functionality
│   │   ├── database.py          # SQLite ORM & business logic
│   │   └── logging_config.py    # Logging setup (UTC+7 formatter)
│   ├── bots/                     # Bot implementations
│   │   ├── bot.py               # Telegram bot (polling + reload server)
│   │   └── b24_bot.py           # Bitrix24 bot (webhook-based)
│   ├── api/                      # External integrations
│   │   └── b24_api.py           # Bitrix24 REST API client
│   └── web/                      # Web interface
│       ├── web_admin.py         # Flask admin panel
│       └── templates/           # HTML templates
│           └── admin/
│               ├── index.html   # FAQ CRUD
│               ├── logs.html    # Analytics dashboard
│               └── settings.html # Bot settings
│
├── scripts/                      # Utilities & migrations
│   ├── migrate_data.py          # Initial DB setup
│   ├── migrate_add_logging.py   # Add logging tables
│   ├── migrate_add_platform.py  # Add platform field
│   ├── demo_faq.py              # Demo data (21 FAQs)
│   ├── fix_tables.py            # DB repair utility
│   └── register_bot.py          # Bitrix24 bot registration
│
├── docker/                       # Docker configuration
│   ├── Dockerfile               # Multi-service image
│   ├── docker-compose.yml       # Service orchestration
│   └── docker-compose.nginx.yml # Nginx reverse proxy
│
├── nginx/                        # Nginx configs
├── docs/                         # Documentation
├── requirements.txt              # Python dependencies
├── .env.example                  # Configuration template
├── docker-compose.yml            # Docker Compose wrapper
├── start.sh                      # Interactive startup script
├── Makefile                      # Common operations (31 commands)
└── README.md                     # User documentation (Russian)
```

---

## Core Components

### 1. Database Layer (`src/core/database.py`)

**Purpose**: SQLite ORM with business logic for FAQ management, logging, and analytics.

**Key Functions**:

```python
# FAQ Management
get_all_faqs() -> List[Dict]
get_faq_by_id(faq_id: str) -> Optional[Dict]
add_faq(category, question, answer, keywords) -> str  # Returns new ID
update_faq(faq_id, **fields) -> bool
delete_faq(faq_id) -> bool

# Categories
get_all_categories() -> List[Dict]
add_category(name) -> int

# Logging
add_query_log(user_id, username, query_text, platform) -> int
add_answer_log(query_log_id, faq_id, similarity_score, answer_shown) -> int
add_rating_log(answer_log_id, user_id, rating) -> int
get_logs(filters: Dict) -> List[Dict]  # Supports: user_id, faq_id, rating, date_range, platform

# Settings
get_bot_setting(key, default=None) -> str
update_bot_setting(key, value) -> bool
get_all_settings() -> Dict

# Analytics
get_statistics(filters: Dict) -> Dict  # Returns: total_queries, unique_users, avg_similarity, etc.
```

**Important Patterns**:

- **Context Manager**: Use `get_db_connection()` for safe transactions
- **Timezone Handling**: `convert_utc_to_utc7(utc_timestamp)` for display
- **Keywords**: Stored as comma-separated strings, converted with `keywords.split(',')` / `','.join(keywords)`
- **Platform Field**: Values are `'telegram'`, `'bitrix24'`, or `'web'`

**Schema Highlights**:

```sql
-- FAQ data
CREATE TABLE faq (
    id TEXT PRIMARY KEY,
    category TEXT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    keywords TEXT,  -- comma-separated
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Analytics (3-table join)
CREATE TABLE query_logs (id, user_id, username, query_text, platform, timestamp);
CREATE TABLE answer_logs (id, query_log_id, faq_id, similarity_score, answer_shown, timestamp);
CREATE TABLE rating_logs (id, answer_log_id, user_id, rating, timestamp);
```

---

### 2. Telegram Bot (`src/bots/bot.py`)

**Architecture**: Long-polling bot with embedded Flask reload server.

**Key Handlers**:

- `/start` → Welcome message + category keyboard
- Text messages → `search_faq()` → ChromaDB semantic search
- Callback queries → Category navigation, FAQ display, feedback buttons

**Advanced Features**:

1. **User-Level Rate Limiting**:
   ```python
   user_last_action = {}  # user_id → timestamp
   user_cooldown = {}     # user_id → cooldown_until

   def check_user_rate_limit(user_id, min_interval=0.5):
       # Returns True if allowed, False if rate limited
   ```

2. **Callback Debouncing**:
   ```python
   user_last_callback = {}  # user_id → (callback_data, timestamp)

   def check_callback_debounce(user_id, callback_data, debounce_time=1.0):
       # Prevents duplicate button clicks within 1 second
   ```

3. **Bot Sleep Mode**:
   ```python
   def record_timeout_error():
       # After 3+ errors in 5 min → sleep 10 seconds
       # Prevents cascading failures
   ```

4. **Safe Message Sending**:
   ```python
   async def safe_send_message(func, *args, max_retries=3, **kwargs):
       # Handles: TimedOut, NetworkError, RetryAfter, RemoteProtocolError
       # Exponential backoff: 1s, 2s, 4s
   ```

5. **Hot Reload Server** (Flask on port 5001):
   ```python
   @app.route('/reload', methods=['POST'])
   def reload():
       reload_collection()  # Reloads ChromaDB collection
       return {"status": "ok"}
   ```

**Similarity Threshold Logic**:
```python
similarity = (1 - distance) * 100  # Convert cosine distance to percentage
if similarity >= SIMILARITY_THRESHOLD:
    # Show answer + log as "found"
else:
    # Show "not found" message + log as "not found" (faq_id=None)
```

---

### 3. Bitrix24 Bot (`src/bots/b24_bot.py`)

**Architecture**: Webhook-based Flask app receiving events from Bitrix24.

**Event Types**:

```python
ONIMBOTMESSAGEADD  → handle_message_event()  # New message
ONIMCOMMANDADD     → handle_command_event()  # Button click
ONIMBOTJOINCHAT    → handle_start()          # Bot added to chat
```

**Key Differences from Telegram**:

- **Webhook-based** (not polling)
- **Command Registration**: Buttons are registered as "commands" via API
- **Flat Keyboard**: Buttons in flat array with `{TYPE: "NEWLINE"}` separators
- **Rich Attachments**: Uses `create_attach()` for formatted messages

**Authentication Variables**:
```python
BITRIX24_WEBHOOK    # REST API base URL (with auth key)
BITRIX24_CLIENT_ID  # For sending messages (string, e.g., "vntu29my...")
BITRIX24_BOT_ID     # For registering commands (integer, e.g., 62)
```

**Important**: BOT_ID ≠ CLIENT_ID. BOT_ID is numeric (for commands), CLIENT_ID is string (for auth).

---

### 4. Web Admin (`src/web/web_admin.py`)

**Flask Routes**:

```python
# Public
GET  /                        # Public search interface

# Admin - FAQ Management
GET  /admin/                  # FAQ list
GET  /admin/faq/<id>          # Get single FAQ
POST /admin/faq/              # Create FAQ
PUT  /admin/faq/<id>          # Update FAQ
DEL  /admin/faq/<id>          # Delete FAQ
POST /admin/retrain           # Rebuild ChromaDB + notify bots

# Admin - Search
GET  /admin/search            # Text search (SQL LIKE)
GET  /admin/search/semantic   # Semantic search (ChromaDB)

# Admin - Settings
GET  /admin/settings          # Settings page
POST /admin/settings          # Update settings
POST /admin/settings/reset    # Reset to defaults

# Admin - Logs
GET  /admin/logs              # Logs viewer
GET  /admin/api/logs/list     # Get logs (JSON, with filters)
GET  /admin/api/logs/export   # Export to CSV
```

**Hot Retrain Workflow**:
```python
1. retrain_chromadb()
   - Delete old collection
   - Create new collection
   - Load all FAQs from SQLite
   - Add documents: f"{question} {keywords}" → embeddings

2. notify_bot_reload()
   - POST http://127.0.0.1:5001/reload (Telegram)
   - POST http://127.0.0.1:5002/api/reload-chromadb (Bitrix24)

3. Bots reload collection in memory
```

**Analytics Features**:

- **Filters**: user_id, faq_id, rating, date_range, search_text, platform
- **"No Answer" Filter**: Shows queries where `faq_id IS NULL` OR `similarity < threshold`
- **CSV Export**: UTF-8 BOM + semicolon-delimited (for Excel)
- **Statistics**: Top queries, top helpful FAQs, FAQs needing improvement

---

### 5. Bitrix24 API Client (`src/api/b24_api.py`)

**Classes**:

```python
class Bitrix24API:
    """REST API client for Bitrix24"""

    register_bot(name, code)                    # Initial setup
    register_command(bot_id, command, params)   # Register button
    send_message(client_id, dialog_id, message, keyboard, attach)
    send_typing(dialog_id)                      # May not work with webhooks
    update_message(message_id, ...)
    answer_command(command_id, ...)             # Response to button click

    # Helpers
    create_keyboard(buttons: List[List[Dict]]) → List[Dict]  # Flattens 2D array
    create_attach(items: List[Dict]) → Dict                  # Rich formatting

class Bitrix24Event:
    """Parses webhook event data"""

    # Properties
    is_message, is_command, is_join_chat
    message_text, user_id, dialog_id, username
    command_name, command_params, command_context
```

**Design Notes**:

- Built to mirror `python-telegram-bot` API style for consistency
- Extensive DEBUG logging for troubleshooting
- Handles Bitrix24's flat `data[PARAMS][MESSAGE]` format

---

## Development Workflows

### Setting Up Development Environment

```bash
# 1. Clone repository
git clone <repository-url>
cd AI-FAQ-Bot

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
nano .env  # Add TELEGRAM_TOKEN, etc.

# 5. Initialize database
python scripts/migrate_data.py
python scripts/migrate_add_logging.py
python scripts/migrate_add_platform.py

# 6. Run services (in separate terminals)
python src/bots/bot.py           # Telegram bot
python src/web/web_admin.py      # Web admin
python src/bots/b24_bot.py       # Bitrix24 bot (optional)
```

### Docker Development

```bash
# Start all services
docker-compose --profile telegram --profile bitrix24 up -d

# View logs
docker-compose logs -f telegram-bot

# Rebuild after code changes
docker-compose up -d --build

# Stop all
docker-compose down
```

---

## Code Conventions

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Modules | `snake_case` | `web_admin.py`, `b24_api.py` |
| Classes | `PascalCase` | `Bitrix24API`, `Bitrix24Event` |
| Functions | `snake_case` | `get_all_faqs()`, `send_message()` |
| Constants | `UPPER_SNAKE_CASE` | `MODEL_NAME`, `SIMILARITY_THRESHOLD` |
| Global vars | `snake_case` | `user_last_action`, `bot_is_sleeping` |
| Database tables | `snake_case_plural` | `query_logs`, `rating_logs` |
| Database columns | `snake_case` | `user_id`, `similarity_score` |
| Routes | `kebab-case` | `/admin/faq/list`, `/api/logs/export` |

### Code Style

**Comments**:
```python
# Russian comments for business logic (this is a Russian project)
# English docstrings for functions

def add_query_log(user_id: int, query_text: str, platform: str) -> Optional[int]:
    """
    Логировать запрос пользователя

    :param user_id: ID пользователя
    :param platform: Платформа ('telegram' или 'bitrix24')
    :return: ID созданного лога или None при ошибке
    """
    # Implementation...
```

**Logging**:
```python
logger.info("✅ ChromaDB загружена: {count} записей")
logger.warning("⚠️ Порог схожести слишком низкий: {score}%")
logger.error("❌ Ошибка: {e}", exc_info=True)
```

**Error Handling**:

Always use defensive patterns:
```python
# Context managers for resources
with get_db_connection() as conn:
    # Use connection

# Safe wrappers for external APIs
result = await safe_send_message(update.message.reply_text, "...")
if result is None:
    logger.error("Failed to send message")

# Defensive checks
if not user_id:
    logger.warning("Missing user_id")
    return None
```

### File Organization

**When adding new features**:

1. **Database changes** → Create migration script in `scripts/migrate_*.py`
2. **New bot commands** → Add handler in `src/bots/bot.py` or `b24_bot.py`
3. **New API routes** → Add to `src/web/web_admin.py`
4. **New HTML templates** → Add to `src/web/templates/admin/`
5. **New utilities** → Add to `src/core/` if reusable

---

## Common Tasks

### Task 1: Add a New FAQ

**Via Web Admin**:
1. Open http://localhost:5000/admin/
2. Click "Добавить FAQ"
3. Fill form, click "Сохранить"
4. Click "Переобучить базу знаний" button

**Via Code**:
```python
from src.core.database import add_faq
from src.web.web_admin import retrain_chromadb, notify_bot_reload

# Add FAQ
faq_id = add_faq(
    category="HR",
    question="Как получить справку 2-НДФЛ?",
    answer="Обратитесь в бухгалтерию...",
    keywords=["2-НДФЛ", "справка", "налоги"]
)

# Retrain and reload
retrain_chromadb()
notify_bot_reload()
```

---

### Task 2: Add a New Bot Setting

**Step 1**: Add to defaults in `src/core/database.py`:
```python
DEFAULT_BOT_SETTINGS = {
    # ... existing settings ...
    "new_setting_key": "default value",
}
```

**Step 2**: Add UI field in `src/web/templates/admin/settings.html`:
```html
<div class="mb-3">
    <label for="new_setting_key" class="form-label">New Setting</label>
    <input type="text" class="form-control" id="new_setting_key"
           value="{{ settings.get('new_setting_key', '') }}">
</div>
```

**Step 3**: Use in bot code:
```python
from src.core.database import get_bot_setting

new_value = get_bot_setting("new_setting_key")
```

---

### Task 3: Add a New Analytics Filter

**Step 1**: Update `get_logs()` in `src/core/database.py`:
```python
def get_logs(filters: Dict) -> List[Dict]:
    conditions = []
    params = {}

    # Existing filters...

    # Add new filter
    if filters.get('new_filter'):
        conditions.append("some_column = :new_filter")
        params['new_filter'] = filters['new_filter']

    # ... rest of function
```

**Step 2**: Add UI filter in `src/web/templates/admin/logs.html`:
```html
<div class="col-md-3">
    <label for="newFilter" class="form-label">New Filter</label>
    <input type="text" class="form-control" id="newFilter">
</div>
```

**Step 3**: Update JavaScript to include filter in AJAX requests.

---

### Task 4: Add Support for a New Platform

**Step 1**: Update platform enum (if needed):
```python
# In src/core/database.py
VALID_PLATFORMS = ['telegram', 'bitrix24', 'new_platform']
```

**Step 2**: Create bot file:
```python
# src/bots/new_platform_bot.py
import logging
from src.core.database import add_query_log, add_answer_log
# ... implement bot logic
```

**Step 3**: Add Docker service:
```yaml
# docker/docker-compose.yml
new-platform-bot:
  build: ..
  command: python -m src.bots.new_platform_bot
  profiles: ["new_platform"]
  # ... volumes, networks, etc.
```

**Step 4**: Update documentation and `.env.example`.

---

### Task 5: Change Similarity Threshold

**Option A**: Environment variable (requires restart):
```bash
# .env
SIMILARITY_THRESHOLD=50  # Change from 45 to 50

# Restart bot
docker-compose restart telegram-bot
```

**Option B**: Dynamic (future enhancement):
```python
# Add similarity_threshold to bot_settings table
# Update bots to reload threshold via /reload-settings endpoint
```

---

### Task 6: Export Logs for Analysis

**Via Web Admin**:
1. Open http://localhost:5000/admin/logs
2. Set filters (date range, platform, etc.)
3. Click "📥 Экспорт в CSV"
4. Open CSV in Excel/Google Sheets

**Via Code**:
```python
from src.core.database import get_logs
import csv

logs = get_logs({
    'platform': 'telegram',
    'date_from': '2025-01-01',
    'date_to': '2025-01-31'
})

with open('export.csv', 'w', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=logs[0].keys())
    writer.writeheader()
    writer.writerows(logs)
```

---

### Task 7: Debug Low Similarity Scores

**Step 1**: Check logs with "No Answer" filter:
```
http://localhost:5000/admin/logs?no_answer=1
```

**Step 2**: Look at similarity scores in 40-60% range.

**Step 3**: Options:
- **Lower threshold** → More answers (may be less accurate)
- **Add keywords** → Improve FAQ matching
- **Retrain FAQ** → Better question phrasing

**Step 4**: Test semantic search:
```python
from src.web.web_admin import collection

results = collection.query(
    query_texts=["Как получить зарплату?"],
    n_results=3
)
print(results['distances'])  # Check similarity scores
```

---

## Database Schema

### Tables Overview

```sql
-- FAQ Management
faq (id, category, question, answer, keywords, created_at, updated_at)
categories (id, name)
bot_settings (key, value, updated_at)

-- Analytics (3-table join)
query_logs (id, user_id, username, query_text, platform, timestamp)
answer_logs (id, query_log_id FK, faq_id FK, similarity_score, answer_shown, timestamp)
rating_logs (id, answer_log_id FK, user_id, rating, timestamp)
```

### Detailed Schemas

**faq**:
```sql
CREATE TABLE faq (
    id TEXT PRIMARY KEY,           -- UUID
    category TEXT NOT NULL,        -- Category name
    question TEXT NOT NULL,        -- Question text
    answer TEXT NOT NULL,          -- Answer text
    keywords TEXT,                 -- Comma-separated keywords
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Auto-update trigger
CREATE TRIGGER update_faq_timestamp
AFTER UPDATE ON faq
BEGIN
    UPDATE faq SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
```

**query_logs**:
```sql
CREATE TABLE query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    query_text TEXT NOT NULL,
    platform TEXT DEFAULT 'telegram',  -- 'telegram' | 'bitrix24' | 'web'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_logs_user_id ON query_logs(user_id);
CREATE INDEX idx_query_logs_timestamp ON query_logs(timestamp);
```

**answer_logs**:
```sql
CREATE TABLE answer_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_log_id INTEGER,
    faq_id TEXT,                       -- NULL if no answer found
    similarity_score REAL,             -- 0-100 (percentage)
    answer_shown TEXT,                 -- Full answer text or "Ответ не найден"
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_log_id) REFERENCES query_logs(id),
    FOREIGN KEY (faq_id) REFERENCES faq(id)
);

CREATE INDEX idx_answer_logs_query_log_id ON answer_logs(query_log_id);
CREATE INDEX idx_answer_logs_faq_id ON answer_logs(faq_id);
```

**rating_logs**:
```sql
CREATE TABLE rating_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_log_id INTEGER,
    user_id INTEGER,
    rating TEXT,                       -- 'helpful' | 'not_helpful'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (answer_log_id) REFERENCES answer_logs(id)
);
```

### ChromaDB Collections

**Collection Name**: `faq_collection`

**Document Structure**:
```python
{
    "documents": [f"{question} {keyword1} {keyword2}"],  # Text to embed
    "metadatas": [{
        "category": "HR",
        "question": "Как получить зарплату?",
        "answer": "Полный текст ответа...",
        "keywords": "зарплата,выплаты,аванс"
    }],
    "ids": [faq_id]
}
```

**Query Example**:
```python
results = collection.query(
    query_texts=["Вопрос пользователя"],
    n_results=3,
    include=["documents", "metadatas", "distances"]
)

# Convert distance to similarity
distance = results["distances"][0][0]  # Cosine distance (0-2)
similarity = (1 - distance) * 100      # Percentage (0-100)
```

---

## Configuration Management

### Environment Variables (.env)

**Required**:
```bash
# Telegram Bot
TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Embedding Model
MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
SIMILARITY_THRESHOLD=45  # 0-100
```

**Optional (Bitrix24)**:
```bash
BITRIX24_WEBHOOK=https://your-domain.bitrix24.ru/rest/1/webhook_key/
BITRIX24_BOT_CODE=FAQBot
BITRIX24_BOT_ID=62                                    # Integer
BITRIX24_CLIENT_ID=vntu29my52f21kbrx5jzjzctktvgvnbi  # String
BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24
BITRIX24_BOT_NAME=FAQ Помощник
BITRIX24_PORT=5002
```

**Optional (Advanced)**:
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
ENVIRONMENT=production  # development, staging, production
```

### Database Settings (bot_settings table)

```python
DEFAULT_BOT_SETTINGS = {
    "start_message": "👋 Здравствуйте! Я бот FAQ...",
    "feedback_button_yes": "👍 Полезно",
    "feedback_button_no": "👎 Не помогло",
    "feedback_response_yes": "✅ Спасибо за отзыв!",
    "feedback_response_no": "😔 Извините, что не смогли помочь..."
}
```

**Accessing**:
```python
from src.core.database import get_bot_setting, update_bot_setting

message = get_bot_setting("start_message")
update_bot_setting("start_message", "New message")
```

### Docker Volumes

**Production data**:
```yaml
volumes:
  - ./data/faq_database.db:/app/data/faq_database.db  # SQLite
  - ./data/chroma_db:/app/data/chroma_db              # ChromaDB
  - sentence-transformers-cache:/root/.cache/torch    # Model cache
```

---

## Testing & Debugging

### Manual Testing

**Test Telegram Bot**:
1. Send `/start` → Should show category keyboard
2. Send text question → Should return answer or "not found"
3. Click feedback button → Should log rating

**Test Web Admin**:
1. Open http://localhost:5000/admin/
2. Add FAQ → Should appear in list
3. Click "Переобучить" → Check logs for "ChromaDB переобучена"
4. Search FAQ → Should find by text or semantic

**Test Bitrix24 Bot**:
1. Add bot to chat in Bitrix24
2. Send question → Should respond
3. Check logs: `docker-compose logs -f bitrix24-bot`

### Health Checks

**Telegram Bot**:
```bash
curl http://localhost:5001/health
# Response: {"status": "ok", "faq_count": 21}
```

**Web Admin**:
```bash
curl http://localhost:5000/admin/
# Should return HTML
```

**Bitrix24 Bot**:
```bash
curl http://localhost:5002/api/health
# Response: {"status": "ok", "faq_count": 21}
```

### Debugging Commands

**View SQLite data**:
```bash
sqlite3 data/faq_database.db
sqlite> SELECT * FROM faq LIMIT 5;
sqlite> SELECT COUNT(*) FROM query_logs;
sqlite> .quit
```

**Check ChromaDB collection**:
```python
python3
>>> import chromadb
>>> client = chromadb.PersistentClient(path="./data/chroma_db")
>>> collection = client.get_collection("faq_collection")
>>> collection.count()
21
```

**View logs**:
```bash
# Docker
docker-compose logs -f telegram-bot
docker-compose logs --tail=100 web-admin

# Local
# Logs are in console output
```

**Test semantic search**:
```python
from sentence_transformers import SentenceTransformer
import chromadb

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
client = chromadb.PersistentClient(path="./data/chroma_db")
collection = client.get_collection("faq_collection")

results = collection.query(
    query_texts=["Как получить справку?"],
    n_results=3
)

for i, (doc, meta, dist) in enumerate(zip(
    results['documents'][0],
    results['metadatas'][0],
    results['distances'][0]
)):
    similarity = (1 - dist) * 100
    print(f"{i+1}. {meta['question']} - {similarity:.1f}%")
```

### Common Issues

**Issue**: Bot not responding
- Check token in `.env`
- Check internet connection
- View logs: `docker-compose logs telegram-bot`

**Issue**: Low similarity scores
- Check threshold: should be 30-60 for Russian text
- Add more keywords to FAQs
- Try different model (mpnet for better quality)

**Issue**: "Collection not found" error
- Run retrain: Open http://localhost:5000/admin/ → Click "Переобучить"
- Or manually: `python -c "from src.web.web_admin import retrain_chromadb; retrain_chromadb()"`

**Issue**: Database locked
- SQLite is single-writer
- Check for hung processes: `ps aux | grep python`
- Restart services: `docker-compose restart`

---

## Important Constraints

### Technical Constraints

1. **SQLite is Single-Writer**:
   - Concurrent writes will fail with "database is locked"
   - Use transactions carefully
   - Consider PostgreSQL for high concurrency

2. **ChromaDB Must Be Synced**:
   - All services share same ChromaDB folder
   - After updating FAQs, MUST call `retrain_chromadb()` + `notify_bot_reload()`
   - Otherwise bots will serve stale data

3. **Timezone Handling**:
   - Database stores UTC timestamps
   - Display converts to UTC+7 via `convert_utc_to_utc7()`
   - DO NOT store UTC+7 directly

4. **Similarity Threshold**:
   - Values: 0-100 (percentage)
   - Recommended: 45-50 for balanced results
   - Too low → False positives
   - Too high → Too many "not found"

5. **Rate Limiting**:
   - Telegram: User-level rate limiting (0.3s minimum interval)
   - Without this, bot may get 429 errors from Telegram API
   - Bitrix24: No rate limiting (relies on platform)

6. **Model Download on First Run**:
   - sentence-transformers downloads model (~400MB) on first run
   - Takes 2-5 minutes depending on internet speed
   - Docker caches in volume to avoid re-downloading

### Business Constraints

1. **"Not Found" Logging**:
   - Even when no answer is shown, MUST log to `answer_logs` with `faq_id=NULL`
   - This enables "No Answer" filter in analytics

2. **Feedback Cannot Be Changed**:
   - Once user clicks feedback button, rating is logged
   - No "undo" mechanism (by design)

3. **Keywords Are Comma-Separated Strings**:
   - NOT JSON or array
   - Must join/split when reading/writing

4. **Platform Field is Required**:
   - All logs must specify platform: 'telegram', 'bitrix24', or 'web'
   - Enables multi-platform analytics

---

## Deployment

### Production Checklist

**Security**:
- [ ] Change default settings in `bot_settings`
- [ ] Add authentication to web admin (NOT implemented yet)
- [ ] Use HTTPS (Nginx SSL included)
- [ ] Firewall: Only expose ports 80, 443, 5002 (Bitrix24 webhook)
- [ ] Rotate Bitrix24 webhook URLs periodically
- [ ] Set strong `.env` values

**Performance**:
- [ ] Consider PostgreSQL instead of SQLite for >1000 users/day
- [ ] Consider Qdrant/Pinecone instead of ChromaDB for >10k FAQs
- [ ] Set up database backups (cron job)
- [ ] Monitor disk space (ChromaDB + SQLite grow over time)

**Monitoring**:
- [ ] Set up log aggregation (e.g., Loki, ELK)
- [ ] Monitor `/health` endpoints
- [ ] Set up alerts for high error rates
- [ ] Track analytics: queries/day, avg similarity, user feedback

### Docker Production Deployment

```bash
# 1. Clone and configure
git clone <repo>
cd AI-FAQ-Bot
cp .env.example .env
nano .env  # Set production values

# 2. Initialize database
docker-compose run --rm web-admin python scripts/migrate_data.py

# 3. Start services
docker-compose --profile telegram --profile bitrix24 up -d

# 4. Set up Nginx reverse proxy (optional)
docker-compose -f docker/docker-compose.nginx.yml up -d

# 5. Get SSL certificate
make ssl-certbot  # Or manually with certbot
```

### Backup Strategy

```bash
# Backup script (backup.sh)
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)

# Backup SQLite
cp data/faq_database.db /backups/faq_$DATE.db

# Backup ChromaDB
tar czf /backups/chroma_$DATE.tar.gz data/chroma_db/

# Keep only last 30 days
find /backups -name "faq_*.db" -mtime +30 -delete
find /backups -name "chroma_*.tar.gz" -mtime +30 -delete

# Add to crontab
# 0 3 * * * /path/to/backup.sh
```

### Scaling Considerations

**Horizontal Scaling** (future):
- Use PostgreSQL (replaces SQLite)
- Use Qdrant/Pinecone (replaces ChromaDB)
- Add Redis for caching
- Load balance web admin with Nginx
- Use Celery for async tasks (e.g., retraining)

**Vertical Scaling** (current):
- Increase Docker memory limits
- Use faster disk (SSD) for ChromaDB
- Optimize SQL queries with indexes (already implemented)

---

## AI Assistant Guidelines

### When Working on This Codebase

**DO**:
- ✅ Use Russian comments for business logic (this is a Russian project)
- ✅ Always call `retrain_chromadb()` + `notify_bot_reload()` after FAQ changes
- ✅ Use context managers (`get_db_connection()`) for database access
- ✅ Add migrations to `scripts/` for schema changes
- ✅ Test both Telegram and Bitrix24 bots after changes
- ✅ Check logs in UTC+7 (use `convert_utc_to_utc7()`)
- ✅ Add new settings to `DEFAULT_BOT_SETTINGS` first
- ✅ Log errors with `exc_info=True` for stack traces

**DON'T**:
- ❌ Store UTC+7 timestamps directly in database (store UTC)
- ❌ Modify database schema without creating migration script
- ❌ Update FAQs without retraining ChromaDB
- ❌ Use `time.sleep()` in async functions (use `await asyncio.sleep()`)
- ❌ Hardcode strings that should be in `bot_settings`
- ❌ Skip error handling for external API calls
- ❌ Forget to update both bots when adding new features

### Understanding User Intent

**When asked to "add FAQ"**:
1. Update SQLite via `add_faq()`
2. Retrain ChromaDB via `retrain_chromadb()`
3. Notify bots via `notify_bot_reload()`

**When asked to "check logs"**:
- Open http://localhost:5000/admin/logs
- Or query database: `get_logs(filters)`

**When asked to "change threshold"**:
- Modify `.env`: `SIMILARITY_THRESHOLD=50`
- Restart bots: `docker-compose restart`

**When asked to "add analytics"**:
- Update `get_statistics()` in `database.py`
- Update UI in `templates/admin/logs.html`

---

## Quick Reference

### Ports

| Service | Port | URL |
|---------|------|-----|
| Web Admin | 5000 | http://localhost:5000 |
| Telegram Bot (reload) | 5001 | http://localhost:5001/reload |
| Bitrix24 Bot | 5002 | http://localhost:5002/webhook/bitrix24 |

### Key Files

| Purpose | File |
|---------|------|
| Database ORM | `src/core/database.py` |
| Telegram bot | `src/bots/bot.py` |
| Bitrix24 bot | `src/bots/b24_bot.py` |
| Web admin | `src/web/web_admin.py` |
| Bitrix24 API | `src/api/b24_api.py` |
| Config | `.env` |
| Demo data | `scripts/demo_faq.py` |

### Makefile Commands

```bash
make up-telegram      # Start with Telegram bot
make up-bitrix24      # Start with Bitrix24 bot
make up-all           # Start all services
make logs             # View all logs
make logs-telegram    # View Telegram bot logs
make init             # Initialize database
make backup           # Backup databases
make restart          # Restart services
make down             # Stop all services
```

---

## Conclusion

This codebase is **production-ready** with excellent architecture, comprehensive logging, and defensive programming. Key strengths:

- ✅ Well-structured modular code
- ✅ Comprehensive error handling
- ✅ Rich documentation (Russian)
- ✅ Docker-first deployment
- ✅ Multi-platform support
- ✅ Hot-reload mechanism
- ✅ Analytics and logging

**Areas for improvement**:
- Add unit tests
- Add authentication to web admin
- Consider PostgreSQL for high concurrency
- Add async/await to Bitrix24 bot

When working with this codebase, focus on maintaining the existing patterns and defensive programming style. Always test changes on both platforms (Telegram and Bitrix24).

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Maintained By**: AI Assistants working with this repository
