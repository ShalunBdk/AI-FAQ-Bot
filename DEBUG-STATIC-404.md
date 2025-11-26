# 🐛 Диагностика: Статика возвращает 404

## Симптомы

Браузер запрашивает: `GET /static/css/output.css` (без BASE_PATH)
Ожидается: `GET /faqbot/static/css/output.css`

**Причина:** Flask генерирует URL без BASE_PATH → ProxyFix не работает или не настроен.

---

## ✅ Пошаговая диагностика

### Шаг 1: Проверьте что код обновлён

```bash
cd /path/to/FAQBot
git status
git log -1 --oneline
```

Должен быть последний коммит с ProxyFix.

### Шаг 2: Проверьте наличие ProxyFix в коде

```bash
grep -n "ProxyFix" src/web/web_admin.py
```

**Ожидаемый вывод:**
```
8:from werkzeug.middleware.proxy_fix import ProxyFix
50:app.wsgi_app = ProxyFix(
```

Если **НЕТ** → `git pull origin main`

### Шаг 3: Проверьте что контейнер пересобран

```bash
# Посмотрите дату сборки образа:
docker images | grep faqbot

# Если дата старая (до сегодня) → пересоберите:
docker compose --profile bitrix24 build web-admin --no-cache
docker compose --profile bitrix24 up -d
```

### Шаг 4: Проверьте BASE_PATH в .env

```bash
cat .env | grep BASE_PATH
```

**Должно быть:**
```
BASE_PATH=/faqbot
```

Если **пусто или нет** → добавьте:

```bash
echo "BASE_PATH=/faqbot" >> .env
docker compose --profile bitrix24 restart web-admin
```

### Шаг 5: Проверьте что Flask видит BASE_PATH

```bash
docker compose exec web-admin env | grep BASE_PATH
```

**Должно быть:**
```
BASE_PATH=/faqbot
```

Если **пусто** → проблема в docker-compose.yml:

```yaml
# В docker-compose.yml должно быть:
services:
  faqbot-web-admin:
    environment:
      - BASE_PATH=${BASE_PATH:-}  # Передаём из .env
```

### Шаг 6: Проверьте nginx конфигурацию

```bash
# Если nginx на хосте:
sudo cat /etc/nginx/sites-available/faqbot | grep -A 10 "location /faqbot"

# Если nginx в docker:
docker compose exec nginx cat /etc/nginx/nginx.conf | grep -A 10 "location /faqbot"
```

**Должно быть:**
```nginx
location /faqbot {
    proxy_pass http://faqbot-web-admin:5000;
    proxy_set_header X-Script-Name /faqbot;  # ← ВАЖНО!
    # ...
}
```

**НЕ должно быть:**
```nginx
# ❌ ПЛОХО:
rewrite ^/faqbot(/.*)$ $1 break;  # ← Это убирает BASE_PATH!
```

Если есть rewrite → уберите его:

```bash
sudo nano /etc/nginx/sites-available/faqbot
# Закомментируйте или удалите строку с rewrite

sudo nginx -t
sudo systemctl reload nginx
```

### Шаг 7: Проверьте логи Flask

```bash
docker compose logs web-admin | grep -i "script_name\|base_path"
```

Если видите ошибки с ProxyFix → возможно werkzeug слишком старый.

### Шаг 8: Проверьте версию werkzeug

```bash
docker compose exec web-admin pip show werkzeug
```

**Должно быть:** Version: 2.x.x или 3.x.x

Если < 2.0 → обновите в requirements.txt:

```
werkzeug>=2.0.0
```

И пересоберите контейнер.

---

## 🔧 Быстрый фикс (если ProxyFix не работает)

### Вариант A: Вернуться к старому способу (ВРЕМЕННО)

В `src/web/web_admin.py`:

```python
# ЗАКОММЕНТИРОВАТЬ ProxyFix:
# app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

# И ИЗМЕНИТЬ static_url_path:
app = Flask(__name__,
            static_folder=static_folder,
            template_folder=template_folder,
            static_url_path=f"{BASE_PATH}/static")  # ВЕРНУТЬ BASE_PATH
```

Пересоберите:

```bash
docker compose --profile bitrix24 build web-admin --no-cache
docker compose --profile bitrix24 up -d
```

### Вариант B: Использовать Blueprint (правильно, но сложнее)

Создайте Blueprint с url_prefix - см. [BASE-PATH-STATIC-FILES-FIX.md](BASE-PATH-STATIC-FILES-FIX.md) → Вариант 3

---

## 📋 Чек-лист проверки

- [ ] Код обновлён (`git pull`)
- [ ] ProxyFix есть в коде (`grep ProxyFix`)
- [ ] Контейнер пересобран (`docker compose build`)
- [ ] BASE_PATH в .env (`cat .env | grep BASE_PATH`)
- [ ] BASE_PATH в контейнере (`docker compose exec web-admin env`)
- [ ] Nginx передаёт X-Script-Name (`grep X-Script-Name`)
- [ ] Nginx НЕ делает rewrite (`grep -v rewrite`)
- [ ] werkzeug >= 2.0 (`pip show werkzeug`)

---

## 🎯 Итоговая проверка

После всех исправлений:

1. **Откройте:** `https://it.virtex-food.ru/faqbot/admin/`
2. **Откройте DevTools:** Network tab
3. **Обновите страницу:** Ctrl+R
4. **Найдите:** `output.css`
5. **Проверьте URL запроса:**
   - ✅ Правильно: `GET /faqbot/static/css/output.css`
   - ❌ Неправильно: `GET /static/css/output.css`

6. **Проверьте статус:**
   - ✅ Status: 200 OK
   - ❌ Status: 404 Not Found

---

## 📞 Если ничего не помогло

Вышлите вывод команд:

```bash
# 1. Версия кода
git log -1 --oneline

# 2. ProxyFix в коде
grep -A 3 "ProxyFix" src/web/web_admin.py

# 3. BASE_PATH
cat .env | grep BASE_PATH
docker compose exec web-admin env | grep BASE_PATH

# 4. Nginx config
sudo cat /etc/nginx/sites-available/faqbot

# 5. Docker compose
cat docker-compose.production.yml

# 6. Логи Flask
docker compose logs web-admin --tail=50
```
