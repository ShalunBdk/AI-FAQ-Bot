.PHONY: help build up down restart logs ps clean init

help: ## Показать эту справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Собрать Docker образы
	docker-compose build

up: ## Запустить только Web-админку
	docker-compose up -d

up-telegram: ## Запустить Web-админку + Telegram бот
	docker-compose --profile telegram up -d

up-bitrix: ## Запустить Web-админку + Bitrix24 бот
	docker-compose --profile bitrix24 up -d

up-all: ## Запустить все сервисы (Web + Telegram + Bitrix24)
	docker-compose --profile telegram --profile bitrix24 up -d

down: ## Остановить все сервисы
	docker-compose down

restart: ## Перезапустить все сервисы
	docker-compose restart

logs: ## Показать логи всех сервисов
	docker-compose logs -f

logs-telegram: ## Показать логи Telegram бота
	docker-compose logs -f telegram-bot

logs-web: ## Показать логи Web админки
	docker-compose logs -f web-admin

logs-bitrix: ## Показать логи Bitrix24 бота
	docker-compose logs -f bitrix24-bot

ps: ## Показать статус контейнеров
	docker-compose ps

clean: ## Остановить и удалить контейнеры, volumes
	docker-compose down -v

rebuild: ## Пересобрать и перезапустить сервисы
	docker-compose down
	docker-compose build
	docker-compose up -d

init: ## Инициализировать базу данных
	@echo "Инициализация базы данных..."
	docker-compose run --rm web-admin python migrate_data.py
	@echo "База данных инициализирована!"

shell-web: ## Открыть shell в контейнере Web админки
	docker-compose exec web-admin bash

shell-telegram: ## Открыть shell в контейнере Telegram бота
	docker-compose --profile telegram exec telegram-bot bash

shell-bitrix: ## Открыть shell в контейнере Bitrix24 бота
	docker-compose --profile bitrix24 exec bitrix24-bot bash

backup: ## Создать резервную копию баз данных
	@echo "Создание резервной копии..."
	@mkdir -p backups
	@cp faq_database.db backups/faq_database_$(shell date +%Y%m%d_%H%M%S).db
	@tar czf backups/chroma_db_$(shell date +%Y%m%d_%H%M%S).tar.gz chroma_db/
	@echo "Резервная копия создана в папке backups/"

stats: ## Показать использование ресурсов контейнерами
	docker stats --no-stream

# Nginx команды
up-nginx: ## Запустить с Nginx прокси (Web + Bitrix24 + Nginx)
	docker-compose -f docker-compose.yml -f docker-compose.nginx.yml --profile bitrix24 up -d

up-nginx-all: ## Запустить все сервисы с Nginx
	docker-compose -f docker-compose.yml -f docker-compose.nginx.yml --profile telegram --profile bitrix24 up -d

logs-nginx: ## Показать логи Nginx
	docker-compose -f docker-compose.yml -f docker-compose.nginx.yml logs -f nginx

ssl-certbot: ## Получить SSL сертификат через Certbot
	@echo "Получение SSL сертификата..."
	@read -p "Введите ваш домен (например, admin.yourdomain.com): " domain; \
	read -p "Введите ваш email: " email; \
	docker-compose -f docker-compose.yml -f docker-compose.nginx.yml run --rm certbot certonly --webroot \
		-w /var/www/certbot \
		-d $$domain \
		--email $$email \
		--agree-tos \
		--no-eff-email

nginx-reload: ## Перезагрузить конфигурацию Nginx
	docker-compose -f docker-compose.yml -f docker-compose.nginx.yml exec nginx nginx -s reload

nginx-test: ## Проверить конфигурацию Nginx
	docker-compose -f docker-compose.yml -f docker-compose.nginx.yml exec nginx nginx -t
