# Быстрый старт развертывания FAQ-бота

## ⚠️ Важно: Замените значения-заполнители

Перед началом замените в инструкции:
- `your-domain.com` → ваш реальный домен (например: `bot.company.com`)
- `your-company.bitrix24.ru` → ваш портал Bitrix24 (например: `mycompany.bitrix24.ru`)
- `your-server` → IP или hostname вашего сервера

**Подробный список замен см. в файле DEPLOY-BITRIX24.md (раздел "Перед началом")**

---

## Краткая инструкция

### 1. Подготовка (5 минут)

```bash
# На сервере
cd /opt
git clone <repository> FAQBot
cd FAQBot

# Настройка .env
cp docker.env.production .env
nano .env
# ОБЯЗАТЕЛЬНО заполните:
#   - BITRIX24_WEBHOOK, BITRIX24_BOT_ID, BITRIX24_CLIENT_ID, BITRIX24_HANDLER_URL
#   - JWT_SECRET, REFRESH_SECRET, SECRET_KEY (сгенерируйте: openssl rand -hex 32)
# ОПЦИОНАЛЬНО (если нужен Telegram бот):
#   - TELEGRAM_TOKEN

# Создание директорий
mkdir -p data
chmod 777 data
```

### 2. Инициализация БД (2 минуты)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python scripts/migrate_data.py
python scripts/migrate_add_logging.py
python scripts/migrate_add_platform.py
python scripts/migrate_add_bitrix24_permissions.py
python scripts/demo_faq.py  # Опционально - демо данные

deactivate
```

### 3. Настройка Docker сети (1 минута)

```bash
# Проверьте имя сети Nginx
docker network ls

# Если нужно, создайте
docker network create nginx_default

# ИЛИ обновите docker-compose.production.yml:
# networks:
#   nginx_default:
#     external: true
#     name: <your_network_name>
```

### 4. Обновление Nginx (3 минуты)

```bash
# Найдите конфиг Nginx
docker ps | grep nginx
docker exec <nginx_container> cat /etc/nginx/conf.d/default.conf > nginx-current.conf

# Откройте nginx-bitrix-only.conf и скопируйте все location блоки
# в секцию server { listen 443 ssl; ... } ПЕРЕД location / { ... }

# Обновите конфиг
nano nginx-current.conf  # Добавьте location блоки из nginx-bitrix-only.conf

# Скопируйте обратно и перезагрузите
docker cp nginx-current.conf <nginx_container>:/etc/nginx/conf.d/default.conf
docker exec <nginx_container> nginx -t
docker exec <nginx_container> nginx -s reload
```

**Location блоки для добавления (из файла nginx-bitrix-only.conf):**

```nginx
# В секцию server { listen 443 ssl; ... } перед location / { ... }

# Админ-панель
location /faq-admin {
    rewrite ^/faq-admin/(.*)$ /$1 break;
    rewrite ^/faq-admin$ / break;
    proxy_pass http://faqbot-web-admin:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_read_timeout 300s;
}

# Bitrix24 webhook
location /faq-bot/webhook/bitrix24 {
    rewrite ^/faq-bot/webhook/bitrix24(.*)$ /webhook/bitrix24$1 break;
    proxy_pass http://faqbot-bitrix24-bot:5002;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_read_timeout 300s;
    limit_except POST { deny all; }
}

# Health checks
location /faq-admin/health {
    rewrite ^/faq-admin/health$ /health break;
    proxy_pass http://faqbot-web-admin:5000;
    access_log off;
}

location /faq-bot/health {
    rewrite ^/faq-bot/health$ /api/health break;
    proxy_pass http://faqbot-bitrix24-bot:5002;
    access_log off;
}
```

### 5. Запуск (5-10 минут первый раз)

```bash
cd /opt/FAQBot

# Сборка
docker-compose -f docker-compose.production.yml build

# Запуск (веб-админка + Bitrix24 бот)
docker-compose -f docker-compose.production.yml up -d

# Если в будущем нужен Telegram бот, добавьте --profile telegram:
# docker-compose -f docker-compose.production.yml --profile telegram up -d

# Логи (первый запуск - скачивание модели ~5 мин)
docker-compose -f docker-compose.production.yml logs -f
```

### 6. Проверка (1 минута)

```bash
# Health checks
curl -k https://your-domain.com/faq-admin/health
# Ожидается: {"status":"ok","faq_count":21}

curl -k https://your-domain.com/faq-bot/webhook/bitrix24
# Ожидается: ответ от Bitrix24 бота

# Браузер
# https://your-domain.com/faq-admin

# Bitrix24
# Отправьте сообщение боту в Bitrix24
```

## Важные URL

- **Админ-панель:** https://your-domain.com/faq-admin
- **Health check админки:** https://your-domain.com/faq-admin/health
- **Health check Bitrix24 бота:** https://your-domain.com/faq-bot/health
- **Bitrix24 webhook:** https://your-domain.com/faq-bot/webhook/bitrix24
- **Bitrix24 OAuth callback:** https://your-domain.com/bitrix24/callback (если используется)
- **Bitrix24 OAuth app:** https://your-domain.com/bitrix24/app (если используется)

## Полезные команды

```bash
# Логи
docker logs -f faqbot-web-admin
docker logs -f faqbot-telegram-bot

# Перезапуск
docker-compose -f docker-compose.production.yml restart

# Остановка
docker-compose -f docker-compose.production.yml down

# Обновление
git pull
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d
```

## Устранение проблем

**502 Bad Gateway:**
```bash
docker-compose -f docker-compose.production.yml ps
docker network inspect nginx_default
```

**Контейнеры не запускаются:**
```bash
docker logs faqbot-web-admin
chmod 777 data/
```

**ChromaDB ошибки:**
```bash
docker exec -it faqbot-web-admin python -c "from src.web.web_admin import retrain_chromadb; retrain_chromadb()"
```

## Автозапуск при перезагрузке

```bash
# Создать systemd сервис (см. DEPLOYMENT.md)
sudo systemctl enable faqbot.service
```

## Резервное копирование

```bash
# Скопировать backup.sh из DEPLOYMENT.md
chmod +x backup.sh
crontab -e
# Добавить: 0 3 * * * /opt/FAQBot/backup.sh
```

---

**Подробная инструкция:** См. DEPLOYMENT.md
**Архитектура проекта:** См. CLAUDE.md
