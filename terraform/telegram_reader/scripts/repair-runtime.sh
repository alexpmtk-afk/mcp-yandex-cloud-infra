#!/usr/bin/env bash
set -euo pipefail

STATE_DEV=/dev/disk/by-id/virtio-telegram-state
IMAGE='cr.yandex/crphagvid8e8g5pp4fpe/telegram-news-reader:fdd97c7fa8ca91f4d70d39f89a1188977eea7ee1'
CREDS_ID='e6qgrhklnqgnml4lgn5u'
AUTH_ID='e6qahpv53i53pk07c37n'
SETUP_TOKEN_SHA256='b33311a41482a4a1ccd84a293fdfc1c3097306249147e84f409920b915f07c2f'

mkdir -p /state /opt/telegram-reader
for attempt in $(seq 1 60); do
  [ -e "$STATE_DEV" ] && break
  udevadm settle 2>/dev/null || true
  sleep 2
done
test -e "$STATE_DEV"
if ! blkid "$STATE_DEV" >/dev/null 2>&1; then
  mkfs.ext4 -F "$STATE_DEV"
fi
uuid="$(blkid -s UUID -o value "$STATE_DEV")"
grep -q "$uuid" /etc/fstab || echo "UUID=$uuid /state ext4 defaults,nofail 0 2" >> /etc/fstab
mountpoint -q /state || mount /state
chown 10001:10001 /state
chmod 700 /state

cat >/opt/telegram-reader/Caddyfile <<'EOF'
111-88-248-156.sslip.io {
  handle_path /setup* {
    reverse_proxy 127.0.0.1:8081
  }
  handle {
    reverse_proxy 127.0.0.1:8080
  }
}
EOF

cat >/usr/local/sbin/telegram-reader-launcher <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
CREDS_ID='e6qgrhklnqgnml4lgn5u'
AUTH_ID='e6qahpv53i53pk07c37n'
IMAGE='cr.yandex/crphagvid8e8g5pp4fpe/telegram-news-reader:fdd97c7fa8ca91f4d70d39f89a1188977eea7ee1'
marker=/state/setup.complete

metadata_token() {
  curl -sf -H Metadata-Flavor:Google \
    169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token |
    jq -r .access_token
}
fetch_secret() {
  token="$(metadata_token)"
  curl -sf -H "Authorization: Bearer $token" \
    "https://payload.lockbox.api.cloud.yandex.net/lockbox/v1/secrets/$1/payload"
}

while true; do
  if [ ! -f "$marker" ] || [ ! -f /state/telegram_news.session ] || [ ! -f /state/allowed_chats.yaml ]; then
    sleep 5
    continue
  fi
  creds="$(fetch_secret "$CREDS_ID" 2>/dev/null || true)"
  auth="$(fetch_secret "$AUTH_ID" 2>/dev/null || true)"
  api_id="$(printf '%s' "$creds" | jq -r '.entries[]? | select(.key=="api_id") | .textValue' | head -1)"
  api_hash="$(printf '%s' "$creds" | jq -r '.entries[]? | select(.key=="api_hash") | .textValue' | head -1)"
  api_token="$(printf '%s' "$auth" | jq -r '.entries[]? | select(.key=="bearer_token") | .textValue' | head -1)"
  if [ -z "$api_id" ] || [ "$api_id" = null ] || [ -z "$api_hash" ] || [ "$api_hash" = null ] || [ -z "$api_token" ] || [ "$api_token" = null ]; then
    sleep 5
    continue
  fi

  umask 077
  {
    printf 'TELEGRAM_API_ID=%s\n' "$api_id"
    printf 'TELEGRAM_API_HASH=%s\n' "$api_hash"
    printf '%s\n' 'TELEGRAM_SESSION_PATH=/state/telegram_news'
    printf '%s\n' 'TELEGRAM_DATABASE_PATH=/state/telegram.db'
    printf '%s\n' 'TELEGRAM_WHITELIST_PATH=/state/allowed_chats.yaml'
    printf 'READER_API_TOKEN=%s\n' "$api_token"
    printf '%s\n' 'COLLECT_INTERVAL_SECONDS=60'
    printf '%s\n' 'COLLECT_BOOTSTRAP_LIMIT=200'
  } >/opt/telegram-reader/runtime.env

  docker rm -f telegram-reader >/dev/null 2>&1 || true
  docker run -d --name telegram-reader --restart unless-stopped \
    -p 127.0.0.1:8080:8080 \
    --env-file /opt/telegram-reader/runtime.env \
    -v /state:/state \
    "$IMAGE"
  docker rm -f telegram-reader-setup >/dev/null 2>&1 || true
  exit 0
done
EOF
chmod 0750 /usr/local/sbin/telegram-reader-launcher

cat >/etc/systemd/system/telegram-reader-launcher.service <<'EOF'
[Unit]
Description=Telegram News Reader launcher
Wants=network-online.target docker.service
After=network-online.target docker.service

[Service]
Type=simple
ExecStart=/usr/local/sbin/telegram-reader-launcher
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

metadata_token="$(curl -sf -H Metadata-Flavor:Google \
  169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token | jq -r .access_token)"
echo "$metadata_token" | docker login --username iam --password-stdin cr.yandex >/dev/null
docker pull "$IMAGE" >/dev/null

docker rm -f telegram-reader-setup caddy >/dev/null 2>&1 || true
if [ ! -f /state/setup.complete ]; then
  docker run -d --name telegram-reader-setup --restart unless-stopped --network host \
    -e SETUP_TOKEN_SHA256="$SETUP_TOKEN_SHA256" \
    -e TELEGRAM_CREDENTIALS_SECRET_ID="$CREDS_ID" \
    -e TELEGRAM_SESSION_PATH=/state/telegram_news \
    -e TELEGRAM_WHITELIST_PATH=/state/allowed_chats.yaml \
    -e SETUP_COMPLETE_MARKER=/state/setup.complete \
    -v /state:/state \
    "$IMAGE" \
    uvicorn app.setup_service:app --host 127.0.0.1 --port 8081 --workers 1
fi

docker run -d --name caddy --restart unless-stopped --network host \
  -v /opt/telegram-reader/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v caddy_data:/data -v caddy_config:/config caddy:2-alpine

systemctl daemon-reload
systemctl enable --now telegram-reader-launcher.service

for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8081/healthz | grep -q setup_required; then
    echo 'SETUP_LOCAL_READY=PASS'
    exit 0
  fi
  sleep 2
done

docker logs telegram-reader-setup --tail 100 >&2 || true
exit 1
