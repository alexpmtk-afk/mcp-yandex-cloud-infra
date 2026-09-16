# Marketplaces MCP — Current Runtime Baseline

Статус: CANONICAL

Этот файл фиксирует текущую рабочую архитектуру Marketplaces MCP. Он предназначен для всех параллельных чатов/агентов, которые меняют runtime, archive layer, deploy или transport.

## 1. Каноническое хранилище

- Google Drive — PRIMARY/source of truth для архивных CSV и registry.
- Корень Drive: `MCP архив базы данных` (`1UVKUcFfDhCDk6nMHX1mWg9cRL05DT-OJ`).
- Yandex Object Storage — durable job state, staging и byte-for-byte backup.
- Архив считается завершённым только после подтверждённой записи канонического результата на Google Drive.

## 2. Канонический Drive transport для Marketplaces

- Marketplaces использует Google Apps Script Bridge V3.
- Runtime secret: `google_drive_bridge_secret` из Yandex Lockbox.
- Runtime env: `MARKETPLACE_MCP_GOOGLE_DRIVE_BRIDGE_URL`, `MARKETPLACE_MCP_GOOGLE_DRIVE_BRIDGE_SECRET`, `MARKETPLACE_MCP_ARCHIVE_DRIVE_ROOT_ID`.
- Marketplaces V1 transport удалён из рабочего runtime и не должен возвращаться как fallback.
- V1 проекта `Биржа` — отдельная подсистема и не относится к Marketplaces.

## 3. Канонический deploy

- Единственный штатный TEST runtime deploy: `.github/workflows/deploy-mcp-test.yml`.
- Vendored runtime source обязан быть зафиксирован в `app/.source-revision` на `alexpmtk-afk/marketplaces-mcp-ru@<commit>`.
- Deploy обязан выбирать ACTIVE Lockbox version с рабочими Marketplaces-ключами, включая `google_drive_bridge_secret`.
- Deploy не должен вводить Marketplaces V1 env/bindings/legacy transport.

## 4. Single-writer защита

Все workflow, способные менять общий Marketplaces TEST runtime, должны использовать:

```yaml
concurrency:
  group: marketplaces-test-runtime-write
  cancel-in-progress: false
  queue: max
```

Смысл: один writer выполняется, остальные ждут. Никакой параллельный чат не должен обходить эту очередь собственным mutating workflow.

## 5. Archive protocol

Для WB weekly finance:

- durable state хранится в Yandex Object Storage;
- staging — Yandex Object Storage;
- annual CSV — canonical Google Drive;
- registry — canonical Google Drive;
- перед повторным `UPLOAD_ANNUAL` обязательна reconciliation с внешним side effect;
- большой annual-файл загружается resumable-чанками;
- candidate проверяется по bytes + SHA256;
- повторный запуск не должен повторять WB-запрос, PREPARE или upload, если точный canonical уже существует.

## 6. Минимальный runtime acceptance

После изменения runtime/deploy/bridge должны быть подтверждены:

- `/healthz` PASS;
- MCP auth PASS;
- Google Drive Bridge V3 PASS;
- правильный Drive root PASS;
- Yandex backup/job-state PASS;
- Redis limiter PASS;
- Semantic runtime PASS;
- live WB PASS;
- live Ozon PASS.

## 7. Запрещённые регрессии

Нельзя:

- возвращать Marketplaces Bridge V1 или legacy fallback;
- менять Drive root на другой архив;
- заменять Google Drive как canonical archive на Object Storage;
- запускать обходной deploy вне общей `marketplaces-test-runtime-write` concurrency group;
- повторно скачивать уже принятый reportId при recovery;
- считать архив COMPLETE до доказанной canonical записи и registry commit.

## 8. Правило изменения baseline

Если меняется storage role, Drive transport, canonical deploy, concurrency contract или archive finalize protocol — этот файл должен быть обновлён в том же PR.

История инцидентов хранится отдельно. Этот документ описывает только текущую рабочую архитектуру.