# 🔀 Настройка Reverse Proxy с BASE_PATH

## Проблема

Когда FAQ Bot развёрнут не на корневом пути (например, `https://domain.com/faqbot` вместо `https://domain.com`), кнопки похожих вопросов в Bitrix24 не работают.

**Причина:** Bitrix24 отправляет события команд на URL, который был указан при регистрации команды. Если этот URL не учитывает BASE_PATH - события не доходят до приложения.

---

## ✅ Решение

FAQ Bot теперь автоматически добавляет `BASE_PATH` к `BITRIX24_HANDLER_URL` при регистрации команд.

### Пример:

**Без BASE_PATH:**
```env
BITRIX24_HANDLER_URL=https://domain.com/webhook/bitrix24
BASE_PATH=
```
→ Команды регистрируются с URL: `https://domain.com/webhook/bitrix24`

**С BASE_PATH:**
```env
BITRIX24_HANDLER_URL=https://domain.com/webhook/bitrix24
BASE_PATH=/faqbot
```
→ Команды регистрируются с URL: `https://domain.com/faqbot/webhook/bitrix24`

---

## 📝 Настройка

### Шаг 1: Обновите .env файл

Добавьте переменную `BASE_PATH`:

```env
# Префикс пути для reverse proxy
BASE_PATH=/faqbot

# HANDLER_URL БЕЗ префикса (BASE_PATH добавится автоматически)
BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24
```

**⚠️ ВАЖНО:**
- `BASE_PATH` должен начинаться с `/` (например: `/faqbot`, `/bot`, `/api/faq`)
- `BITRIX24_HANDLER_URL` указывается **БЕЗ** BASE_PATH - он добавится автоматически
- Не дублируйте BASE_PATH в HANDLER_URL

### Шаг 2: Настройте Nginx

