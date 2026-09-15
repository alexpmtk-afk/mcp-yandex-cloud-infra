FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY core ./core
COPY wb_mcp ./wb_mcp
COPY ozon_mcp ./ozon_mcp
COPY ozon_perf_mcp ./ozon_perf_mcp

# The canonical runtime uses the owner-operated Google Apps Script Drive bridge
# with Bridge v3 hardened capabilities. Fail closed before image publication if
# the vendored archive backend loses the canonical env binding, resumable-upload
# session broker, SHA256 metadata, or verified promotion contract.
RUN grep -Fq 'MARKETPLACE_MCP_GOOGLE_DRIVE_BRIDGE_URL' core/archive_google.py \
    && grep -Fq 'MARKETPLACE_MCP_GOOGLE_DRIVE_BRIDGE_SECRET' core/archive_google.py \
    && grep -Fq 'MARKETPLACE_MCP_ARCHIVE_DRIVE_ROOT_ID' core/archive_google.py \
    && grep -Fq '"resumable_start"' core/archive_google.py \
    && grep -Fq '"promote_verified"' core/archive_google.py \
    && grep -Fq 'sha256Checksum' core/archive_google.py

RUN pip install --no-cache-dir . \
    && mkdir -p /opt/yandex \
    && python -c "import urllib.request; urllib.request.urlretrieve('https://storage.yandexcloud.net/cloud-certs/CA.pem','/opt/yandex/YandexInternalRootCA.crt')"

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "core.remote"]
