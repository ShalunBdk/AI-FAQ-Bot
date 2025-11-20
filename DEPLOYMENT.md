# Инструкция по развертыванию FAQ-бота на сервере

## Предварительные требования

Убедитесь, что на сервере установлены:
- Docker (версия 20.10+)
- Docker Compose (версия 1.29+)
- Git

---

## ⚠️ Важно: Замените значения-заполнители

В этой инструкции используются общие примеры:
- `your-domain.com` - замените на ваш реальный домен
- `your-company.bitrix24.ru` - замените на ваш портал Bitrix24
- `your-server` - замените на IP/hostname вашего сервера

**Для полного списка замен см. файл DEPLOY-BITRIX24.md (раздел "⚠️ Перед началом")**

---

## Шаг 1: Подготовка проекта на сервере

### 1.1. Клонирование репозитория

```bash
cd /opt
git clone <your-repository-url> FAQBot
cd FAQBot
```

### 1.2. Создание .env файла

```bash
cp docker.env.production .env
nano .env
```

Заполните следующие обязательные поля:
- `TELEGRAM_TOKEN` - токен Telegram бота (получить у @BotFather)
- `JWT_SECRET` - сгенерируйте: `openssl rand -hex 32`
- `REFRESH_SECRET` - сгенерируйте: `openssl rand -hex 32`
- `SECRET_KEY` - сгенерируйте: `openssl rand -hex 32`

Если используете Bitrix24:
- `BITRIX24_WEBHOOK`
- `BITRIX24_BOT_ID`
- `BITRIX24_CLIENT_ID`
- `BITRIX24_HANDLER_URL=https://your-domain.com/faq-bot/webhook/bitrix24`

### 1.3. Создание директорий для данных

```bash
mkdir -p data
chmod 777 data  # Временно для создания БД
```

### 1.4. Инициализация базы данных

```bash
# Установка Python зависимостей (если нужно запустить скрипты миграции)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Запуск миграций
python scripts/migrate_data.py
python scripts/migrate_add_logging.py
python scripts/migrate_add_platform.py
python scripts/migrate_add_bitrix24_permissions.py

# Загрузка демо-данных (опционально)
python scripts/demo_faq.py

deactivate
```

## Шаг 2: Настройка Docker сети

### 2.1. Проверка существующей сети Nginx

```bash
docker network ls | grep nginx
```

Если сеть называется по-другому (например, `nginx_network` или `default`), обновите `docker-compose.production.yml`:

```yaml
networks:
  nginx_default:
    external: true
    name: <имя_вашей_сети>  # Добавьте эту строку
```

### 2.2. Если сеть не существует, создайте её

```bash
docker network create nginx_default
```

Или подключите к существующей сети:
```bash
# Узнайте имя сети Nginx
docker inspect nginx | grep NetworkMode

# Используйте это имя в docker-compose.production.yml
```

## Шаг 3: Обновление конфигурации Nginx

### 3.1. Добавление конфигурации FAQ-бота в Nginx

Найдите конфигурационный файл Nginx на сервере. Обычно это:
- `/etc/nginx/conf.d/default.conf`
- `/etc/nginx/sites-enabled/default`
- Или внутри контейнера Nginx

**Вариант A: Если Nginx в контейнере**

```bash
# Найдите контейнер Nginx
docker ps | grep nginx

# Скопируйте конфиг из контейнера
docker cp <nginx_container_id>:/etc/nginx/conf.d/default.conf ./nginx-backup.conf

# Добавьте содержимое из файла nginx-faq-config.conf
# в секцию server { ... } перед location / { ... }

# Скопируйте обновленный конфиг обратно
docker cp nginx-complete-config.conf <nginx_container_id>:/etc/nginx/conf.d/default.conf

# Проверьте конфигурацию
docker exec <nginx_container_id> nginx -t

# Перезагрузите Nginx
docker exec <nginx_container_id> nginx -s reload
```

**Вариант B: Если Nginx на хосте**

```bash
# Бэкап текущей конфигурации
sudo cp /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.backup

# Откройте конфиг и добавьте location блоки из nginx-faq-config.conf
sudo nano /etc/nginx/conf.d/default.conf

# Проверьте конфигурацию
sudo nginx -t

# Перезагрузите Nginx
sudo systemctl reload nginx
```

