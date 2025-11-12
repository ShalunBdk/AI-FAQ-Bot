# FAQ Бот для Bitrix24 - Техническая документация

## Обзор

Полноценная реализация FAQ бота для платформы Bitrix24, использующая ChromaDB для семантического поиска ответов. Бот создан по аналогии с Telegram ботом и переиспользует ~90% кода.

## Архитектура системы

```
┌─────────────────┐
│   Bitrix24      │  Отправляет события через webhook
│   Platform      │  (ONIMBOTMESSAGEADD, ONIMCOMMANDADD)
└────────┬────────┘
         │ POST запросы
         ▼
┌─────────────────┐
│   b24_bot.py    │  Flask сервер на порту 5002
│   (Flask App)   │  Роутинг событий и обработка команд
└────────┬────────┘
         │
         ├──────────────────────────────┐
         ▼                              ▼
┌─────────────────┐          ┌─────────────────┐
│   b24_api.py    │          │   ChromaDB      │
│  Bitrix24 API   │          │  Semantic search│
│     wrapper     │          │  (embeddings)   │
└─────────┬───────┘          └────────┬────────┘
          │                           │
          ▼                           ▼
┌──────────────────────────────────────────────┐
│            database.py (SQLite)              │
│  query_logs, answer_logs, rating_logs, faqs  │
└──────────────────────────────────────────────┘
```

## Основные компоненты

### 1. `b24_api.py` - REST API обертка для Bitrix24

Это аналог `python-telegram-bot`, но для Bitrix24. Предоставляет высокоуровневый интерфейс для работы с REST API Bitrix24.

#### Класс `Bitrix24API`

**Инициализация:**

```python
api = Bitrix24API(
    webhook_url="https://your-domain.bitrix24.ru/rest/405/webhook_key/",
    client_id="vntu29my52f21kbrx5jzjzctktvgvnbi",  # Строковый CLIENT_ID
    bot_id=926  # Числовой BOT_ID
)
```

**КРИТИЧЕСКИ ВАЖНО:** BOT_ID и CLIENT_ID - это **разные параметры**!

| Параметр | Тип | Использование |
|----------|-----|---------------|
| `bot_id` | int (926) | Регистрация команд (`imbot.command.register`) |
| `client_id` | str | Отправка сообщений (`imbot.message.add`) |

#### Основные методы API

```python
# Отправка сообщения
result = api.send_message(
    dialog_id=405,
    message="Привет!",
    keyboard=keyboard_array,  # Опционально
    attach=attach_array       # Опционально
)

# Регистрация команды для кнопок
result = api.register_command(
    command="helpful_yes",
    title="Полезно",
    handler_url="https://your-domain.com/webhook/bitrix24",
    hidden=True
)

# Ответ на команду (при нажатии кнопки)
result = api.answer_command(
    command_id=15,
    message_id=171308,
    message="Спасибо за отзыв!",
    keyboard=None
)

# Индикатор печатания (не работает с incoming webhooks!)
api.send_typing(dialog_id=405)
```

#### Метод `_call()` - базовый метод для API запросов

```python
def _call(self, method: str, params: Dict = None, use_bot_id: bool = False):
    """
    Отправляет запрос к Bitrix24 REST API

    Args:
        method: Название метода (например, 'imbot.message.add')
        params: Параметры запроса
        use_bot_id: Использовать BOT_ID вместо CLIENT_ID
    """
    url = f"{self.webhook_url}/{method}"

    if self.client_id and not use_bot_id:
        params['CLIENT_ID'] = self.client_id
    elif self.bot_id and use_bot_id:
        params['BOT_ID'] = self.bot_id

    response = self.session.post(url, json=params, timeout=10)
    return response.json()
```

### 2. Формат клавиатуры Bitrix24

**КРИТИЧЕСКАЯ ОСОБЕННОСТЬ:** Bitrix24 использует **плоский массив**, а не двумерный!

#### Создание клавиатуры

