# Сборка статических файлов (CSS, шрифты)

## Обзор

Проект использует локальные версии Tailwind CSS и шрифтов (Inter, Material Symbols Outlined) вместо CDN для повышения производительности и надежности.

## Первоначальная установка

### 1. Установите Node.js и npm
Если у вас еще нет Node.js:
- Скачайте с https://nodejs.org/ (LTS версию)
- Проверьте установку: `node --version` и `npm --version`

### 2. Установите зависимости
```bash
npm install
```

### 3. Скачайте шрифты локально
```bash
python download_fonts.py
```

Это скачает:
- Inter font (regular, 500, 600, 700, 900)
- Material Symbols Outlined icons

Шрифты будут сохранены в `src/web/static/fonts/`

### 4. Соберите CSS
```bash
npm run build:css
```

Это создаст минифицированный `src/web/static/css/output.css`

## Разработка

### Автоматическая пересборка CSS при изменениях
Если вы редактируете HTML шаблоны и хотите, чтобы CSS пересобирался автоматически:

```bash
npm run watch:css
```

Оставьте эту команду запущенной в отдельном терминале во время разработки.

### Ручная пересборка
Если вы внесли изменения в `src/web/static/css/input.css` или шаблоны:

```bash
npm run build:css
```

## Структура файлов

```
├── package.json                    # npm зависимости и скрипты
├── tailwind.config.js              # Конфигурация Tailwind CSS
├── download_fonts.py               # Скрипт для скачивания шрифтов
├── src/web/static/
│   ├── css/
│   │   ├── input.css              # Исходный CSS (Tailwind + custom styles)
│   │   └── output.css             # Скомпилированный CSS (не коммитить в git)
│   └── fonts/
│       ├── inter-*.woff2          # Локальные шрифты Inter
│       └── material-symbols-outlined.woff2  # Material Icons
└── src/web/templates/admin/       # HTML шаблоны
```

## Что было изменено

### До (CDN):
- Tailwind CSS загружался с `cdn.tailwindcss.com` (~300KB, медленно)
- Google Fonts загружались с `fonts.googleapis.com` и `fonts.gstatic.com`
- Material Icons загружались с `fonts.googleapis.com`
- ⚠️ Предупреждения в консоли о production использовании CDN

### После (локально):
- ✅ Tailwind CSS: минифицированный `output.css` (~50-100KB)
- ✅ Шрифты: локальные `.woff2` файлы (быстрая загрузка)
- ✅ Нет предупреждений в консоли
- ✅ Работает офлайн
- ✅ Лучшая производительность

## Troubleshooting

### CSS не применяется после изменений
```bash
# Пересоберите CSS
npm run build:css

# Очистите кеш браузера (Ctrl+Shift+R или Cmd+Shift+R)
```

### Шрифты не загружаются
```bash
# Проверьте наличие файлов шрифтов
ls src/web/static/fonts/

# Если файлов нет, скачайте заново
python download_fonts.py
```

### Ошибки при npm install
```bash
# Удалите node_modules и package-lock.json
rm -rf node_modules package-lock.json

# Установите заново
npm install
```

## Production Deployment

При деплое на production убедитесь, что:

1. ✅ Выполнили `npm run build:css` перед деплоем
2. ✅ Папка `src/web/static/` включена в деплой
3. ✅ Flask настроен для отдачи статических файлов (уже настроено в `web_admin.py`)

## Git

Файл `output.css` не коммитится в git (см. `.gitignore`), поэтому каждый разработчик должен собрать его локально после клонирования:

```bash
git clone <repo>
cd FAQBot
npm install
python download_fonts.py
npm run build:css
```
