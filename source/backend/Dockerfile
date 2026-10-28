# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

# Отключаем создание .pyc файлов и буферизацию вывода (важно для логов)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости (если нужны, например для psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только requirements — чтобы использовать кэш Docker
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копируем исходники
COPY . .

# По умолчанию порт 8000
ENV PORT=8000

EXPOSE ${PORT}

# Healthcheck — проверяем, что сервис отвечает
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# Запуск через uvicorn. Имя модуля "main:app" — поправьте, если у вас файл называется иначе
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
