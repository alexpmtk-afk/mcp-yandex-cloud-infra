FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ARG TG_WS_PROXY_VERSION=v2.3.3
ARG TG_WS_PROXY_SHA256=4174b8c10efc83d2a1122d472bf13e78e5296b0462783a1eda832ee02b79b444
RUN python -c "import hashlib,os,tarfile,tempfile,urllib.request; url=f'https://github.com/valnesfjord/tg-ws-proxy-rs/releases/download/${TG_WS_PROXY_VERSION}/tg-ws-proxy-x86_64-unknown-linux-musl.tar.gz'; p='/tmp/tg-ws-proxy.tar.gz'; urllib.request.urlretrieve(url,p); actual=hashlib.sha256(open(p,'rb').read()).hexdigest(); assert actual=='${TG_WS_PROXY_SHA256}', (actual,'${TG_WS_PROXY_SHA256}'); d=tempfile.mkdtemp(); tarfile.open(p,'r:gz').extractall(d); src=os.path.join(d,'tg-ws-proxy'); os.replace(src,'/usr/local/bin/tg-ws-proxy'); os.chmod('/usr/local/bin/tg-ws-proxy',0o755)"

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
