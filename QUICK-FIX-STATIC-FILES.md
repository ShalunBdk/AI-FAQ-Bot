# 🚀 Быстрое исправление статических файлов (удаление костылей)

## ✅ Что было сделано в коде

1. **Добавлен ProxyFix middleware** в `src/web/web_admin.py`:
   ```python
   from werkzeug.middleware.proxy_fix import ProxyFix

   app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)
   static_url_path='/static'  # БЕЗ BASE_PATH
   ```

2. **Создана правильная nginx конфигурация**: `nginx/nginx-base-path-correct.conf`

---

## 🔧 Что нужно сделать на сервере

### Шаг 1: Обновить код

```bash
cd /path/to/FAQBot
git pull origin main
```

### Шаг 2: Обновить nginx конфигурацию

Отредактируйте ваш nginx конфиг (например, `/etc/nginx/sites-available/faqbot`):

**УБРАТЬ:**

```nginx
# ❌ УБРАТЬ этот блок:
location /faqbot/static/ {
    alias /var/www/faqbot/static/;
    access_log off;
    expires 30d;
}

# ❌ УБРАТЬ rewrite в основном location:
location /faqbot {
    rewrite ^/faqbot(/.*)$ $1 break;  # ← УБРАТЬ эту строку!
    proxy_pass ...
}
```

**ДОБАВИТЬ:**

```nginx
# ✅ ПРАВИЛЬНАЯ конфигурация:
location /faqbot {
    # НЕТ rewrite! Проксируем полный путь
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

# Статика обрабатывается тем же location /faqbot!
# Отдельный location /faqbot/static НЕ НУЖЕН!
```

Проверьте конфигурацию:

```bash
sudo nginx -t
```

### Шаг 3: Убрать volume из docker-compose

Отредактируйте `docker-compose.yml` или `docker-compose.production.yml`:

**УБРАТЬ:**

```yaml
services:
  nginx:
    volumes:
      # ❌ УБРАТЬ:
      - /home/ubuntu/FAQBot/src/web/static:/var/www/faqbot/static
```

### Шаг 4: Перезапустить сервисы

```bash
# Пересобрать Flask контейнер (с ProxyFix)
docker compose --profile bitrix24 build web-admin

# Перезапустить все
docker compose --profile bitrix24 down
docker compose --profile bitrix24 up -d

# Перезапустить nginx
sudo systemctl reload nginx
```

### Шаг 5: Проверить

```bash
# Откройте в браузере
https://your-domain.com/faqbot/admin/

# Проверьте DevTools:
# Network → output.css → должен быть 200 OK ✓
```

---

## ✅ Результат

**Было (костыли):**
- ❌ 3 файла конфигурации
- ❌ Volume между контейнерами
- ❌ Nginx читает файлы из Flask контейнера
- ❌ Хрупкая архитектура

**Стало (правильно):**
- ✅ Чистая архитектура
- ✅ ProxyFix middleware (стандарт)
- ✅ Полная изоляция контейнеров
- ✅ Работает при масштабировании

---

## 🐛 Если что-то не работает

### 404 на статику

**Проверьте X-Script-Name:**

```bash
# В логах Flask должно быть:
docker compose logs web-admin | grep "SCRIPT_NAME"
```

**Проверьте nginx:**

```bash
sudo nginx -t
cat /etc/nginx/sites-available/faqbot | grep "X-Script-Name"
```

Должно быть: `proxy_set_header X-Script-Name /faqbot;`

### Styles не применяются

**Проверьте Content-Type:**

```bash
curl -I https://your-domain.com/faqbot/static/css/output.css
```

Должно быть: `Content-Type: text/css`

---

## 📚 Подробнее

См. полную документацию:
- [BASE-PATH-STATIC-FILES-FIX.md](BASE-PATH-STATIC-FILES-FIX.md) - детальный анализ
- [nginx/nginx-base-path-correct.conf](nginx/nginx-base-path-correct.conf) - пример конфигурации
