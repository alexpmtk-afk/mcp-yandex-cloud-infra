FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY config ./config

RUN mkdir -p /state && useradd --system --uid 10001 telegramreader \
    && chown -R telegramreader:telegramreader /app /state

USER telegramreader

ENV TELEGRAM_SESSION_PATH=/state/telegram_news \
    TELEGRAM_DATABASE_PATH=/state/telegram.db \
    TELEGRAM_WHITELIST_PATH=/app/config/allowed_chats.yaml

EXPOSE 8080
CMD ["uvicorn", "app.service:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
