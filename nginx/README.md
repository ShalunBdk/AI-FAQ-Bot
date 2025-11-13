# Nginx Configuration для FAQBot

## 🎯 Варианты конфигурации

### Вариант 1: Разные поддомены (рекомендуется)

```
admin.yourdomain.com  → Web-админка (порт 5000)
bot.yourdomain.com    → Bitrix24 вебхуки (порт 5002)
```

**Использовать:** `nginx/faqbot.conf`

**Преимущества:**
- Чистое разделение сервисов
- Проще управление SSL сертификатами
- Независимые логи

### Вариант 2: Один домен с путями

```
yourdomain.com/              → Web-админка
yourdomain.com/webhook/bitrix24 → Bitrix24 вебхуки
yourdomain.com/api/          → API endpoints
```

**Использовать:** `nginx/faqbot-single-domain.conf`

**Преимущества:**
- Один домен, один SSL сертификат
- Проще для небольших установок

## 🚀 Быстрый старт

### Локальная установка Nginx

```bash
# 1. Установите Nginx
sudo apt install nginx  # Ubuntu/Debian
# или
sudo yum install nginx  # CentOS/RHEL

# 2. Скопируйте конфигурацию
sudo cp nginx/faqbot.conf /etc/nginx/sites-available/faqbot
sudo ln -s /etc/nginx/sites-available/faqbot /etc/nginx/sites-enabled/

# 3. Отредактируйте домены
sudo nano /etc/nginx/sites-available/faqbot
# Замените yourdomain.com на ваш домен

# 4. Измените proxy_pass для локального использования
# Замените http://web-admin:5000 на http://localhost:5000
# Замените http://bitrix24-bot:5002 на http://localhost:5002

# 5. Проверьте конфигурацию
sudo nginx -t

# 6. Перезапустите Nginx
sudo systemctl restart nginx
```

### Docker Compose с Nginx

```bash
# 1. Запустите FAQBot с Nginx
docker-compose -f docker-compose.yml -f docker-compose.nginx.yml --profile bitrix24 up -d

# 2. Проверьте логи
docker-compose logs nginx

# 3. Проверьте что все работает
curl http://localhost/health/web
curl http://localhost/health/bot
```

## 🔐 Установка SSL (Let's Encrypt)

### Вариант A: Certbot в Docker

```bash
# 1. Получите сертификат для первого домена
docker-compose run --rm certbot certonly --webroot \
  -w /var/www/certbot \
  -d admin.yourdomain.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# 2. Для второго домена (если используете поддомены)
docker-compose run --rm certbot certonly --webroot \
  -w /var/www/certbot \
  -d bot.yourdomain.com \
  --email your-email@example.com \
  --agree-tos

# 3. Раскомментируйте SSL блоки в nginx конфиге

# 4. Перезапустите Nginx
docker-compose restart nginx

# 5. Автоматическое обновление (certbot контейнер обновляет раз в 12 часов)
docker-compose --profile ssl up -d certbot
```

### Вариант B: Certbot локально

```bash
# 1. Установите Certbot
sudo apt install certbot python3-certbot-nginx

# 2. Получите сертификат (автоматическая настройка Nginx)
sudo certbot --nginx -d admin.yourdomain.com -d bot.yourdomain.com

# 3. Автообновление уже настроено через systemd timer
sudo systemctl status certbot.timer
```

## ⚙️ Настройка DNS

Добавьте A-записи в вашем DNS провайдере:

```
# Для варианта с поддоменами:
admin.yourdomain.com.  A  123.45.67.89
bot.yourdomain.com.    A  123.45.67.89

# Для варианта с одним доменом:
yourdomain.com.        A  123.45.67.89
```

Проверьте DNS:
```bash
dig admin.yourdomain.com
dig bot.yourdomain.com
```

## 📝 Настройка .env для Bitrix24

После настройки Nginx обновите `.env`:

```bash
# Для варианта с поддоменами:
BITRIX24_HANDLER_URL=https://bot.yourdomain.com/webhook/bitrix24

# Для варианта с одним доменом:
BITRIX24_HANDLER_URL=https://yourdomain.com/webhook/bitrix24
```

Перезапустите Bitrix24 бота:
```bash
docker-compose restart bitrix24-bot
```

## 🔍 Проверка работы

```bash
# Проверка Web-админки
curl -I http://admin.yourdomain.com
# или
curl -I http://yourdomain.com

# Проверка Bitrix24 endpoint
curl -I http://bot.yourdomain.com/health
# или
curl -I http://yourdomain.com/health/bot

# Проверка SSL
curl -I https://admin.yourdomain.com
```

## 📊 Мониторинг логов

```bash
# Docker Nginx
docker-compose logs -f nginx

# Локальный Nginx
sudo tail -f /var/log/nginx/faqbot-admin-access.log
sudo tail -f /var/log/nginx/faqbot-admin-error.log
sudo tail -f /var/log/nginx/faqbot-bitrix-access.log
```

## 🛡️ Безопасность

### Ограничение доступа к админке

Добавьте в конфигурацию Web-админки:

```nginx
# Доступ только с определенных IP
location / {
    allow 123.45.67.89;  # Офисный IP
    allow 10.0.0.0/8;    # Внутренняя сеть
    deny all;

    proxy_pass http://web-admin:5000;
    # ... остальные настройки
}
```

### Basic Auth для админки

```bash
# Создайте файл паролей
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Добавьте в конфигурацию
auth_basic "Admin Area";
auth_basic_user_file /etc/nginx/.htpasswd;
```

### Rate Limiting

```nginx
# В http блоке /etc/nginx/nginx.conf
http {
    # Ограничение запросов от одного IP
    limit_req_zone $binary_remote_addr zone=faqbot:10m rate=10r/s;

    server {
        location / {
            limit_req zone=faqbot burst=20 nodelay;
            # ...
        }
    }
}
```

## 🐛 Troubleshooting

### Ошибка 502 Bad Gateway

```bash
# Проверьте что сервисы запущены
docker-compose ps

# Проверьте логи
docker-compose logs web-admin
docker-compose logs bitrix24-bot

# Проверьте сеть Docker
docker network inspect faqbot-network
```

### Ошибка 504 Gateway Timeout

Увеличьте таймауты в конфигурации:
```nginx
proxy_connect_timeout 120s;
proxy_send_timeout 120s;
proxy_read_timeout 120s;
```

### Не работает Let's Encrypt

```bash
# Проверьте что порт 80 открыт
sudo netstat -tulpn | grep :80

# Проверьте DNS
dig yourdomain.com

# Проверьте firewall
sudo ufw allow 80
sudo ufw allow 443
```

## 📖 Дополнительная информация

- [Nginx документация](https://nginx.org/ru/docs/)
- [Let's Encrypt](https://letsencrypt.org/ru/)
- [Certbot](https://certbot.eff.org/)
- [Nginx SSL Configuration Generator](https://ssl-config.mozilla.org/)
