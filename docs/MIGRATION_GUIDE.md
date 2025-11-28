# Миграция на локальные статические файлы

## Что изменилось

### До
- ❌ Tailwind CSS загружался с CDN (~300KB, медленно)
- ❌ Google Fonts загружались с внешнего источника
- ❌ Material Icons загружались с Google Fonts CDN
- ❌ Предупреждения в консоли браузера о production использовании CDN
- ❌ Зависимость от внешних сервисов (Google)
- ❌ Медленная загрузка при плохом интернете

### После
- ✅ Tailwind CSS локально: минифицированный `output.css` (~32KB)
- ✅ Шрифты Inter локально (5 weights): ~275KB total
- ✅ Material Icons локально: ~297KB
- ✅ Нет предупреждений в консоли
- ✅ Полная независимость от CDN
- ✅ Быстрая загрузка
- ✅ Работает офлайн
- ✅ Лучший контроль версий

## Для локальной разработки

### 1. Первоначальная установка (один раз)

```bash
# Установите Node.js зависимости
npm install

# Скачайте шрифты локально
python download_fonts.py

# Соберите CSS
npm run build:css
```

### 2. Разработка с автоматической пересборкой

Если вы редактируете шаблоны или стили, запустите в отдельном терминале:

```bash
npm run watch:css
```

Это автоматически пересобирает CSS при изменениях в:
- `src/web/static/css/input.css`
- `src/web/templates/**/*.html`

### 3. Запуск приложения

```bash
# Обычный запуск
python src/web/web_admin.py

# Или через Docker
docker-compose up -d
```

## Для Docker

### Локальная разработка

```bash
# Сначала соберите статические файлы локально
npm install
python download_fonts.py
npm run build:css

# Затем запустите Docker
docker-compose up -d
```

### Production deployment

```bash
# Dockerfile автоматически соберет статические файлы при сборке образа
docker-compose -f docker-compose.production.yml up -d --build
```

Dockerfile теперь:
1. Устанавливает Node.js и npm
2. Скачивает шрифты (`python download_fonts.py`)
3. Собирает CSS (`npm run build:css`)
4. Удаляет node_modules для уменьшения размера образа

## Структура файлов

```
├── package.json                    # npm зависимости
├── tailwind.config.js              # Конфигурация Tailwind
├── download_fonts.py               # Скрипт загрузки шрифтов
├── src/web/static/
│   ├── css/
│   │   ├── input.css              # Исходный CSS
│   │   └── output.css             # Собранный CSS (в .gitignore)
│   └── fonts/
│       ├── inter-*.woff2          # Шрифты Inter
│       └── material-symbols-outlined.woff2
└── src/web/templates/admin/
    ├── index.html                 # Обновлено
    ├── logs.html                  # Обновлено
    ├── settings.html              # Обновлено
    └── permissions.html           # Обновлено
```

## Обновленные файлы

### Конфигурация
- ✅ `package.json` - npm зависимости и скрипты
- ✅ `tailwind.config.js` - конфигурация Tailwind CSS
- ✅ `download_fonts.py` - скрипт загрузки шрифтов
- ✅ `.gitignore` - добавлены node_modules и output.css

### Код
- ✅ `src/web/web_admin.py` - настройка Flask для статических файлов
- ✅ `src/web/static/css/input.css` - исходный CSS с @font-face
- ✅ `src/web/templates/admin/*.html` - все 4 шаблона обновлены

### Docker
- ✅ `docker/Dockerfile` - сборка статических файлов при build
- ✅ `docker/docker-compose.yml` - добавлен volume для static
- ✅ `docker-compose.production.yml` - добавлен volume для static

### Документация
- ✅ `README_ASSETS.md` - полная документация
- ✅ `QUICKSTART_ASSETS.txt` - быстрый старт
- ✅ `MIGRATION_GUIDE.md` - этот файл
- ✅ `CLAUDE.md` - обновлена секция Web Admin

## Troubleshooting

### CSS не применяется

```bash
# Пересоберите CSS
npm run build:css

# Очистите кеш браузера (Ctrl+Shift+R)
```

### Шрифты не отображаются

```bash
# Проверьте наличие файлов
ls src/web/static/fonts/

# Если пусто, скачайте заново
python download_fonts.py
```

### Docker: статические файлы не обновляются

```bash
# Пересоберите образ с --no-cache
docker-compose build --no-cache web-admin
docker-compose up -d
```

### Ошибки npm install

```bash
# Очистите кеш
rm -rf node_modules package-lock.json
npm install
```

## Производительность

### Размеры файлов

| Ресурс | До (CDN) | После (локально) | Экономия |
|--------|----------|------------------|----------|
| Tailwind CSS | ~300KB | 32KB | **89%** |
| Inter fonts | streaming | 275KB | N/A |
| Material Icons | streaming | 297KB | N/A |
| **TOTAL** | ~300KB + streaming | ~604KB | - |

### Время загрузки

- ✅ Все ресурсы кэшируются браузером
- ✅ Нет дополнительных DNS запросов
- ✅ Нет зависимости от скорости CDN
- ✅ Работает при отсутствии интернета

## Git workflow

```bash
# output.css НЕ коммитится (в .gitignore)
git add .
git commit -m "feat: migrate to local Tailwind CSS and fonts"
git push

# Другие разработчики должны выполнить:
git pull
npm install
python download_fonts.py
npm run build:css
```

## Полезные ссылки

- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [Material Symbols](https://fonts.google.com/icons)
- [Inter Font](https://rsms.me/inter/)

---

**Автор миграции**: Claude Code Assistant
**Дата**: 2025-01-25
**Версия**: 1.0