```python
def create_keyboard(self, buttons: List[List[Dict]]) -> List[Dict]:
    """
    Преобразует двумерный массив кнопок в плоский массив для Bitrix24

    Входные данные (удобный формат):
    [
        [{'text': '👍 Полезно', 'action': 'helpful_yes', 'params': '123'}],
        [{'text': '👎 Не помогло', 'action': 'helpful_no', 'params': '123'}]
    ]

    Выходные данные (формат Bitrix24):
    [
        {'TEXT': '👍 Полезно', 'COMMAND': 'helpful_yes', 'COMMAND_PARAMS': '123', 'DISPLAY': 'LINE'},
        {'TYPE': 'NEWLINE'},  # Разделитель строк!
        {'TEXT': '👎 Не помогло', 'COMMAND': 'helpful_no', 'COMMAND_PARAMS': '123', 'DISPLAY': 'LINE'}
    ]
    """
    keyboard = []
    for row_index, row in enumerate(buttons):
        for button in row:
            btn_data = {
                'TEXT': button['text'],
                'DISPLAY': 'LINE',
                'COMMAND': button['action'],
                'COMMAND_PARAMS': button.get('params', '')
            }
            keyboard.append(btn_data)

        # Добавляем NEWLINE после каждой строки, кроме последней
        if row_index < len(buttons) - 1:
            keyboard.append({'TYPE': 'NEWLINE'})

    return keyboard
```

### 3. Парсинг событий от Bitrix24

**Класс `Bitrix24Event`**

#### Проблема: плоский формат данных

Bitrix24 отправляет данные в "плоском" формате:

```python
{
    'data[PARAMS][MESSAGE]': 'Привет',
    'data[PARAMS][FROM_USER_ID]': '405',
    'data[PARAMS][DIALOG_ID]': '405',
    'data[COMMAND][15][COMMAND]': 'helpful_yes',
    'data[COMMAND][15][COMMAND_PARAMS]': '47',
    'data[COMMAND][15][COMMAND_ID]': '15',
    'data[COMMAND][15][MESSAGE_ID]': '171308'
}
```

#### Решение: метод `_parse_flat_dict()`

```python
@staticmethod
def _parse_flat_dict(data: Dict, prefix: str) -> Dict:
    """
    Преобразует плоский формат в вложенную структуру

    'data[PARAMS][MESSAGE]' -> {'PARAMS': {'MESSAGE': '...'}}
    'data[COMMAND][15][COMMAND]' -> {'COMMAND': {'COMMAND': '...', ...}}

    ВАЖНО: Числовые индексы (например [15]) пропускаются!
    """
    result = {}
    prefix_pattern = f'{prefix}['

    for key, value in data.items():
        if key.startswith(prefix_pattern):
            # Извлекаем путь
            path = key[len(prefix)+1:-1].split('][')

            # Фильтруем числовые индексы
            filtered_path = [p for p in path if not p.isdigit()]

            # Создаем вложенную структуру
            current = result
            for part in filtered_path[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[filtered_path[-1]] = value

    return result
```

#### Свойства события

```python
event.event_type        # 'ONIMBOTMESSAGEADD', 'ONIMCOMMANDADD', etc.
event.is_message        # True если новое сообщение
event.is_command        # True если команда от кнопки
event.message_text      # Текст сообщения
event.user_id          # ID пользователя
event.dialog_id        # ID диалога
event.command_name     # Название команды
event.command_params   # Параметры команды
event.command_id       # ID команды
event.message_id       # ID сообщения
event.command_context  # 'KEYBOARD', 'TEXTAREA', 'MENU'
```

### 4. `b24_bot.py` - Flask приложение

#### Роутинг событий

```python
@app.route('/', methods=['POST'])
@app.route('/webhook/bitrix24', methods=['POST'])
def webhook_handler():
    """
    Принимает все события от Bitrix24
    ВАЖНО: Bitrix24 может отправлять на / или на /webhook/bitrix24
    """
    # Получаем данные
    if request.is_json:
        event_data = request.get_json()
    else:
        event_data = request.form.to_dict()  # Плоский формат!

    # Парсим событие
    event = Bitrix24Event(event_data)

    # Инициализируем API (один раз при первом запросе)
    global b24_api
    if not b24_api:
        bot_id = int(BITRIX24_BOT_ID)
        b24_api = Bitrix24API(BITRIX24_WEBHOOK, BITRIX24_CLIENT_ID, bot_id)
        register_bot_commands(b24_api)  # Регистрируем команды

    # Роутинг по типу события
    if event.is_message:
        handle_message_event(event, b24_api)
    elif event.is_command:
        handle_command_event(event, b24_api)
    elif event.is_join_chat:
        handle_start(event, b24_api)

    return jsonify({'success': True})
```

