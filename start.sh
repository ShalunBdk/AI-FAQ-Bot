#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🤖  FAQ Bot - Быстрый старт${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен!${NC}"
    echo "Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose не установлен!${NC}"
    echo "Установите Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✅ Docker и Docker Compose найдены${NC}"
echo ""

# Проверка .env файла
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Файл .env не найден${NC}"
    echo "Создаю .env из .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✅ Файл .env создан${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  ВАЖНО: Отредактируйте .env и укажите TELEGRAM_TOKEN!${NC}"
    echo "Затем запустите скрипт снова."
    exit 0
fi

# Проверка TELEGRAM_TOKEN
if ! grep -q "TELEGRAM_TOKEN=.*[a-zA-Z0-9]" .env; then
    echo -e "${RED}❌ TELEGRAM_TOKEN не настроен в .env!${NC}"
    echo "Откройте .env и укажите токен от @BotFather"
    exit 1
fi

echo -e "${GREEN}✅ Конфигурация найдена${NC}"
echo ""

# Проверка базы данных
if [ ! -f faq_database.db ]; then
    echo -e "${YELLOW}📦 Инициализация базы данных...${NC}"
    docker-compose run --rm web-admin python migrate_data.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ База данных инициализирована${NC}"
    else
        echo -e "${RED}❌ Ошибка при инициализации базы данных${NC}"
        exit 1
    fi
    echo ""
fi

# Выбор ботов для запуска
echo -e "${BLUE}Какие боты запустить?${NC}"
echo "1) Только Web-админка (по умолчанию)"
echo "2) Web-админка + Telegram бот"
echo "3) Web-админка + Bitrix24 бот"
echo "4) Все сервисы (Web-админка + Telegram + Bitrix24)"
echo ""
read -p "Выберите вариант [1-4] (Enter = 1): " choice
choice=${choice:-1}
echo ""

# Определяем профили для запуска
profiles=""
case $choice in
    1)
        echo -e "${BLUE}Запуск: только Web-админка${NC}"
        ;;
    2)
        echo -e "${BLUE}Запуск: Web-админка + Telegram бот${NC}"
        profiles="--profile telegram"
        ;;
    3)
        echo -e "${BLUE}Запуск: Web-админка + Bitrix24 бот${NC}"
        profiles="--profile bitrix24"
        ;;
    4)
        echo -e "${BLUE}Запуск: все сервисы${NC}"
        profiles="--profile telegram --profile bitrix24"
        ;;
    *)
        echo -e "${YELLOW}⚠️  Неверный выбор, запуск только Web-админки${NC}"
        ;;
esac
echo ""

# Запуск сервисов
echo -e "${YELLOW}🚀 Запуск сервисов...${NC}"
docker-compose $profiles up -d

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ Сервисы запущены!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}🌐 Web-админка:${NC} http://localhost:5000"
    if [[ "$choice" == "2" || "$choice" == "4" ]]; then
        echo -e "${BLUE}📱 Telegram бот:${NC} работает в фоне"
    fi
    if [[ "$choice" == "3" || "$choice" == "4" ]]; then
        echo -e "${BLUE}💼 Bitrix24 бот:${NC} http://localhost:5002"
    fi
    echo ""
    echo -e "${YELLOW}Полезные команды:${NC}"
    echo "  docker-compose logs -f          # Просмотр логов"
    echo "  docker-compose ps               # Статус контейнеров"
    echo "  docker-compose down             # Остановить сервисы"
    echo "  make help                       # Все доступные команды"
    echo ""
else
    echo -e "${RED}❌ Ошибка при запуске сервисов${NC}"
    echo "Проверьте логи: docker-compose logs"
    exit 1
fi
