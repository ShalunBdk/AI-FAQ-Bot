# Развертывание FAQ-бота для Bitrix24

## Что будет запущено

- ✅ Веб-админка (https://your-domain.com/faq-admin)
- ✅ Bitrix24 бот (webhook: https://your-domain.com/faq-bot/webhook/bitrix24)
- ❌ Telegram бот (не запускается)

---

## ⚠️ Перед началом: Замените общие значения на свои

В этой инструкции используются примеры-заполнители. **ОБЯЗАТЕЛЬНО замените их на ваши реальные данные**:

### 1. Доменные имена и серверы

| Заполнитель | Что это | Ваше значение (пример) |
|-------------|---------|------------------------|
| `your-server` | IP или hostname вашего сервера | `192.168.1.100` или `server.company.com` |
| `your-domain.com` | Публичный домен для доступа к боту | `bot.company.com` или `it.company.ru` |
| `your-company.bitrix24.ru` | Домен вашего портала Bitrix24 | `mycompany.bitrix24.ru` |

**Где заменить:**
- В `.env` файле:
  - `BITRIX24_HANDLER_URL=https://your-domain.com/faq-bot/webhook/bitrix24`
  - `BITRIX24_REDIRECT_URI=https://your-domain.com/bitrix24/callback`
  - `BITRIX24_ADMIN_URL=https://your-domain.com/bitrix24/app`
  - `BITRIX24_DOMAIN=your-company.bitrix24.ru`
- В Nginx конфигурации: все упоминания `your-domain.com`
- При регистрации бота в Bitrix24: URL обработчика событий

### 2. Bitrix24 учетные данные

| Параметр | Где получить | Формат | Пример |
|----------|--------------|--------|--------|
| `BITRIX24_WEBHOOK` | Bitrix24 → Настройки → Разработчикам → Вебхуки | `https://ДОМЕН/rest/ID/КЛЮЧ/` | `https://mycompany.bitrix24.ru/rest/1/abc123def456/` |
| `BITRIX24_BOT_ID` | После регистрации бота (см. шаг "Регистрация бота") | Число | `62` |
| `BITRIX24_BOT_CLIENT_ID` | После регистрации бота (см. шаг "Регистрация бота") | Строка ~40 символов | `vntu29my52f21kbr...` |
| `BITRIX24_OAUTH_CLIENT_ID` | (Опционально) Для OAuth приложения | Строка вида `local.xxx.yyy` | `local.691c0d024180f7.96486428` |

**⚠️ Важно:** `BITRIX24_BOT_CLIENT_ID` (для бота) и `BITRIX24_OAUTH_CLIENT_ID` (для OAuth приложения) - это **разные** параметры!

**Где заменить:** В `.env` файле

### 3. JWT секреты (генерируются)

**Сгенерируйте 3 уникальных ключа:**

```bash
# На сервере выполните:
openssl rand -hex 32  # Для JWT_SECRET
openssl rand -hex 32  # Для REFRESH_SECRET
openssl rand -hex 32  # Для SECRET_KEY
```

Каждая команда выдаст строку из 64 символов. Скопируйте их в `.env`:

```bash
JWT_SECRET=a1b2c3d4e5f6...  # Вставьте результат первой команды
REFRESH_SECRET=f6e5d4c3b2a1...  # Вставьте результат второй команды
SECRET_KEY=1a2b3c4d5e6f...  # Вставьте результат третьей команды
```

### 4. Docker сеть Nginx

Проверьте имя сети вашего Nginx:

```bash
docker network ls | grep nginx
```

Если сеть называется **не** `nginx_default` (например, `nginx_network`), то в файле `docker-compose.production.yml` замените:

```yaml
networks:
  nginx_default:
    external: true
    name: ваше_имя_сети  # Добавьте эту строку с реальным именем
```

### 5. SSL сертификаты в Nginx (если используются)

В файле `nginx-complete-config.conf` (если вы его используете целиком):

```nginx
ssl_certificate /etc/nginx/ssl/your-domain.com.pem;  # Замените на путь к вашему сертификату
ssl_certificate_key /etc/nginx/ssl/your-domain.com-key.pem;  # Замените на путь к ключу
```

---

### ✅ Checklist перед развертыванием

Убедитесь, что вы заменили ВСЕ следующие значения:

**В файле `.env`:**
- [ ] `BITRIX24_WEBHOOK` - ваш реальный вебхук из Bitrix24
- [ ] `BITRIX24_BOT_ID` - получите после регистрации бота (число)
- [ ] `BITRIX24_BOT_CLIENT_ID` - получите после регистрации бота (строка ~40 символов)
- [ ] `BITRIX24_HANDLER_URL` - замените `your-domain.com` на ваш домен
- [ ] `BITRIX24_REDIRECT_URI` - замените `your-domain.com` на ваш домен (если используете OAuth)
- [ ] `BITRIX24_ADMIN_URL` - замените `your-domain.com` на ваш домен (если используете OAuth)
- [ ] `BITRIX24_DOMAIN` - замените `your-company.bitrix24.ru` на ваш портал
- [ ] `JWT_SECRET` - сгенерируйте уникальный ключ
- [ ] `REFRESH_SECRET` - сгенерируйте уникальный ключ
- [ ] `SECRET_KEY` - сгенерируйте уникальный ключ

**В Nginx конфигурации:**
- [ ] Все `your-domain.com` заменены на ваш реальный домен
- [ ] Пути к SSL сертификатам правильные (если используются)

**В docker-compose.production.yml (если нужно):**
- [ ] Имя Docker сети Nginx правильное

**В Bitrix24:**
- [ ] Бот зарегистрирован с правильным URL обработчика событий

---

## Быстрое развертывание

### 1. Клонирование проекта (1 мин)

```bash
ssh user@your-server
cd /opt
git clone <your-repository-url> FAQBot
cd FAQBot
```

### 2. Настройка .env (3 мин)

```bash
cp docker.env.production .env
nano .env
```

**Обязательные переменные:**

```bash
# Bitrix24 бот
BITRIX24_WEBHOOK=https://ваш-портал.bitrix24.ru/rest/1/ваш_ключ/
BITRIX24_BOT_ID=62
BITRIX24_BOT_CLIENT_ID=ваш_bot_client_id
BITRIX24_HANDLER_URL=https://your-domain.com/faq-bot/webhook/bitrix24

# JWT секреты (сгенерируйте: openssl rand -hex 32)
JWT_SECRET=сгенерированный_ключ_32_символа
REFRESH_SECRET=сгенерированный_ключ_32_символа
SECRET_KEY=сгенерированный_ключ_32_символа

# Векторная модель (по умолчанию)
MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
SIMILARITY_THRESHOLD=45

# Окружение
ENVIRONMENT=production
```

**Опциональные (если планируете встраивать админку в Bitrix24):**

```bash
BITRIX24_OAUTH_CLIENT_ID=local.xxxxxxxxxx.xxxxxxxx
BITRIX24_CLIENT_SECRET=ваш_секрет
BITRIX24_REDIRECT_URI=https://your-domain.com/bitrix24/callback
BITRIX24_ADMIN_URL=https://your-domain.com/bitrix24/app
BITRIX24_DOMAIN=ваш-портал.bitrix24.ru
```

### 3. Инициализация БД (2 мин)

```bash
# Создание директорий
mkdir -p data
chmod 777 data

# Установка зависимостей (если нужно запустить миграции локально)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Миграции
python scripts/migrate_data.py
python scripts/migrate_add_logging.py
python scripts/migrate_add_platform.py
python scripts/migrate_add_bitrix24_permissions.py

# Демо-данные (опционально)
python scripts/demo_faq.py

deactivate
```

### 4. Настройка Docker сети (1 мин)

```bash
# Проверьте имя сети Nginx
docker network ls | grep nginx

# Если сеть называется по-другому, обновите docker-compose.production.yml
# или создайте сеть nginx_default:
docker network create nginx_default
```

### 5. Обновление Nginx (3 мин)

```bash
# Найдите контейнер Nginx
docker ps | grep nginx
NGINX_CONTAINER=$(docker ps --format "{{.Names}}" | grep nginx)

# Сохраните текущий конфиг
docker exec $NGINX_CONTAINER cat /etc/nginx/conf.d/default.conf > nginx-backup.conf

# Скопируйте новый конфиг из проекта
cp nginx-backup.conf nginx-updated.conf

# Откройте nginx-updated.conf и добавьте блоки из nginx-bitrix-only.conf
# ПЕРЕД location / { ... } в секции server { listen 443 ssl; ... }
nano nginx-updated.conf
```

**Что нужно добавить (скопируйте из nginx-bitrix-only.conf):**

1. **location /faq-admin** - админ-панель
2. **location /faq-admin/static** - статические файлы
3. **location /faq-admin/health** - health check админки
4. **location /faq-bot/webhook/bitrix24** - Bitrix24 webhook
5. **location /faq-bot/health** - health check бота
6. **location /bitrix24/** (опционально) - OAuth endpoints

```bash
# Загрузите обновленный конфиг
docker cp nginx-updated.conf $NGINX_CONTAINER:/etc/nginx/conf.d/default.conf

# Проверьте конфигурацию
docker exec $NGINX_CONTAINER nginx -t

# Перезагрузите Nginx
docker exec $NGINX_CONTAINER nginx -s reload
```

### 6. Запуск сервисов (5-10 мин первый раз)

```bash
cd /opt/FAQBot

# Сборка образов
docker-compose -f docker-compose.production.yml build

# Запуск веб-админки и Bitrix24 бота
docker-compose -f docker-compose.production.yml up -d

# Проверка статуса
docker-compose -f docker-compose.production.yml ps

# Просмотр логов (первый запуск - скачивание модели ~5 мин)
docker-compose -f docker-compose.production.yml logs -f
```

**Ожидаемый вывод:**

```
faqbot-web-admin       Up      5000/tcp
faqbot-bitrix24-bot    Up      5002/tcp
```

### 7. Проверка работы (2 мин)

```bash
# Health check админки
curl -k https://your-domain.com/faq-admin/health
# Ожидается: {"status":"ok","faq_count":21}

# Health check Bitrix24 бота
curl -k https://your-domain.com/faq-bot/health
# Ожидается: {"status":"ok"}

# Откройте в браузере
# https://your-domain.com/faq-admin
```

---

## Регистрация бота в Bitrix24

### Вариант 1: Автоматическая регистрация

```bash
cd /opt/FAQBot
source venv/bin/activate
python scripts/register_bot.py
```

Скрипт выведет `BOT_ID` и `BOT_CLIENT_ID` - добавьте их в `.env` как `BITRIX24_BOT_ID` и `BITRIX24_BOT_CLIENT_ID`.

### Вариант 2: Ручная регистрация

1. Откройте Bitrix24 → **Настройки** → **Разработчикам** → **Чат-боты**
2. Нажмите **Создать бота**
3. Заполните:
   - **Название:** FAQ Помощник
   - **Код:** FAQBot
   - **Обработчик событий:** https://your-domain.com/faq-bot/webhook/bitrix24
4. Скопируйте `BOT_ID` (число) и `CLIENT_ID` (строка) из карточки бота
5. Добавьте в `.env`:
   ```bash
   BITRIX24_BOT_ID=62  # ← Ваш BOT_ID (число)
   BITRIX24_BOT_CLIENT_ID=vntu29my52f21kbr...  # ← Ваш CLIENT_ID (строка)
   ```
6. Перезапустите контейнеры: `docker-compose -f docker-compose.production.yml restart`

---

## Проверка работы бота

1. В Bitrix24 найдите бота в списке контактов
2. Откройте диалог с ботом
3. Отправьте сообщение `/start` или любой вопрос
4. Бот должен ответить

**Проверка логов:**

```bash
docker logs -f faqbot-bitrix24-bot
```

---

## Управление FAQ

### Через веб-админку

1. Откройте https://your-domain.com/faq-admin
2. **Список FAQ** - просмотр всех вопросов/ответов
3. **Добавить FAQ** - создание нового FAQ
4. **Переобучить базу знаний** - после изменений (обязательно!)
5. **Логи** - просмотр запросов пользователей
6. **Настройки** - изменение текстов бота

### После каждого изменения FAQ

**Обязательно нажмите "Переобучить базу знаний"** или выполните:

```bash
docker exec -it faqbot-web-admin python -c "from src.web.web_admin import retrain_chromadb, notify_bot_reload; retrain_chromadb(); notify_bot_reload()"
```

---

## Автозапуск при перезагрузке сервера

```bash
sudo nano /etc/systemd/system/faqbot.service
```

```ini
[Unit]
Description=FAQ Bot для Bitrix24
Requires=docker.service
After=docker.service network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/FAQBot
ExecStart=/usr/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.production.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable faqbot.service
sudo systemctl start faqbot.service
```

---

## Резервное копирование

```bash
# Создание скрипта
sudo nano /opt/FAQBot/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/faqbot"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup SQLite
cp /opt/FAQBot/data/faq_database.db $BACKUP_DIR/faq_$DATE.db

# Backup ChromaDB
tar czf $BACKUP_DIR/chroma_$DATE.tar.gz /opt/FAQBot/data/chroma_db/

# Удалить старые бэкапы (>30 дней)
find $BACKUP_DIR -name "faq_*.db" -mtime +30 -delete
find $BACKUP_DIR -name "chroma_*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
chmod +x /opt/FAQBot/backup.sh

# Добавить в cron (каждый день в 3:00)
crontab -e
# Добавить: 0 3 * * * /opt/FAQBot/backup.sh >> /var/log/faqbot-backup.log 2>&1
```

---

## Полезные команды

```bash
# Просмотр логов
docker logs -f faqbot-web-admin
docker logs -f faqbot-bitrix24-bot
docker-compose -f docker-compose.production.yml logs -f

# Перезапуск
docker-compose -f docker-compose.production.yml restart

# Остановка
docker-compose -f docker-compose.production.yml down

# Обновление кода
cd /opt/FAQBot
git pull
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d

# Использование ресурсов
docker stats faqbot-web-admin faqbot-bitrix24-bot

# Очистка
docker system prune -a
```

---

## Устранение проблем

### 502 Bad Gateway

```bash
# Проверьте статус контейнеров
docker-compose -f docker-compose.production.yml ps

# Проверьте сеть
docker network inspect nginx_default

# Убедитесь, что контейнеры в сети
docker inspect faqbot-web-admin | grep NetworkMode
```

### ChromaDB ошибки

```bash
# Проверьте права
ls -la data/
sudo chmod -R 777 data/

# Переобучите базу
docker exec -it faqbot-web-admin python -c "from src.web.web_admin import retrain_chromadb; retrain_chromadb()"
```

### Бот не отвечает в Bitrix24

```bash
# Проверьте логи
docker logs -f faqbot-bitrix24-bot

# Проверьте переменные окружения
docker exec faqbot-bitrix24-bot env | grep BITRIX24

# Проверьте webhook endpoint
curl -k https://your-domain.com/faq-bot/webhook/bitrix24

# Проверьте регистрацию бота в Bitrix24
# Bitrix24 → Настройки → Разработчикам → Чат-боты
```

### Hot-reload не работает

```bash
# Проверьте доступность из web-admin
docker exec -it faqbot-web-admin curl http://faqbot-bitrix24-bot:5002/api/health

# Проверьте переменные окружения
docker exec faqbot-web-admin env | grep BOT_HOST
```

---

## Контакты

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте health endpoints
3. Обратитесь к полной документации: **DEPLOYMENT.md**

---

**Версия:** 1.0
**Дата:** 2025-01-18
**Платформа:** Web-админка + Bitrix24 бот (без Telegram)