### 3.2. Содержимое для добавления в Nginx

Откройте файл `nginx-faq-config.conf` и скопируйте все `location` блоки в секцию `server { listen 443 ssl; ... }` ПЕРЕД блоком `location / { ... }`.

Основные location блоки:
- `/faq-admin` - админ-панель
- `/faq-admin/static` - статические файлы
- `/faq-bot` - Telegram бот reload endpoint
- `/faq-bot/webhook/bitrix24` - Bitrix24 вебхуки (опционально)

## Шаг 4: Запуск Docker контейнеров

### 4.1. Сборка образов

```bash
cd /opt/FAQBot
docker-compose -f docker-compose.production.yml build
```

### 4.2. Запуск сервисов

**Только Telegram бот:**
```bash
docker-compose -f docker-compose.production.yml up -d faqbot-web-admin faqbot-telegram-bot
```

**С Bitrix24 ботом:**
```bash
docker-compose -f docker-compose.production.yml --profile bitrix24 up -d
```

### 4.3. Проверка запуска

```bash
# Проверка статуса контейнеров
docker-compose -f docker-compose.production.yml ps

# Просмотр логов
docker-compose -f docker-compose.production.yml logs -f
```

Ожидаемый вывод:
```
faqbot-web-admin       Up      5000/tcp
faqbot-telegram-bot    Up      5001/tcp
faqbot-bitrix24-bot    Up      5002/tcp (если включен)
```

### 4.4. Проверка первого запуска

При первом запуске модель sentence-transformers будет скачана (около 400MB). Это может занять 2-5 минут.

Следите за логами:
```bash
docker logs -f faqbot-web-admin
```

Должны увидеть:
```
INFO - ✅ ChromaDB загружена: 21 записей
INFO - 🚀 Веб-админка запущена на http://0.0.0.0:5000
```

## Шаг 5: Проверка работы

### 5.1. Проверка health endpoints

```bash
# Web админка
curl -k https://your-domain.com/faq-admin/health
# Ожидаемый ответ: {"status": "ok", "faq_count": 21}

# Telegram бот
curl -k https://your-domain.com/faq-bot/health
# Ожидаемый ответ: {"status": "ok", "faq_count": 21}
```

### 5.2. Проверка админ-панели

Откройте в браузере:
```
https://your-domain.com/faq-admin
```

Должна открыться админ-панель со списком FAQ.

### 5.3. Проверка Telegram бота

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start`
3. Бот должен ответить приветственным сообщением

### 5.4. Проверка hot-reload

1. Откройте админ-панель: `https://your-domain.com/faq-admin`
2. Добавьте новый FAQ
3. Нажмите кнопку "Переобучить базу знаний"
4. Проверьте логи: `docker logs faqbot-web-admin`
5. Должны увидеть сообщения об успешном уведомлении ботов

## Шаг 6: Настройка автозапуска

### 6.1. Создание systemd сервиса

```bash
sudo nano /etc/systemd/system/faqbot.service
```

Содержимое:
```ini
[Unit]
Description=FAQ Bot Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/FAQBot
ExecStart=/usr/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.production.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

### 6.2. Включение автозапуска

```bash
sudo systemctl daemon-reload
sudo systemctl enable faqbot.service
sudo systemctl start faqbot.service
```

## Шаг 7: Резервное копирование

### 7.1. Создание скрипта бэкапа

```bash
sudo nano /opt/FAQBot/backup.sh
```

Содержимое:
```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/faqbot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup SQLite
cp /opt/FAQBot/data/faq_database.db $BACKUP_DIR/faq_$DATE.db

# Backup ChromaDB
tar czf $BACKUP_DIR/chroma_$DATE.tar.gz /opt/FAQBot/data/chroma_db/

# Удалить бэкапы старше 30 дней
find $BACKUP_DIR -name "faq_*.db" -mtime +30 -delete
find $BACKUP_DIR -name "chroma_*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

### 7.2. Настройка cron

```bash
chmod +x /opt/FAQBot/backup.sh
crontab -e
```

Добавить строку (бэкап каждый день в 3:00 ночи):
```
0 3 * * * /opt/FAQBot/backup.sh >> /var/log/faqbot-backup.log 2>&1
```

## Шаг 8: Мониторинг

