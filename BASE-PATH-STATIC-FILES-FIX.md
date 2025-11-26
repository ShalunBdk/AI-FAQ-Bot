# 🔧 Профессиональное решение BASE_PATH + статические файлы

## 📋 Анализ проблемы

### Текущая архитектура (КОСТЫЛИ ❌)

```
Браузер → Nginx → Flask

1. Templates генерируют: <link href="/faqbot/static/css/output.css">
2. Браузер запрашивает: GET /faqbot/static/css/output.css
3. Nginx (location /faqbot):
   - rewrite ^/faqbot(/.*)$ $1 break  ← УБИРАЕТ /faqbot!
   - proxy_pass → Flask получает: /static/css/output.css
4. Flask ищет route для /static/...
   - static_url_path = "/faqbot/static"
   - Flask ожидает: /faqbot/static/...
   - Получает: /static/...
   → 404 NOT FOUND ❌
```

### Текущие костыли:

```nginx
# Костыль 1: Отдельный location для статики
location /faqbot/static/ {
    alias /var/www/faqbot/static/;  # ❌ Nginx напрямую читает файлы
    access_log off;
    expires 30d;
}
```

```yaml
# Костыль 2: Volume из Flask в Nginx
services:
  nginx:
    volumes:
      - /path/to/flask/static:/var/www/faqbot/static  # ❌ Нарушение изоляции
```

```python
# Костыль 3: Изменение static_url_path
app = Flask(__name__, static_url_path=f"{BASE_PATH}/static")
```

**Почему это плохо:**

1. ❌ **Нарушение изоляции контейнеров** - Nginx читает файлы из контейнера Flask
2. ❌ **Дублирование конфигурации** - Путь к статике в 3 местах (nginx, Flask, volume)
3. ❌ **Хрупкая архитектура** - При изменении BASE_PATH нужно менять 3+ файла
4. ❌ **Проблемы с масштабированием** - Volumes не работают при multi-instance деплое
5. ❌ **Плохая читаемость** - Непонятно где что обрабатывается

---

## ✅ Профессиональное решение

### Вариант 1: Правильный nginx reverse proxy (РЕКОМЕНДУЕТСЯ)

**Идея:** Nginx НЕ должен убирать BASE_PATH для статики, Flask сам её обработает.

#### Изменения в Nginx конфигурации:

```nginx
# ПРАВИЛЬНАЯ конфигурация для BASE_PATH
location /faqbot {
    # ❌ СТАРЫЙ ВАРИАНТ (неправильно):
    # rewrite ^/faqbot(/.*)$ $1 break;

    # ✅ НОВЫЙ ВАРИАНТ: Проксируем с полным путём, убираем BASE_PATH в headers
    proxy_pass http://faqbot-web-admin:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Script-Name /faqbot;  # ← Flask поймёт BASE_PATH

    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 300s;
}

# УБИРАЕМ отдельный location /faqbot/static - он не нужен!
```

#### Изменения в Flask (`web_admin.py`):

```python
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_PATH = os.getenv('BASE_PATH', '').rstrip('/')

app = Flask(
    __name__,
    static_folder=static_folder,
    template_folder=template_folder,
    static_url_path='/static'  # ← БЕЗ BASE_PATH!
)

# ProxyFix - правильно обрабатывает X-Script-Name от nginx
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1  # ← Читает X-Script-Name → SCRIPT_NAME
)

app.config['BASE_PATH'] = BASE_PATH
app.config['PREFERRED_URL_SCHEME'] = 'https'
```

**Как это работает:**

1. Templates генерируют: `{{ url_for('static', filename='css/output.css') }}`
2. Flask видит `SCRIPT_NAME=/faqbot` (из X-Script-Name)
3. url_for() генерирует: `/faqbot/static/css/output.css` ✓
4. Nginx получает: `/faqbot/static/css/output.css`
5. Nginx НЕ делает rewrite, проксирует как есть на Flask
6. Flask (через ProxyFix) понимает что BASE_PATH = /faqbot
7. Flask обрабатывает `/faqbot` + `/static/css/output.css` ✓
8. Файл отдаётся ✓

---

### Вариант 2: Использовать nginx только для проксирования (БЕЗ rewrite)

Если не хотите менять Flask, просто **НЕ делайте rewrite** для BASE_PATH.

#### Nginx:

```nginx
location /faqbot/ {
    # НЕТ rewrite! Проксируем полный путь
    proxy_pass http://faqbot-web-admin:5000/faqbot/;
    proxy_set_header Host $host;
    # ... остальные headers
}
```

#### Flask остаётся как есть:

```python
static_url_path=f"{BASE_PATH}/static"  # /faqbot/static
```

**Минус:** Flask должен сам парсить `/faqbot/...` во всех маршрутах.

---

### Вариант 3: Flask Blueprint с префиксом (для сложных случаев)

Использовать Blueprint с `url_prefix`:

```python
from flask import Blueprint

BASE_PATH = os.getenv('BASE_PATH', '').rstrip('/')

# Основное приложение БЕЗ BASE_PATH
app = Flask(__name__, static_url_path='/static')

# Blueprint с префиксом
admin_bp = Blueprint('admin', __name__, url_prefix=BASE_PATH or None)

@admin_bp.route('/')
def index():
    return render_template('admin/index.html')

app.register_blueprint(admin_bp)
```

