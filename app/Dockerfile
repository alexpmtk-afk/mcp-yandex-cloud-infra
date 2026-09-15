FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY core ./core
COPY wb_mcp ./wb_mcp
COPY ozon_mcp ./ozon_mcp
COPY ozon_perf_mcp ./ozon_perf_mcp

# Production Marketplaces was explicitly cut over to Google Drive Bridge Protocol v1.
# The generic deploy workflow builds this vendored app snapshot, so fail closed
# before image publication if an older snapshot could restore the legacy v3
# URL/secret binding. Remove neither guard; update the vendored runtime to v1.
RUN grep -Fq 'BRIDGE_RELEASE_V1 = "1.0.0"' core/archive_google.py \
    && grep -Fq 'MARKETPLACE_MCP_GOOGLE_DRIVE_BRIDGE_V1_URL' core/archive_google.py \
    && grep -Fq 'MARKETPLACE_MCP_GOOGLE_DRIVE_BRIDGE_V1_SECRET' core/archive_google.py \
    && grep -Fq 'MARKETPLACE_MCP_GOOGLE_DRIVE_BRIDGE_V1_ROOT_ID' core/archive_google.py

RUN pip install --no-cache-dir . \
    && mkdir -p /opt/yandex \
    && python -c "import urllib.request; urllib.request.urlretrieve('https://storage.yandexcloud.net/cloud-certs/CA.pem','/opt/yandex/YandexInternalRootCA.crt')"

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "core.remote"]