#### Обработка сообщений

```python
def handle_message_event(event, api):
    """Обработка текстовых сообщений от пользователя"""
    message = event.message_text.lower().strip()

    if message in ['/start', 'помощь', 'help']:
        handle_start(event, api)
    elif message in ['категории']:
        handle_categories(event, api)
    else:
        handle_search_faq(event, api)  # Поиск в ChromaDB
```

#### Обработка команд от кнопок

```python
def handle_command_event(event, api):
    """
    Обработка нажатий на кнопки
    ВАЖНО: Используем answer_command(), а не send_message()!
    """
    command = event.command_name
    params = event.command_params
    command_id = event.command_data.get('COMMAND_ID')
    message_id = event.command_data.get('MESSAGE_ID')

    if command == 'helpful_yes':
        answer_log_id = int(params)
        handle_rating(
            event, api, answer_log_id,
            is_helpful=True,
            command_id=command_id,
            message_id=message_id
        )
```

### 5. Регистрация команд

Для работы кнопок команды нужно зарегистрировать через `imbot.command.register`.

```python
def register_bot_commands(api):
    """
    Регистрирует команды при старте бота
    Вызывается ОДИН РАЗ при первой инициализации API
    """
    commands = [
        ('helpful_yes', 'Полезно'),
        ('helpful_no', 'Не помогло'),
        ('cat', 'Выбор категории'),
    ]

    for command, title in commands:
        result = api.register_command(
            command=command,
            title=title,
            handler_url=BITRIX24_HANDLER_URL,
            hidden=True
        )
```

#### Формат запроса регистрации

```python
{
    'BOT_ID': 926,                    # ЧИСЛОВОЙ ID!
    'COMMAND': 'helpful_yes',
    'COMMON': 'N',                    # N = только в диалоге с ботом
    'HIDDEN': 'Y',                    # Y = скрыть из списка команд
    'EXTRANET_SUPPORT': 'N',
    'CLIENT_ID': '',                  # Пустая строка!
    'EVENT_COMMAND_ADD': 'https://...',  # URL обработчика
    'LANG': [                         # ОБЯЗАТЕЛЬНЫЙ параметр!
        {
            'LANGUAGE_ID': 'ru',
            'TITLE': 'Полезно',
            'PARAMS': ''
        }
    ]
}
```

## Конфигурация

### Переменные окружения (.env)

```env
# Вебхук для API запросов
# Получить: Настройки → Разработчикам → Входящий вебхук
BITRIX24_WEBHOOK=https://your-domain.bitrix24.ru/rest/405/webhook_key/

# Числовой BOT_ID (например: 926)
# Получить: Настройки → Разработчикам → Чат-боты
BITRIX24_BOT_ID=926

# Строковый CLIENT_ID (например: vntu29my52f21kbrx5jzjzctktvgvnbi)
# Это тот же ID, что отображается в админке бота
BITRIX24_CLIENT_ID=vntu29my52f21kbrx5jzjzctktvgvnbi

# Публичный URL для приема событий
# Должен быть доступен из интернета!
BITRIX24_HANDLER_URL=https://4owrbr-95-47-244-236.ru.tuna.am/webhook/bitrix24

# Порт Flask сервера
BITRIX24_PORT=5002
BITRIX24_HOST=0.0.0.0

# Модель эмбеддингов
MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2

# Порог схожести (45% рекомендуется)
SIMILARITY_THRESHOLD=45
```

## События Bitrix24

### ONIMBOTMESSAGEADD - Новое сообщение

```python
{
    'event': 'ONIMBOTMESSAGEADD',
    'data[PARAMS][MESSAGE]': 'Привет',
    'data[PARAMS][FROM_USER_ID]': '405',
    'data[PARAMS][DIALOG_ID]': '405',
    'data[PARAMS][MESSAGE_TYPE]': 'P',  # P = личное сообщение
    'data[PARAMS][CHAT_TYPE]': 'P'
}
```

