# 🚀 Deployment Guide - Production Setup

## 📐 Архитектура с Nginx

```
                         Internet
                            │
                            ▼
                    ┌───────────────┐
                    │     Nginx     │  ports: 80, 443
                    │  Reverse Proxy│  SSL termination
                    └───────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │   Web-админка    │        │  Bitrix24 Bot    │
    │   (port 5000)    │        │   (port 5002)    │
    │                  │        │   /webhook/      │
    └────────┬─────────┘        └────────┬─────────┘
             │                           │
             └───────────┬───────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │  Shared Storage  │
              │  - PostgreSQL    │
              │  - ChromaDB      │
              │  - Cache         │
              └──────────────────┘
```

## 🎯 Варианты конфигурации Nginx

### Вариант 1: Разные поддомены (рекомендуется)

```
https://admin.company.com   → Web-админка
https://bot.company.com     → Bitrix24 вебхуки
```

**Преимущества:**
- ✅ Чистое разделение
- ✅ Независимые SSL сертификаты
- ✅ Проще управление доступом
- ✅ Отдельные логи

**Файл конфигурации:** `nginx/faqbot.conf`

### Вариант 2: Один домен с путями

```
https://faq.company.com/              → Web-админка
https://faq.company.com/webhook/bitrix24 → Bitrix24 вебхуки
https://faq.company.com/api/          → API
```

**Преимущества:**
- ✅ Один SSL сертификат
- ✅ Проще настройка DNS
- ✅ Меньше доменов

**Файл конфигурации:** `nginx/faqbot-single-domain.conf`

## 🚀 Production Deployment

### Шаг 1: Подготовка сервера

```bash
# Обновите систему
sudo apt update && sudo apt upgrade -y

# Установите Docker и Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установите дополнительные утилиты
sudo apt install -y git make htop
```

### Шаг 2: Клонирование проекта

```bash
# Клонируйте репозиторий
git clone <your-repo-url> /opt/faqbot
cd /opt/faqbot

# Установите правильные права
sudo chown -R $USER:$USER /opt/faqbot
```

### Шаг 3: Настройка DNS

Добавьте A-записи в DNS:

```
# Для варианта с поддоменами:
admin.company.com    A    123.45.67.89
bot.company.com      A    123.45.67.89

# Для варианта с одним доменом:
faq.company.com      A    123.45.67.89
```

Проверьте DNS:
```bash
dig admin.company.com +short
# Должен вернуть ваш IP
```

### Шаг 4: Конфигурация приложения

```bash
# Создайте .env файл
cp .env.example .env

# Отредактируйте настройки
nano .env
```

**Обязательные параметры для Bitrix24:**

```env
# Bitrix24 вебхук (получите в Bitrix24: Настройки → Вебхуки)
BITRIX24_WEBHOOK=https://your-portal.bitrix24.ru/rest/1/your_key/

# Bot ID (получите после регистрации бота)
BITRIX24_BOT_ID=62

# Client ID (получите после регистрации)
BITRIX24_CLIENT_ID=your_client_id_here

# Публичный URL для вебхуков (ваш домен с Nginx)
# Вариант 1 (поддомены):
BITRIX24_HANDLER_URL=https://bot.company.com/webhook/bitrix24

# Вариант 2 (один домен):
# BITRIX24_HANDLER_URL=https://faq.company.com/webhook/bitrix24

# Модель и порог
MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
SIMILARITY_THRESHOLD=45.0
```

### Шаг 5: Настройка Nginx

```bash
# Выберите конфигурацию (поддомены или один домен)
cd nginx

# Вариант 1: Поддомены
nano faqbot.conf
# Замените yourdomain.com на ваши домены:
# admin.company.com и bot.company.com

# Вариант 2: Один домен
nano faqbot-single-domain.conf
# Замените yourdomain.com на faq.company.com
```

### Шаг 6: Инициализация базы данных

```bash
# Вернитесь в корень проекта
cd /opt/faqbot

# Инициализируйте БД
docker-compose run --rm web-admin python migrate_data.py
```

### Шаг 7: Запуск сервисов

```bash
# Запуск с Nginx (Web-админка + Bitrix24 + Nginx)
make up-nginx

# Или вручную:
docker-compose -f docker-compose.yml -f docker-compose.nginx.yml --profile bitrix24 up -d

# Проверьте статус
docker-compose ps
```

### Шаг 8: Получение SSL сертификата

```bash
# Вариант A: Через Makefile (интерактивно)
make ssl-certbot

# Вариант B: Вручную для первого домена
docker-compose -f docker-compose.yml -f docker-compose.nginx.yml run --rm certbot \
  certonly --webroot \
  -w /var/www/certbot \
  -d admin.company.com \
  --email admin@company.com \
  --agree-tos \
  --no-eff-email

# Для второго домена (если используете поддомены)
docker-compose -f docker-compose.yml -f docker-compose.nginx.yml run --rm certbot \
  certonly --webroot \
  -w /var/www/certbot \
  -d bot.company.com \
  --email admin@company.com \
  --agree-tos \
  --no-eff-email
```

### Шаг 9: Активация SSL в Nginx

