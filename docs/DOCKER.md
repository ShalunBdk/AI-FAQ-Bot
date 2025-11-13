# 🐳 Docker Guide для FAQBot

Это руководство описывает запуск FAQBot с помощью Docker и Docker Compose.

## 📋 Содержание

- [Быстрый старт](#быстрый-старт)
- [Архитектура](#архитектура)
- [Конфигурация](#конфигурация)
- [Полезные команды](#полезные-команды)
- [Troubleshooting](#troubleshooting)

## 🚀 Быстрый старт

### Предварительные требования

- Docker 20.10+
- Docker Compose 2.0+
- Минимум 2GB свободной оперативной памяти

### Установка Docker

#### Linux (Ubuntu/Debian)
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

#### Windows/Mac
Скачайте и установите [Docker Desktop](https://www.docker.com/products/docker-desktop)

### Запуск проекта

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd FAQBot

# 2. Создайте .env файл
cp .env.example .env
nano .env  # Настройте переменные окружения

# 3. Инициализируйте базу данных
docker-compose run --rm web-admin python migrate_data.py

# 4. Запустите сервисы
# Вариант 1: Только Web-админка
docker-compose up -d

# Вариант 2: Web-админка + Telegram бот
docker-compose --profile telegram up -d

# Вариант 3: Web-админка + Bitrix24 бот (рекомендуется для корпоративного использования)
docker-compose --profile bitrix24 up -d

# Вариант 4: Все сервисы
docker-compose --profile telegram --profile bitrix24 up -d

# 5. Проверьте статус
docker-compose ps
```

**Готово!**
- Web-админка: http://localhost:5000 (всегда доступна)
- Telegram бот: работает если запущен
- Bitrix24 бот: http://localhost:5002 (если запущен)

## 🏗️ Архитектура

### Сервисы

```
                    ┌─────────────────┐
                    │   web-admin     │
                    │   (port 5000)   │ ← Всегда запускается
                    │  [Основной]     │
                    └────────┬────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │                                       │
┌────────┴────────┐                   ┌─────────┴────────┐
│  telegram-bot   │                   │  bitrix24-bot    │
│   (port 5001)   │                   │   (port 5002)    │
│  [Опциональный] │                   │  [Опциональный]  │
└────────┬────────┘                   └─────────┬────────┘
         │                                      │
         └──────────────────┬───────────────────┘
                            │
               ┌────────────┴───────────┐
               │  Shared Volumes:       │
               │  - faq_database.db     │
               │  - chroma_db/          │
               │  - model cache         │
               └────────────────────────┘
```

**Профили запуска:**
- `web-admin` - всегда запускается (основной сервис)
- `telegram-bot` - profile: `telegram` (опциональный)
- `bitrix24-bot` - profile: `bitrix24` (опциональный, рекомендуется)

### Volumes

| Volume | Описание | Назначение |
|--------|----------|------------|
| `./faq_database.db` | SQLite БД | Хранение FAQ, логов, настроек |
| `./chroma_db/` | ChromaDB | Векторные эмбеддинги для поиска |
| `sentence-transformers-cache` | Кэш моделей | Ускорение запуска (не скачивать модель каждый раз) |
| `./templates/` | HTML шаблоны | Шаблоны для web-админки |

### Сети

Все сервисы работают в одной сети `faqbot-network`, что позволяет им взаимодействовать друг с другом.

## ⚙️ Конфигурация

### Переменные окружения (.env)

**Для Telegram бота (если используете):**
```env
TELEGRAM_TOKEN=your_bot_token_here
```

**Для Bitrix24 бота (если используете - рекомендуется):**
```env
BITRIX24_WEBHOOK=https://your-domain.bitrix24.ru/rest/1/xxx/
BITRIX24_BOT_ID=62
BITRIX24_CLIENT_ID=your_client_id
BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24
```

**Опциональные общие настройки:**
```env
# Модель эмбеддингов (по умолчанию: paraphrase-multilingual-MiniLM-L12-v2)
MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2

# Порог схожести 0-100 (по умолчанию: 45)
SIMILARITY_THRESHOLD=45.0

# Bitrix24 (если используете)
BITRIX24_WEBHOOK=https://your-domain.bitrix24.ru/rest/1/xxx/
BITRIX24_BOT_ID=62
BITRIX24_CLIENT_ID=vntu29my52f21kbrx5jzjzctktvgvnbi
BITRIX24_HANDLER_URL=https://your-domain.com/webhook/bitrix24
```

### Health Checks

Контейнеры настроены с health checks для автоматического мониторинга:

- **telegram-bot**: проверка HTTP endpoint `/health` на порту 5001
- **web-admin**: проверка HTTP endpoint `/health` на порту 5000

## 🛠️ Полезные команды

### Использование Makefile (рекомендуется)

```bash
# Показать все доступные команды
make help

# Запуск различных конфигураций
make up              # Только Web-админка
make up-telegram     # Web-админка + Telegram бот
make up-bitrix       # Web-админка + Bitrix24 бот (рекомендуется)
make up-all          # Все сервисы

# Просмотр логов
make logs            # Все сервисы
make logs-telegram   # Только Telegram бот
make logs-bitrix     # Только Bitrix24 бот
make logs-web        # Только Web-админка

# Остановить сервисы
make down

# Пересобрать и перезапустить
make rebuild

# Создать бэкап
make backup
```

### Docker Compose команды

```bash
# Запуск сервисов
docker-compose up -d                                      # Только Web-админка
docker-compose --profile telegram up -d                   # Web + Telegram
docker-compose --profile bitrix24 up -d                   # Web + Bitrix24 (рекомендуется)
docker-compose --profile telegram --profile bitrix24 up -d # Все сервисы

# Остановка
docker-compose down                     # Остановить контейнеры
docker-compose down -v                  # Остановить + удалить volumes

# Логи
docker-compose logs -f                  # Все сервисы
docker-compose logs -f telegram-bot     # Конкретный сервис
docker-compose logs --tail=100 web-admin # Последние 100 строк

# Статус и мониторинг
docker-compose ps                       # Список контейнеров
docker-compose top                      # Процессы внутри контейнеров
docker stats                            # Использование ресурсов

# Перезапуск
docker-compose restart                  # Все сервисы
docker-compose restart telegram-bot     # Конкретный сервис

# Выполнение команд
docker-compose exec telegram-bot bash   # Shell в контейнере
docker-compose exec web-admin python migrate_data.py # Команда в контейнере

# Пересборка
docker-compose build                    # Пересобрать образы
docker-compose up -d --build            # Пересобрать и запустить
```

### Бэкапы

```bash
# Создать бэкап вручную
mkdir -p backups
cp faq_database.db backups/faq_$(date +%Y%m%d).db
tar czf backups/chroma_$(date +%Y%m%d).tar.gz chroma_db/

# Восстановление из бэкапа
docker-compose down
cp backups/faq_YYYYMMDD.db faq_database.db
tar xzf backups/chroma_YYYYMMDD.tar.gz
docker-compose up -d
```

### Обновление приложения

```bash
# Метод 1: С использованием Makefile
make down
git pull
make rebuild

# Метод 2: Вручную
docker-compose down
git pull
docker-compose build
docker-compose up -d
```

## 🐛 Troubleshooting

### Проблема: Контейнер не запускается

```bash
# Проверьте логи
docker-compose logs telegram-bot

# Проверьте переменные окружения
docker-compose config

# Пересоберите образ
docker-compose build --no-cache telegram-bot
docker-compose up -d telegram-bot
```

### Проблема: База данных не найдена

```bash
# Инициализируйте БД
docker-compose run --rm telegram-bot python migrate_data.py

# Проверьте что файл создан
ls -lh faq_database.db
```

### Проблема: Порт уже занят

```bash
# Проверьте какой процесс использует порт
lsof -i :5000  # Linux/Mac
netstat -ano | findstr :5000  # Windows

# Измените порт в docker-compose.yml
ports:
  - "5001:5000"  # внешний:внутренний
```

### Проблема: Мало места на диске

```bash
# Очистите неиспользуемые образы и контейнеры
docker system prune -a

# Очистите volumes (ВНИМАНИЕ: удалит данные!)
docker volume prune
```

### Проблема: Модель sentence-transformers долго скачивается

Модель кэшируется в named volume `sentence-transformers-cache`. При первом запуске может потребоваться время для загрузки (~400MB).

```bash
# Проверьте процесс загрузки
docker-compose logs -f telegram-bot | grep "Downloading"
```

### Проблема: Ошибка ChromaDB "Collection already exists"

```bash
# Удалите папку chroma_db и пересоздайте коллекцию
docker-compose down
rm -rf chroma_db/
docker-compose up -d
# В web-админке нажмите "Переобучить базу знаний"
```

## 🔒 Безопасность

### Production рекомендации

1. **Не коммитьте .env файл**
   ```bash
   # Убедитесь что .env в .gitignore
   echo ".env" >> .gitignore
   ```

2. **Используйте Docker secrets для токенов**
   ```yaml
   # docker-compose.yml
   secrets:
     telegram_token:
       file: ./secrets/telegram_token.txt
   ```

3. **Ограничьте ресурсы контейнеров**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '1'
         memory: 2G
   ```

4. **Используйте read-only файловую систему где возможно**
   ```yaml
   read_only: true
   tmpfs:
     - /tmp
   ```

## 📊 Мониторинг

### Prometheus метрики (будущая фича)

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

## 💡 Полезные ссылки

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [ChromaDB Docker](https://docs.trychroma.com/deployment)

---

**Нужна помощь?** Создайте Issue на GitHub!