### ONIMCOMMANDADD - Команда (кнопка)

```python
{
    'event': 'ONIMCOMMANDADD',
    'data[COMMAND][15][BOT_ID]': '926',
    'data[COMMAND][15][COMMAND]': 'helpful_yes',
    'data[COMMAND][15][COMMAND_PARAMS]': '47',
    'data[COMMAND][15][COMMAND_CONTEXT]': 'KEYBOARD',  # или TEXTAREA, MENU
    'data[COMMAND][15][COMMAND_ID]': '15',
    'data[COMMAND][15][MESSAGE_ID]': '171308',
    'data[PARAMS][FROM_USER_ID]': '405',
    'data[PARAMS][DIALOG_ID]': '405'
}
```

## Решенные проблемы и важные моменты

### 1. "Access denied! Client ID not specified"

**Ошибка:** При отправке сообщений через `imbot.message.add`

**Причина:** CLIENT_ID не передается в параметрах запроса

**Решение:**
```python
params['CLIENT_ID'] = self.client_id
```

### 2. "Incorrect keyboard params"

**Ошибка:** Клавиатура не работает

**Причина:** Неправильный формат - используется двумерный массив

**Решение:** Использовать плоский массив с `{'TYPE': 'NEWLINE'}`

### 3. "Bot not found" / "BOT_ID_ERROR"

**Ошибка:** При регистрации команд

**Причина:** Используется строковый CLIENT_ID вместо числового BOT_ID

**Решение:**
```python
# ПРАВИЛЬНО
'BOT_ID': 926  # int

# НЕПРАВИЛЬНО
'BOT_ID': 'vntu29my52f21kbrx5jzjzctktvgvnbi'  # str
```

### 4. "Handler for 'Command add' event isn't specified"

**Ошибка:** При регистрации команды

**Причина:** Не указан URL обработчика

**Решение:**
```python
params['EVENT_COMMAND_ADD'] = 'https://your-domain.com/webhook/bitrix24'
```

### 5. "Lang set can't be empty"

**Ошибка:** При регистрации команды

**Причина:** Обязательный параметр LANG не указан

**Решение:**
```python
params['LANG'] = [
    {'LANGUAGE_ID': 'ru', 'TITLE': 'Команда', 'PARAMS': ''}
]
```

### 6. send_typing возвращает 404

**Ошибка:** `ERROR_METHOD_NOT_FOUND`

**Причина:** Метод `imbot.chat.setTyping` не работает с incoming webhooks

**Решение:** Игнорировать ошибку - это нормально
```python
if result.get('success') == False:
    logger.debug("send_typing не поддерживается (это нормально)")
```

### 7. User ID = 0 при команде

**Ошибка:** `event.user_id` возвращает 0

**Причина:** Числовой индекс `[15]` не обрабатывается в парсере

**Решение:** Фильтровать числовые индексы в `_parse_flat_dict()`

### 8. Attach не отображаются

**Ошибка:** Вложения с `LINK: '#'` не показываются

**Решение:** Добавлять похожие вопросы прямо в текст сообщения

## Сравнение с Telegram ботом

| Аспект | Telegram | Bitrix24 |
|--------|----------|----------|
| **Библиотека** | python-telegram-bot | Собственная обертка (b24_api.py) |
| **Получение событий** | Long polling / Webhook | Только Webhook |
| **Формат данных** | JSON (вложенный) | Плоский (data[KEY][SUBKEY]) |
| **Клавиатура** | `[[Button1, Button2]]` | `[Button1, Button2, {'TYPE': 'NEWLINE'}]` |
| **Callback данные** | `callback_data='action_123'` | `COMMAND='action'` + `COMMAND_PARAMS='123'` |
| **Ответ на кнопку** | `answer_callback_query()` | `answer_command()` |
| **Typing indicator** | `send_chat_action('typing')` | `send_typing()` (не работает с webhooks) |
| **Регистрация команд** | `set_my_commands()` | `imbot.command.register` |