#### Вариант A: Один сервис на корневом пути

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Битрикс24 бот
    location / {
        proxy_pass http://localhost:5002;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**.env:**
```env
BASE_PATH=
BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24
```

---

#### Вариант B: Несколько сервисов с префиксами (РЕКОМЕНДУЕТСЯ)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Веб-админка на корневом пути
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Битрикс24 бот на /bot
    location /bot {
        # ВАЖНО: rewrite убирает /bot из пути перед проксированием
        rewrite ^/bot(/.*)$ $1 break;

        proxy_pass http://localhost:5002;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**.env:**
```env
BASE_PATH=/bot
BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24
```

**Как работает:**
1. Запрос приходит: `https://domain.com/bot/webhook/bitrix24`
2. Nginx убирает `/bot`: → `/webhook/bitrix24`
3. Проксирует на `http://localhost:5002/webhook/bitrix24`
4. Flask обрабатывает запрос по роуту `/webhook/bitrix24`

---

#### Вариант C: BASE_PATH на поддомене

```nginx
server {
    listen 443 ssl http2;
    server_name faqbot.your-domain.com;

    ssl_certificate /etc/letsencrypt/live/faqbot.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/faqbot.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:5002;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**.env:**
```env
BASE_PATH=
BITRIX24_HANDLER_URL=https://faqbot.your-domain.com/webhook/bitrix24
```

---

## 🔧 Применение изменений

### На сервере с Docker

1. **Обновите .env:**
   ```bash
   nano .env
   # Добавьте BASE_PATH=/your-prefix
   ```

2. **Перезапустите контейнеры:**
   ```bash
   docker compose --profile bitrix24 down
   docker compose --profile bitrix24 up -d
   ```

3. **Проверьте логи:**
   ```bash
   docker compose logs -f bitrix24-bot | grep "BASE_PATH"
   ```

   **Ожидаемый вывод:**
   ```
   🔧 BASE_PATH применён к HANDLER_URL: https://domain.com/faqbot/webhook/bitrix24
   ```

4. **Проверьте регистрацию команд:**

   Отправьте любое сообщение боту в Bitrix24. В логах должно быть:
   ```
   ✅ Зарегистрирована команда: similar_question
   ```

---

## ✅ Проверка работоспособности

### 1. Проверьте HANDLER_URL в логах

```bash
docker compose logs bitrix24-bot | grep "HANDLER_URL"
```

Должны увидеть:
```
🔧 BASE_PATH применён к HANDLER_URL: https://domain.com/faqbot/webhook/bitrix24
```

### 2. Проверьте веб-админку

Откройте: `https://domain.com/faqbot/admin/` (или ваш BASE_PATH)

Если страница открывается, но стили не загружаются - проверьте nginx конфигурацию.

### 3. Проверьте кнопки похожих вопросов

1. Отправьте запрос боту, который даст **семантический** результат (не exact match)
2. Бот должен показать кнопки похожих вопросов: "❓ ..."
3. Нажмите на кнопку
4. ✅ Бот должен ответить на выбранный вопрос

**Если не работает:**
- Проверьте логи: `docker compose logs -f bitrix24-bot`
- Убедитесь что BASE_PATH добавлен к HANDLER_URL
- Проверьте nginx конфигурацию (должен быть `rewrite`)

---

## 🐛 Troubleshooting

### Проблема: "404 Not Found" при нажатии на кнопки

**Причина:** Nginx не проксирует запросы с BASE_PATH на бота

**Решение:**
```nginx
location /bot {
    rewrite ^/bot(/.*)$ $1 break;  # ← Добавьте эту строку
    proxy_pass http://localhost:5002;
    # ...
}
```

---

### Проблема: Стили не загружаются в веб-админке

**Причина:** Статические файлы ищутся по неправильному пути

**Решение:** Добавьте специальное правило для статики:
```nginx
location /bot/static {
    rewrite ^/bot/static(/.*)$ /static$1 break;
    proxy_pass http://localhost:5000;
}

location /bot {
    rewrite ^/bot(/.*)$ $1 break;
    proxy_pass http://localhost:5002;
}
```

---

### Проблема: Команды не регистрируются

**Симптомы:** Логи показывают ошибки при регистрации команд

**Проверьте:**
1. BITRIX24_HANDLER_URL доступен из интернета:
   ```bash
   curl -I https://your-domain.com/faqbot/webhook/bitrix24
   ```
   Должно вернуть 200 OK или 405 Method Not Allowed (это нормально для POST endpoint)

2. Bitrix24 может достучаться до URL (firewall, whitelist IP)

---

## 📊 Примеры конфигураций

### Пример 1: Корпоративный сервер

```env
# .env
BASE_PATH=/services/faqbot
BITRIX24_HANDLER_URL=https://corporate.company.com/webhook/bitrix24
```

```nginx
# /etc/nginx/sites-available/corporate.conf
location /services/faqbot {
    rewrite ^/services/faqbot(/.*)$ $1 break;
    proxy_pass http://localhost:5002;
    # ...
}
```

### Пример 2: Общий домен для всех ботов

```env
# .env
BASE_PATH=/bots/faq
BITRIX24_HANDLER_URL=https://bots.company.com/webhook/bitrix24
```

```nginx
# /etc/nginx/sites-available/bots.conf
location /bots/faq {
    rewrite ^/bots/faq(/.*)$ $1 break;
    proxy_pass http://faqbot:5002;
    # ...
}

location /bots/hr {
    rewrite ^/bots/hr(/.*)$ $1 break;
    proxy_pass http://hrbot:5003;
    # ...
}
```

---

## 🔗 См. также

- [DOCKER-CPU-OPTIMIZATION.md](DOCKER-CPU-OPTIMIZATION.md) - оптимизация Docker сборки
- [DEPLOYMENT.md](DEPLOYMENT.md) - полное руководство по развёртыванию
- [README_BITRIX24.md](README_BITRIX24.md) - интеграция с Bitrix24
