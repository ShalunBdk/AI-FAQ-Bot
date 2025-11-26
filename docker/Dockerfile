# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости + Node.js для сборки CSS
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt и устанавливаем Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Создаем директории для данных если их нет
RUN mkdir -p /app/data/chroma_db

# Устанавливаем npm зависимости и собираем статические файлы
COPY package.json package-lock.json* ./
RUN npm install && \
    python download_fonts.py && \
    npm run build:css && \
    rm -rf node_modules && \
    npm cache clean --force

# Переменная окружения для отключения телеметрии
ENV ANONYMIZED_TELEMETRY=False

# Expose порты для сервисов
# 5000 - web admin
# 5001 - telegram bot reload server
# 5002 - bitrix24 bot
EXPOSE 5000 5001 5002

# По умолчанию запускаем bash (команды будут переопределены в docker-compose)
CMD ["bash"]
