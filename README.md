# AI FAQ Bot

Интеллектуальный бот для автоматических ответов на часто задаваемые вопросы с каскадным поиском и семантическим пониманием.

## Основные возможности

### Каскадный поиск (4 уровня)
- 🎯 **Exact Match** - точное совпадение (100%)
- 🔑 **Keyword Search** - поиск по ключевым словам (70-95%)
- 🧠 **Semantic Search** - семантический поиск через AI (45-70%)
- ❌ **Fallback** - вежливый отказ с подсказками

### Администрирование
- **Web-админка** - управление FAQ, аналитика, логи
- **Bitrix24 интеграция** - OAuth, встраивание в портал, система прав
- **Горячая перезагрузка** - обновление без перезапуска
- **Экспорт в CSV** - выгрузка статистики

### Платформы
- ✅ **Bitrix24** - основная интеграция (бот + веб-админка)
- 🔄 **Telegram** - опциональная поддержка

## Технологии

- **Backend**: Python 3.11, Flask
- **AI/ML**: ChromaDB, sentence-transformers (multilingual embeddings)
- **Database**: SQLite
- **Frontend**: Tailwind CSS, Quill editor
- **Deploy**: Docker, Nginx

## Быстрый старт

### Production (Bitrix24 only)

```bash
# 1. Настроить окружение
cp docker.env.production .env
# Заполнить BITRIX24_WEBHOOK, BITRIX24_BOT_ID, JWT_SECRET и другие параметры

# 2. Запустить
docker-compose -f docker-compose.production.yml up -d

# 3. Настроить Nginx
# Скопировать location блоки из nginx-bitrix-only.conf
```

### Development (все боты)

```bash
# 1. Настроить .env
cp .env.example .env
# Заполнить TELEGRAM_TOKEN, BITRIX24_WEBHOOK и другие параметры

# 2. Запустить все сервисы
docker-compose up -d

# Или выборочно:
docker-compose --profile telegram up -d      # Только Telegram
docker-compose --profile bitrix24 up -d      # Только Bitrix24
```

## Доступ к сервисам

| Сервис | URL | Порт |
|--------|-----|------|
| Веб-админка | `https://domain.com/faq-admin` | 5000 |
| Bitrix24 webhook | `https://domain.com/faq-bot/webhook/bitrix24` | 5002 |
| Telegram reload | `http://localhost:5001/reload` | 5001 |

## Структура проекта

```
FAQBot/
├── src/
│   ├── bots/          # Telegram и Bitrix24 боты
│   ├── core/          # Поиск, БД, логирование
│   ├── web/           # Flask веб-админка
│   └── api/           # Bitrix24 REST API
├── scripts/           # Миграции, тесты, демо данные
├── docs/              # Подробная документация
└── nginx/             # Конфигурации Nginx
```

## Документация

### Основная
- **[DEPLOY-BITRIX24.md](DEPLOY-BITRIX24.md)** - развертывание с Bitrix24 (production)
- **[CLAUDE.md](CLAUDE.md)** - подробное описание кодовой базы для разработчиков
- **[PRODUCTION-CHECKLIST.md](PRODUCTION-CHECKLIST.md)** - чеклист перед деплоем

### Техническая (в docs/)
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - общее развертывание
- [DOCKER.md](docs/DOCKER.md) - Docker гайд
- [QUICKSTART.md](docs/QUICKSTART.md) - быстрый старт за 5 минут
- [BITRIX24_ADMIN_INTEGRATION.md](docs/BITRIX24_ADMIN_INTEGRATION.md) - OAuth интеграция
- [DOCKER-CPU-OPTIMIZATION.md](docs/DOCKER-CPU-OPTIMIZATION.md) - оптимизация образа (~1.5 ГБ)
- [REVERSE-PROXY-SETUP.md](docs/REVERSE-PROXY-SETUP.md) - настройка BASE_PATH

## Конфигурация

### Обязательные переменные (.env)

```env
# Bitrix24 (для production)
BITRIX24_WEBHOOK=https://company.bitrix24.ru/rest/1/KEY/
BITRIX24_BOT_ID=62
BITRIX24_BOT_CLIENT_ID=your_client_id
BITRIX24_HANDLER_URL=https://domain.com/faq-bot/webhook/bitrix24
BITRIX24_DOMAIN=company.bitrix24.ru

# Безопасность
JWT_SECRET=<сгенерировать: openssl rand -hex 32>
REFRESH_SECRET=<сгенерировать: openssl rand -hex 32>
SECRET_KEY=<сгенерировать: openssl rand -hex 32>

# Режим
ENVIRONMENT=production

# Telegram (опционально)
TELEGRAM_TOKEN=
```

## Первый запуск

```bash
# 1. Инициализация БД
docker exec faqbot-web-admin python scripts/migrate_data.py

# 2. Загрузка демо FAQ (опционально)
docker exec faqbot-web-admin python scripts/demo_faq.py

# 3. Регистрация бота в Bitrix24
docker exec faqbot-bitrix24-bot python scripts/register_bot.py
```

## Обновление FAQ

Через веб-админку `/faq-admin` или API:
- FAQ автоматически переиндексируются в ChromaDB
- Боты получают уведомление о перезагрузке (hot reload)
- Перезапуск контейнеров не требуется

## Мониторинг

```bash
# Логи
docker-compose -f docker-compose.production.yml logs -f

# Статистика поиска
# Веб-админка → Логи → Статистика по уровням поиска

# Health check
curl http://localhost:5000/health
```

## Безопасность

В production режиме (`ENVIRONMENT=production`):
- ✅ CORS проверка (только BITRIX24_DOMAIN)
- ✅ JWT авторизация для всех эндпоинтов
- ✅ Content Security Policy (CSP)
- ✅ Origin validation
- ✅ Ролевая система (admin/observer)

## Лицензия

Внутренний проект компании.