**Nginx:**

```nginx
location /faqbot {
    # БЕЗ rewrite - Flask сам разберётся
    proxy_pass http://faqbot-web-admin:5000;
}
```

---

## 🎯 Рекомендация

**Используйте Вариант 1** - это правильный способ работы с reverse proxy.

**Преимущества:**

- ✅ Чистая архитектура - nginx проксирует, Flask обрабатывает
- ✅ Нет volumes между контейнерами
- ✅ Работает при масштабировании (multiple instances)
- ✅ Один источник правды - BASE_PATH только в .env
- ✅ Стандартный подход (ProxyFix - официальный middleware от Werkzeug)

---

## 📝 План миграции

### Шаг 1: Обновить Flask (`src/web/web_admin.py`)

```python
# В начале файла
from werkzeug.middleware.proxy_fix import ProxyFix

# После создания app
BASE_PATH = os.getenv('BASE_PATH', '').rstrip('/')

app = Flask(
    __name__,
    static_folder=static_folder,
    template_folder=template_folder,
    static_url_path='/static'  # БЕЗ BASE_PATH
)

# ProxyFix MIDDLEWARE
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,
    x_proto=1,
    x_host=1,
    x_prefix=1
)

app.config['BASE_PATH'] = BASE_PATH
app.config['PREFERRED_URL_SCHEME'] = 'https'
```

### Шаг 2: Обновить Nginx конфигурацию

```nginx
# Было:
location /faqbot {
    rewrite ^/faqbot(/.*)$ $1 break;  # ← УБРАТЬ
    proxy_pass http://faqbot-web-admin:5000;
}

location /faqbot/static/ {            # ← УБРАТЬ весь блок
    alias /var/www/faqbot/static/;
}

# Стало:
location /faqbot {
    proxy_pass http://faqbot-web-admin:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Script-Name /faqbot;  # ← ВАЖНО!

    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

### Шаг 3: Убрать volume из docker-compose

```yaml
# Было:
services:
  nginx:
    volumes:
      - /home/ubuntu/FAQBot/src/web/static:/var/www/faqbot/static  # ← УБРАТЬ

# Стало:
services:
  nginx:
    volumes:
      # Volume для статики НЕ НУЖЕН!
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
```

### Шаг 4: Перезапустить сервисы

```bash
# 1. Обновить код
git pull origin main

# 2. Пересобрать образы (если меняли web_admin.py)
docker compose --profile bitrix24 build web-admin

# 3. Перезапустить nginx + приложение
docker compose --profile bitrix24 down
docker compose --profile bitrix24 up -d

# 4. Проверить логи
docker compose logs -f web-admin nginx
```

### Шаг 5: Проверка

```bash
# Откройте в браузере
https://your-domain.com/faqbot/admin/

# Проверьте в DevTools:
# Network → output.css → Status: 200 OK ✓
```

---

## 🐛 Troubleshooting

### Проблема: 404 на статику после миграции

**Проверьте:**

1. **X-Script-Name header в nginx:**
   ```bash
   docker compose exec nginx grep "X-Script-Name" /etc/nginx/nginx.conf
   ```

2. **ProxyFix установлен:**
   ```python
   # В web_admin.py должно быть:
   from werkzeug.middleware.proxy_fix import ProxyFix
   app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)
   ```

3. **static_url_path БЕЗ BASE_PATH:**
   ```python
   static_url_path='/static'  # НЕ f"{BASE_PATH}/static"
   ```

### Проблема: Styles не применяются

**Проверьте Content-Type:**

```bash
curl -I https://your-domain.com/faqbot/static/css/output.css
```

Должно быть: `Content-Type: text/css`

Если нет → добавьте в nginx:

```nginx
location /faqbot {
    # ...
    proxy_set_header X-Forwarded-Proto $scheme;

    # Для CSS файлов
    location ~* \.css$ {
        proxy_pass http://faqbot-web-admin:5000;
        add_header Content-Type text/css;
    }
}
```

---

## 📊 Сравнение решений

| Критерий | Костыли (текущее) | Вариант 1 (ProxyFix) | Вариант 2 (без rewrite) |
|----------|-------------------|---------------------|----------------------|
| **Изоляция** | ❌ Volumes между контейнерами | ✅ Полная изоляция | ✅ Полная изоляция |
| **Конфигурация** | ❌ 3+ файла | ✅ 2 файла | ✅ 2 файла |
| **Масштабируемость** | ❌ Не работает | ✅ Работает | ✅ Работает |
| **Читаемость** | ❌ Запутанно | ✅ Понятно | ✅ Понятно |
| **Стандартность** | ❌ Кастомное | ✅ Стандарт (ProxyFix) | ⚠️ Рабочее |
| **Сложность миграции** | - | 🟢 Низкая | 🟡 Средняя |

---

## 🔗 См. также

- [REVERSE-PROXY-SETUP.md](REVERSE-PROXY-SETUP.md) - BASE_PATH для Bitrix24 бота
- [ProxyFix документация](https://werkzeug.palletsprojects.com/en/2.3.x/middleware/proxy_fix/)
- [Flask за reverse proxy](https://flask.palletsprojects.com/en/2.3.x/deploying/proxy_fix/)
