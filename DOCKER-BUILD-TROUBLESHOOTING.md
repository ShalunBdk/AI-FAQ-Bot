# Docker Build Troubleshooting

Решения проблем при сборке Docker образа.

---

## Проблема: npm install зависает

### Симптомы
```
==> Установка npm зависимостей (может занять несколько минут)...
npm info using npm@9.2.0
npm info using node@v20.19.2
[зависает без прогресса]
```

### Причины
1. Медленное интернет-соединение
2. Проблемы с npm registry
3. IPv6 конфликты
4. Сетевые настройки Docker

---

## Решение 1: Использовать обновленный Dockerfile (РЕКОМЕНДУЕТСЯ)

Основной `Dockerfile` уже обновлен с оптимизациями:
- `--verbose` - показывает прогресс
- `--no-audit` - пропускает проверку безопасности
- `--no-fund` - убирает сообщения о спонсорах
- Увеличенные timeouts

**Попробуйте снова:**
```bash
docker-compose -f docker-compose.production.yml build --no-cache
```

Теперь вы увидите детальный прогресс установки пакетов.

---

## Решение 2: Собрать CSS локально и использовать Dockerfile.no-npm (БЫСТРО)

### Шаг 1: Соберите CSS на локальной машине
```bash
# Установите npm зависимости локально
npm install

# Соберите CSS
npm run build:css
```

### Шаг 2: Используйте Dockerfile.no-npm
```bash
# Сборка без npm (быстрее в 2-3 раза)
docker build -f Dockerfile.no-npm -t faqbot:latest .
```

### Шаг 3: Обновите docker-compose для использования
```yaml
services:
  faqbot-web-admin:
    build:
      context: .
      dockerfile: Dockerfile.no-npm  # Изменить здесь
```

---

## Решение 3: Использовать другой npm registry

### Вариант A: Использовать Taobao mirror (Китай)
```dockerfile
# Добавьте перед npm install в Dockerfile
RUN npm config set registry https://registry.npmmirror.com
```

### Вариант B: Использовать Cloudflare registry
```dockerfile
RUN npm config set registry https://registry.npmjs.cf/
```

---

## Решение 4: Отладка с --progress=plain

Чтобы видеть всё что происходит:
```bash
docker build --progress=plain --no-cache -f Dockerfile -t faqbot:latest .
```

Это покажет каждый шаг в реальном времени.

---

## Решение 5: Временно удалить npm из Dockerfile

Если нужно срочно собрать образ:

### Шаг 1: Соберите CSS локально
```bash
npm install
npm run build:css
```

### Шаг 2: Закомментируйте npm блок в Dockerfile
```dockerfile
# ВРЕМЕННО ОТКЛЮЧЕНО
# RUN echo "==> Установка npm зависимостей..." && \
#     npm install --legacy-peer-deps --no-audit --no-fund --verbose && \
#     npm run build:css && \
#     rm -rf node_modules

# Вместо этого просто загружаем шрифты
RUN python download_fonts.py
```

### Шаг 3: Соберите образ
```bash
docker build -t faqbot:latest .
```

---

## Решение 6: Использовать Docker BuildKit кэш

Ускорьте повторные сборки:

```bash
# Включите BuildKit
export DOCKER_BUILDKIT=1

# Сборка с кэшированием
docker build \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  -t faqbot:latest .
```

При следующей сборке npm install будет из кэша (если package.json не менялся).

---

## Решение 7: Проверить сетевые настройки Docker

### Проблема с IPv6
Отключите IPv6 в Docker daemon.json:
```json
{
  "ipv6": false,
  "dns": ["8.8.8.8", "8.8.4.4"]
}
```

Затем перезапустите Docker:
```bash
# Windows
Restart-Service docker

# Linux
sudo systemctl restart docker
```

---

## Решение 8: Увеличить ресурсы Docker

В Docker Desktop:
1. Settings → Resources
2. Увеличьте:
   - **Memory**: минимум 4 GB
   - **CPU**: минимум 2 cores
   - **Disk**: проверьте свободное место

---

## Решение 9: Использовать multi-stage build

Оптимизированный Dockerfile с multi-stage:

```dockerfile
# Stage 1: Build CSS
FROM node:20-slim AS css-builder
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps --no-audit --no-fund
COPY src/web/static/css/input.css ./
COPY tailwind.config.js ./
RUN npm run build:css

# Stage 2: Python app
FROM python:3.11-slim
WORKDIR /app
# ... остальной код
# Копируем собранный CSS из первого stage
COPY --from=css-builder /build/src/web/static/css/output.css /app/src/web/static/css/
```

---

## Проверка успешной сборки

После любого решения проверьте:

```bash
# Список образов
docker images | grep faqbot

# Запуск контейнера
docker run --rm faqbot:latest python --version

# Проверка CSS
docker run --rm faqbot:latest ls -lh /app/src/web/static/css/output.css
```

Должны увидеть файл `output.css` размером ~50-100 KB.

---

## FAQ

**Q: Сколько должна занимать сборка?**
A: 5-15 минут (зависит от интернета). Если больше 20 минут - зависло.

**Q: Можно ли полностью убрать npm?**
A: Да, используйте `Dockerfile.no-npm` и собирайте CSS локально.

**Q: Почему npm install медленный?**
A: npm загружает много транзитивных зависимостей. Tailwind CSS ~50+ пакетов.

**Q: Безопасно ли использовать --no-audit?**
A: В production лучше оставить audit, но для ускорения сборки можно отключить.

---

## Рекомендуемый порядок действий

1. ✅ **Попробуйте обновленный Dockerfile** (уже с --verbose)
2. ✅ **Если зависает > 10 минут** → Ctrl+C и используйте Dockerfile.no-npm
3. ✅ **Соберите CSS локально**: `npm run build:css`
4. ✅ **Пересоберите с Dockerfile.no-npm**

Это самый быстрый путь к работающему образу.

---

**Последнее обновление**: 2025-01-28
