# Client profile — Marketplaces MCP

Project id: `marketplaces`

## Required deployment isolation

Marketplaces MUST use its own:
- Apps Script deployment;
- shared secret;
- fixed Drive root;
- Yandex Lockbox credential binding.

It MUST NOT share any of these with Birzha or future MCP projects.

## Existing project responsibilities that stay inside Marketplaces

- WB/Ozon API logic;
- archive layout and annual CSV naming;
- `reports_registry.csv` semantics;
- PREPARE/UPLOAD/BACKUP/COMMIT state machine;
- Redis/Valkey queue, rate limits and resource/job locks;
- Yandex Object Storage immutable candidates/job state/backups;
- Semantic Core and business calculations;
- FULL_COVERAGE checks.

## Bridge capabilities required

- authenticated/deep `health`;
- `stat` / `metadata_by_id`;
- bounded `read_small` / `write_small`;
- large binary resumable upload;
- direct/streaming large-file download path;
- exact byte count + SHA256 verification;
- staged verified promotion;
- retry-safe/idempotent mutating actions;
- fail-closed root validation for every file-id action;
- safe staging/test cleanup.

## Required client changes after bridge v1 acceptance

Adapt:
- `core/archive_google.py`
- `core/archive_drive_resumable.py`
- `core/archive_resumable_worker.py`
- `core/archive_resumable_diagnostic.py`
- `core/archive_hybrid.py`
- `core/system_map.py`
- architecture/agent docs and bridge tests
- bootstrap/deploy/storage-validation workflows

Add on every call:
- `project_id=marketplaces`
- caller-generated `request_id`
- `idempotency_key` for mutating actions

Do not move Marketplaces queue/orchestration into the bridge.

## Cutover gate

Do not switch production until all pass:
1. correct project/root health;
2. wrong project id rejected;
3. wrong secret rejected;
4. foreign-root file-id rejected;
5. small read/write exact hash;
6. large upload exact size/SHA256;
7. large download exact size/SHA256;
8. idempotency replay safe;
9. concurrent independent resources do not block each other;
10. retry after lost response does not create duplicate canonical state.