## Запуск и тестирование

### Запуск бота

```bash
# Установка зависимостей
pip install -r requirements.txt

# Инициализация БД
python migrate_add_platform.py

# Запуск бота
python b24_bot.py
```

### Health check

```bash
curl http://localhost:5002/health

# Ответ:
{
  "status": "ok",
  "chromadb_records": 21,
  "webhook_configured": true
}
```

### Тестирование webhook

```bash
# Тест сообщения
curl -X POST http://localhost:5002/webhook/bitrix24 \
  -d "event=ONIMBOTMESSAGEADD" \
  -d "data[PARAMS][MESSAGE]=Привет" \
  -d "data[PARAMS][FROM_USER_ID]=405" \
  -d "data[PARAMS][DIALOG_ID]=405"

# Тест команды
curl -X POST http://localhost:5002/webhook/bitrix24 \
  -d "event=ONIMCOMMANDADD" \
  -d "data[COMMAND][15][COMMAND]=helpful_yes" \
  -d "data[COMMAND][15][COMMAND_PARAMS]=47" \
  -d "data[COMMAND][15][COMMAND_ID]=15" \
  -d "data[COMMAND][15][MESSAGE_ID]=171308" \
  -d "data[PARAMS][FROM_USER_ID]=405" \
  -d "data[PARAMS][DIALOG_ID]=405"
```

## Структура файлов

```
FAQBot/
├── b24_api.py              # REST API обертка для Bitrix24
├── b24_bot.py              # Flask приложение (webhook сервер)
├── register_bot.py         # Скрипт регистрации бота (опционально)
├── database.py             # SQLite (логи, FAQ)
├── bot.py                  # Telegram бот (опционально)
├── web_admin.py            # Веб-админка
├── logging_config.py       # Настройка логирования
├── demo_faq.py             # Демо данные
├── migrate_add_platform.py # Миграция для платформ
├── requirements.txt        # Зависимости Python
├── .env                    # Конфигурация (не коммитить!)
├── .env.example            # Пример конфигурации
├── faq_database.db         # SQLite база
├── chroma_db/              # ChromaDB (векторная БД)
└── README_BITRIX24.md      # Эта документация
```

## Отладка

### Включение DEBUG логов

```python
# В b24_bot.py или logging_config.py
logging_config.configure_root_logger(level=logging.DEBUG)
```

### Полезные логи

```
2025-11-12 14:20:32 - INFO - 📥 Получен POST запрос на /webhook/bitrix24
2025-11-12 14:20:32 - INFO - 📩 Получено событие от Bitrix24: ONIMCOMMANDADD
2025-11-12 14:20:32 - DEBUG - 🔧 Распарсенные данные:
2025-11-12 14:20:32 - DEBUG -    User ID: 405
2025-11-12 14:20:32 - DEBUG -    Dialog ID: 405
2025-11-12 14:20:32 - DEBUG -    Message: '/helpful_yes 47'
2025-11-12 14:20:32 - DEBUG - ➡️ Роутинг: обработка команды
2025-11-12 14:20:32 - INFO - 🔘 Получена команда от User ID 405: 'helpful_yes' (params: '47')
```

## Ключевые takeaways для AI

1. **BOT_ID и CLIENT_ID - разные вещи!** BOT_ID (int) для команд, CLIENT_ID (str) для сообщений
2. **Клавиатура - плоский массив** с разделителями `{'TYPE': 'NEWLINE'}`
3. **Данные от Bitrix24 плоские** `data[KEY][INDEX][SUBKEY]` - нужен парсер
4. **Числовые индексы игнорируются** при парсинге событий
5. **LANG обязателен** при регистрации команд
6. **answer_command() для кнопок**, send_message() для обычных сообщений
7. **send_typing() не работает** с incoming webhooks - игнорировать ошибку

## Полезные ссылки

- [Bitrix24 REST API Docs](https://dev.1c-bitrix.ru/rest_help/)
- [Чат-боты в Bitrix24](https://dev.1c-bitrix.ru/learning/course/?COURSE_ID=93)
- [imbot методы](https://dev.1c-bitrix.ru/rest_help/im/imbot/)