### 8.1. Просмотр логов

```bash
# Все логи
docker-compose -f docker-compose.production.yml logs -f

# Только web-admin
docker logs -f faqbot-web-admin

# Только telegram-bot
docker logs -f faqbot-telegram-bot

# Последние 100 строк
docker logs --tail 100 faqbot-web-admin
```

### 8.2. Проверка использования ресурсов

```bash
docker stats faqbot-web-admin faqbot-telegram-bot
```

### 8.3. Настройка алертов (опционально)

Создайте скрипт для проверки health endpoints и отправки уведомлений:

```bash
sudo nano /opt/FAQBot/health-check.sh
```

```bash
#!/bin/bash
WEBHOOK_URL="<your_telegram_webhook_or_email>"

if ! curl -s -f https://your-domain.com/faq-admin/health > /dev/null; then
    echo "FAQ Admin is down!" | mail -s "ALERT: FAQ Bot Down" admin@example.com
    # или отправка в Telegram
fi
```

Добавить в cron (проверка каждые 5 минут):
```
*/5 * * * * /opt/FAQBot/health-check.sh
```

## Шаг 9: Обновление приложения

### 9.1. Обновление кода

```bash
cd /opt/FAQBot
git pull origin main

# Пересборка образов
docker-compose -f docker-compose.production.yml build

# Перезапуск сервисов
docker-compose -f docker-compose.production.yml up -d
```

### 9.2. Обновление без даунтайма

```bash
# Пересборка
docker-compose -f docker-compose.production.yml build

# Перезапуск по одному сервису
docker-compose -f docker-compose.production.yml up -d --no-deps faqbot-web-admin
docker-compose -f docker-compose.production.yml up -d --no-deps faqbot-telegram-bot
```

## Устранение проблем

### Проблема: Контейнеры не видят друг друга

**Решение:**
```bash
# Проверьте сети
docker network inspect nginx_default

# Убедитесь, что все контейнеры в одной сети
docker inspect faqbot-web-admin | grep NetworkMode
docker inspect nginx | grep NetworkMode
```

### Проблема: Nginx возвращает 502 Bad Gateway

**Решение:**
```bash
# Проверьте, что контейнеры запущены
docker-compose -f docker-compose.production.yml ps

# Проверьте логи Nginx
docker logs <nginx_container>

# Проверьте, что имена контейнеров правильные в Nginx конфиге
# Должны быть: faqbot-web-admin, faqbot-telegram-bot
```

### Проблема: ChromaDB не загружается

**Решение:**
```bash
# Проверьте права доступа
ls -la data/
sudo chmod 777 data/chroma_db

# Переобучите базу через админ-панель
# или вручную:
docker exec -it faqbot-web-admin python -c "from src.web.web_admin import retrain_chromadb; retrain_chromadb()"
```

### Проблема: Модель не скачивается

**Решение:**
```bash
# Проверьте интернет-соединение в контейнере
docker exec -it faqbot-web-admin ping -c 3 huggingface.co

# Вручную скачайте модель
docker exec -it faqbot-web-admin python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"
```

### Проблема: Hot-reload не работает

**Решение:**
```bash
# Проверьте переменные окружения
docker exec -it faqbot-web-admin env | grep BOT_HOST

# Проверьте доступность из web-admin
docker exec -it faqbot-web-admin curl http://faqbot-telegram-bot:5001/health

# Проверьте логи
docker logs faqbot-web-admin
```

## Полезные команды

```bash
# Остановка всех сервисов
docker-compose -f docker-compose.production.yml down

# Остановка с удалением volume (ВНИМАНИЕ: удалит кэш модели)
docker-compose -f docker-compose.production.yml down -v

# Перезапуск одного сервиса
docker-compose -f docker-compose.production.yml restart faqbot-web-admin

# Просмотр переменных окружения
docker exec faqbot-web-admin env

# Вход в контейнер
docker exec -it faqbot-web-admin /bin/bash

# Очистка Docker (освобождение места)
docker system prune -a

# Просмотр использования места
docker system df
```

## Контакты и поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте health endpoints
3. Проверьте документацию в README.md и CLAUDE.md
4. Откройте issue в репозитории проекта

---

**Версия документа:** 1.0
**Дата:** 2025-01-18
**Автор:** AI Assistant
