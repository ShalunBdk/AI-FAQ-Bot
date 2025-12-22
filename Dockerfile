# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости + Node.js для сборки CSS + шрифты для PDF
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nodejs \
    npm \
    fonts-dejavu \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и constraints
COPY requirements.txt constraints-cpu.txt ./

# Обновляем pip, setuptools и wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Устанавливаем все зависимости с constraints для CPU версии PyTorch
# Это заставит pip установить CPU версию вместо CUDA (~700 MB экономии)
RUN pip install --no-cache-dir \
    -c constraints-cpu.txt \
    -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Копируем все файлы проекта
COPY . .

# Создаем директории для данных если их нет
RUN mkdir -p /app/data/chroma_db

# Устанавливаем npm зависимости и собираем статические файлы
COPY package.json package-lock.json* ./

# Увеличиваем timeout для npm (для медленных сетей)
# Используем --legacy-peer-deps для совместимости
RUN echo "==> Настройка npm timeouts..." && \
    npm config set fetch-timeout 300000 && \
    npm config set fetch-retries 5 && \
    npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm config set progress false && \
    echo "==> Установка npm зависимостей (может занять несколько минут)..." && \
    npm install --legacy-peer-deps --no-audit --no-fund --verbose && \
    echo "==> Загрузка шрифтов..." && \
    python scripts/download_fonts.py && \
    echo "==> Сборка CSS..." && \
    npm run build:css && \
    echo "==> Очистка npm кэша..." && \
    rm -rf node_modules && \
    npm cache clean --force && \
    echo "==> Готово!"

# Переменная окружения для отключения телеметрии
ENV ANONYMIZED_TELEMETRY=False

# Expose порты для сервисов
# 5000 - web admin
# 5001 - telegram bot reload server
# 5002 - bitrix24 bot
EXPOSE 5000 5001 5002

# По умолчанию запускаем bash (команды будут переопределены в docker-compose)
CMD ["bash"]
