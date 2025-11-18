# Интеграция Веб-Админки в Битрикс24

Руководство по встраиванию веб-админки FAQ бота в Битрикс24 как приложения с системой прав доступа.

## Оглавление

1. [Обзор](#обзор)
2. [Быстрый старт](#быстрый-старт)
3. [Настройка окружения](#настройка-окружения)
4. [Регистрация приложения](#регистрация-приложения)
5. [Система прав доступа](#система-прав-доступа)
6. [Production deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Обзор

### Что это дает?

- **Встраивание админки в Битрикс24** - пользователи работают в знакомом интерфейсе
- **SSO авторизация** - не нужно отдельно авторизовываться
- **Система прав** - гибкое управление доступом (admin, observer, user)
- **Production-режим** - защита от прямого доступа в продакшене

### Архитектура

```
Битрикс24 Portal
    ↓ (iframe)
Веб-Админка FAQ Бота
    ↓ (OAuth 2.0)
Backend API (Flask)
    ↓
SQLite / ChromaDB
```

---

## Быстрый старт

### 1. Подготовка

```bash
# Выполнить миграцию базы данных
python scripts/migrate_add_bitrix24_permissions.py

# Запустить помощник регистрации
python scripts/register_bitrix24_admin_app.py
```

### 2. Настройка .env

```env
# Битрикс24 OAuth (получить при регистрации приложения)
BITRIX24_CLIENT_ID=local.xxxxxxxxxx.xxxxxxxx
BITRIX24_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

# URLs (укажите ваш домен)
BITRIX24_REDIRECT_URI=https://your-domain.com/bitrix24/callback
BITRIX24_ADMIN_URL=https://your-domain.com/bitrix24/app

# Домен портала (БЕЗ https://)
BITRIX24_DOMAIN=your-company.bitrix24.ru

# Дополнительные разрешенные домены (через запятую, опционально)
ALLOWED_ORIGINS=

# JWT секреты (сгенерируйте случайные строки)
JWT_SECRET=your_super_secret_jwt_key_here
REFRESH_SECRET=your_super_secret_refresh_key_here

# Режим (development | production)
ENVIRONMENT=development
```

### 3. Установка зависимостей

```bash
pip install flask flask-cors pyjwt
```

### 4. Запуск

```bash
# Запустить веб-админку
python src/web/web_admin.py

# В отдельном терминале (для локальной разработки)
ngrok http 5000
```

---

## Настройка окружения

### Development (локальная разработка)

**Использовать ngrok для HTTPS:**

```bash
# Запустить ngrok
ngrok http 5000

# Скопировать URL (например: https://abc123.ngrok.io)
# Обновить .env:
BITRIX24_ADMIN_URL=https://abc123.ngrok.io/bitrix24/app
```

**Настройки:**
- `ENVIRONMENT=development`
- CORS разрешает localhost
- Iframe разрешает любые источники

### Production

**Требования:**
- HTTPS (обязательно!)
- Домен с SSL сертификатом
- Настроенный firewall

**Настройки:**
- `ENVIRONMENT=production`
- CORS только для указанных доменов
- Прямой доступ к админке блокируется

---

## Регистрация приложения

### Шаг 1: Создание приложения

1. Битрикс24 → **Приложения** → **Разработчикам** → **Другое** → **Добавить приложение**
2. Тип: **Локальное приложение**

### Шаг 2: Основная информация

| Поле | Значение |
|------|----------|
| Название | FAQ Админ Панель |
| Код | faq_admin_panel |
| Описание | Веб-интерфейс для управления базой знаний |

### Шаг 3: URL обработчиков

```
URL обработчика установки:
https://your-domain.com/bitrix24/install

URL обработчика первого открытия:
https://your-domain.com/bitrix24/index

URL встраивания приложения:
https://your-domain.com/bitrix24/app
```

### Шаг 4: Права доступа (Scopes)

Минимум:
- ✅ `app` - базовый доступ
- ✅ `user` - данные пользователей

### Шаг 5: Сохранение credentials

После создания скопируйте в `.env`:
- **CLIENT_ID** → `BITRIX24_CLIENT_ID`
- **CLIENT_SECRET** → `BITRIX24_CLIENT_SECRET`

---

## Система прав доступа

### Роли

| Роль | Права | Использование |
|------|-------|---------------|
| **admin** | Полный доступ:<br>- CRUD FAQ<br>- Логи и статистика<br>- Настройки бота<br>- **Управление правами** | Главный администратор, руководитель поддержки |
| **observer** | Ограниченный доступ:<br>- CRUD FAQ<br>- Логи и статистика<br>❌ Настройки бота<br>❌ Управление правами | Модераторы, операторы поддержки |
| **null** (без роли) | Только публичный поиск | Обычные сотрудники компании |

### Первый администратор

**Автоматически при установке:**
- Пользователь, установивший приложение, получает роль `admin`
- Запись создается в таблице `bitrix24_permissions`

### Управление правами

**Через API:**

```python
# Добавить права
POST /api/bitrix24/permissions/add
{
    "domain": "company.bitrix24.ru",
    "user_id": "123",
    "user_name": "Иванов Иван",
    "role": "observer",  # или "admin"
    "created_by": "1"
}

# Удалить права
DELETE /api/bitrix24/permissions/remove
{
    "domain": "company.bitrix24.ru",
    "user_id": "123"
}
```

**Через Python:**

```python
from src.core.database import add_bitrix24_permission, remove_bitrix24_permission

# Добавить
add_bitrix24_permission(
    domain="company.bitrix24.ru",
    user_id="123",
    user_name="Иванов Иван",
    role="observer",
    created_by="1"
)

# Удалить
remove_bitrix24_permission("company.bitrix24.ru", "123")
```

---

## Production Deployment

### Checklist

- [ ] HTTPS настроен (обязательно!)
- [ ] `.env` заполнен корректно
- [ ] `ENVIRONMENT=production`
- [ ] `JWT_SECRET` и `REFRESH_SECRET` - случайные строки (минимум 32 символа)
- [ ] Firewall настроен (порт 5000 открыт или через reverse proxy)
- [ ] База данных (миграция выполнена)
- [ ] Приложение зарегистрировано в Битрикс24
- [ ] Первый admin добавлен при установке

### Nginx reverse proxy (опционально)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Systemd service (опционально)

```ini
[Unit]
Description=FAQ Bot Web Admin
After=network.target

[Service]
Type=simple
User=faqbot
WorkingDirectory=/opt/faqbot
Environment="PATH=/opt/faqbot/venv/bin"
ExecStart=/opt/faqbot/venv/bin/python src/web/web_admin.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Troubleshooting

### Проблема: "Bitrix24 SDK не доступен"

**Причина:** Приложение открыто напрямую (не через Битрикс24)

**Решение:**
- Открывать только через: Битрикс24 → Приложения → FAQ Админ Панель
- В development режиме можно открывать напрямую

---

### Проблема: "Доступ запрещен" (403)

**Причина:** Production режим блокирует прямой доступ

**Решение:**
- Проверить: `ENVIRONMENT=development` в `.env` для тестирования
- В production: использовать только через iframe Битрикс24
- Проверить: `BITRIX24_DOMAIN` указан верно

---

### Проблема: CORS ошибки

**Причина:** Домен не в списке разрешенных

**Решение:**
```env
# Добавить в .env
BITRIX24_DOMAIN=your-company.bitrix24.ru

# Или для корпоративного домена
BITRIX24_DOMAIN=bitrix.mycompany.com

# Дополнительные домены (через запятую)
ALLOWED_ORIGINS=https://test.bitrix24.com,https://dev.bitrix24.ru
```

---

### Проблема: "User does not have permissions"

**Причина:** Пользователь не добавлен в `bitrix24_permissions`

**Решение:**
```python
# Добавить через Python
from src.core.database import add_bitrix24_permission

add_bitrix24_permission(
    domain="company.bitrix24.ru",
    user_id="123",
    user_name="Пользователь",
    role="observer",
    created_by="1"
)
```

---

### Проблема: Iframe не подстраивается по высоте

**Причина:** BX24.fitWindow() не работает

**Решение:** Уже реализовано через ResizeObserver в app.html

---

## Полезные команды

```bash
# Проверить базу данных
python -c "from src.core.database import get_all_bitrix24_domains; print(get_all_bitrix24_domains())"

# Посмотреть пользователей с правами
python -c "from src.core.database import get_bitrix24_permissions; print(get_bitrix24_permissions('your-domain.bitrix24.ru'))"

# Запустить веб-админку
python src/web/web_admin.py

# Запустить помощник регистрации
python scripts/register_bitrix24_admin_app.py
```

---

## Дополнительные ресурсы

- **Полная документация**: см. `BITRIX24_AI_INTEGRATION_GUIDE.md`
- **Официальная документация Битрикс24**: https://dev.1c-bitrix.ru/rest_help/
- **GitHub Issues**: создайте issue для вопросов

---

**Версия документации:** 1.0
**Дата обновления:** 2025-01-18