```bash
# Отредактируйте конфигурацию Nginx
nano nginx/faqbot.conf  # или faqbot-single-domain.conf

# Раскомментируйте SSL блоки (начинаются с # server {)
# Закомментируйте редирект на HTTPS в HTTP блоке
# Раскомментируйте return 301 https://...

# Проверьте конфигурацию
make nginx-test

# Перезагрузите Nginx
make nginx-reload
```

### Шаг 10: Регистрация бота в Bitrix24

```bash
# Зарегистрируйте бота в Bitrix24
docker-compose exec bitrix24-bot python register_bot.py

# Скопируйте CLIENT_ID из вывода и добавьте в .env
nano .env
# BITRIX24_CLIENT_ID=полученный_client_id

# Перезапустите Bitrix24 бота
docker-compose restart bitrix24-bot
```

### Шаг 11: Проверка работы

```bash
# Проверка Web-админки
curl -I https://admin.company.com
curl https://admin.company.com/health

# Проверка Bitrix24 бота
curl -I https://bot.company.com/health
# или
curl -I https://faq.company.com/health/bot

# Проверьте логи
make logs-nginx
make logs-bitrix
make logs-web
```

## 🔐 Безопасность

### Firewall настройки

```bash
# Установите UFW
sudo apt install ufw

# Базовые правила
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Разрешите SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Включите firewall
sudo ufw enable
```

### Ограничение доступа к админке

Добавьте в `nginx/faqbot.conf`:

```nginx
location / {
    # Доступ только с офисного IP
    allow 203.0.113.0/24;  # Офисная сеть
    deny all;

    proxy_pass http://web-admin:5000;
    # ... остальные настройки
}
```

### Basic Auth для админки

```bash
# Создайте пользователя
docker-compose exec nginx sh -c "echo -n 'admin:' >> /etc/nginx/.htpasswd"
docker-compose exec nginx sh -c "openssl passwd -apr1 >> /etc/nginx/.htpasswd"

# Добавьте в конфигурацию Nginx для Web-админки:
# auth_basic "Admin Area";
# auth_basic_user_file /etc/nginx/.htpasswd;
```

## 📊 Мониторинг и логи

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Конкретные сервисы
make logs-nginx
make logs-web
make logs-bitrix

# Nginx access logs
tail -f nginx/logs/faqbot-admin-access.log
tail -f nginx/logs/faqbot-bitrix-access.log
```

### Мониторинг ресурсов

```bash
# Использование ресурсов контейнерами
make stats

# Или детальнее
docker stats

# Проверка места на диске
df -h
du -sh /opt/faqbot/*
```

## 🔄 Обновление приложения

```bash
# 1. Создайте бэкап
make backup

# 2. Остановите сервисы
docker-compose down

# 3. Получите обновления
git pull

# 4. Пересоберите образы
docker-compose build

# 5. Запустите обновленные сервисы
make up-nginx

# 6. Проверьте логи
make logs
```

## 🆘 Troubleshooting

### Nginx: 502 Bad Gateway

```bash
# Проверьте что сервисы запущены
docker-compose ps

# Проверьте сеть
docker network inspect faqbot-network

# Проверьте логи бэкенда
docker-compose logs web-admin
docker-compose logs bitrix24-bot
```

### SSL сертификат не получен

```bash
# Проверьте DNS
dig admin.company.com +short

# Проверьте что порт 80 доступен
sudo netstat -tulpn | grep :80

# Проверьте логи Certbot
docker-compose logs certbot

# Попробуйте вручную с staging сервером
docker-compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d admin.company.com \
  --staging \
  --email admin@company.com \
  --agree-tos
```

### Bitrix24 не получает вебхуки

```bash
# Проверьте URL в .env
cat .env | grep BITRIX24_HANDLER_URL

# Проверьте что endpoint доступен извне
curl -X POST https://bot.company.com/webhook/bitrix24 \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Проверьте логи
docker-compose logs bitrix24-bot | grep webhook
```

## 📈 Масштабирование

### Несколько серверов

Используйте Docker Swarm или Kubernetes:

```bash
# Docker Swarm
docker swarm init
docker stack deploy -c docker-compose.yml faqbot

# Load balancer перед Nginx для распределения нагрузки
```

### База данных (переход на PostgreSQL)

Для больших нагрузок замените SQLite на PostgreSQL:

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: faqbot
      POSTGRES_USER: faqbot
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:
```

## ✅ Checklist перед запуском в production

- [ ] DNS записи настроены и работают
- [ ] `.env` файл настроен с production параметрами
- [ ] SSL сертификаты получены и активированы
- [ ] Firewall настроен (только 22, 80, 443)
- [ ] Bitrix24 бот зарегистрирован и CLIENT_ID получен
- [ ] Бэкапы настроены (cron job)
- [ ] Мониторинг логов настроен
- [ ] Basic Auth или IP ограничения для админки
- [ ] Тестовые вебхуки от Bitrix24 работают
- [ ] Health checks проходят успешно

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи: `make logs`
2. Проверьте статус: `docker-compose ps`
3. Проверьте конфигурацию: `make nginx-test`
4. Создайте issue на GitHub с описанием проблемы и логами
