# ⚡ Быстрый старт FAQBot

## 🐳 Docker (5 минут)

```bash
# 1. Клонируйте проект
git clone <repository-url>
cd FAQBot

# 2. Настройте токен
cp .env.example .env
nano .env  # Укажите TELEGRAM_TOKEN

# 3. Запустите скрипт (интерактивный выбор сервисов)
chmod +x start.sh
./start.sh

# Или запустите напрямую нужные сервисы:
docker-compose run --rm web-admin python migrate_data.py
docker-compose up -d                    # Только Web-админка
# docker-compose --profile telegram up -d  # + Telegram бот
# docker-compose --profile bitrix24 up -d  # + Bitrix24 бот (рекомендуется)
```

**Готово!** Web-админка: http://localhost:5000

## 💻 Без Docker (10 минут)

```bash
# 1. Установите Python 3.8+
python --version

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Настройте токен
cp .env.example .env
nano .env  # Укажите TELEGRAM_TOKEN

# 5. Инициализируйте БД
python migrate_data.py

# 6. Запустите сервисы (в разных терминалах)
python bot.py       # Telegram бот
python web_admin.py # Web админка
```

## 📖 Дальше

- [README.md](README.md) - полная документация
- [DOCKER.md](DOCKER.md) - детальное руководство по Docker
- [README_BITRIX24.md](README_BITRIX24.md) - настройка Bitrix24

## 🆘 Проблемы?

- **Бот не отвечает**: проверьте токен в .env
- **Порт занят**: измените порты в docker-compose.yml
- **Ошибка БД**: запустите `python migrate_data.py`

## 💡 Полезные команды

```bash
# Docker
make help              # Все команды
make logs              # Просмотр логов
make down              # Остановить

# Без Docker
python bot.py          # Запустить Telegram бота
python web_admin.py    # Запустить админку
python migrate_data.py # Пересоздать БД
```
