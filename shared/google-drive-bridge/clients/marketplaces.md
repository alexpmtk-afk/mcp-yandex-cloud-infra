# Client profile — Marketplaces MCP

Project id: `marketplaces`

## Project boundary

`project_id=marketplaces` covers the whole Marketplaces MCP security/runtime boundary, including domain modules such as WB Advertising / `MCP Реклама` while they remain inside the same Marketplaces MCP runtime and archive layer.

`MCP Реклама` is therefore **not** a third independent Bridge client. It MUST NOT create its own Apps Script deployment, secret, fixed Drive root, Lockbox binding or separate `project_id` unless it is deliberately extracted into an independent MCP/runtime in the future.

Advertising business code should use the shared Marketplaces archive abstraction. Future Advertising Archive V1 datasets must flow through `HybridArchiveStore` / `GoogleDriveArchiveStore` (and the shared large-file transport where applicable), not call Apps Script directly from `core/wb_advertising.py`.

## Required deployment isolation

Marketplaces MUST use its own:
- Apps Script deployment;
- shared secret;
- fixed Drive root;
- Yandex Lockbox credential binding.

It MUST NOT share any of these with Birzha or future independent MCP projects.

## Existing project responsibilities that stay inside Marketplaces

- WB/Ozon API logic;
- WB Advertising / Promotion API logic;
- advertising metrics and business rules (CTR/CPC/CPO/DRR/ROAS and future bid/budget logic);
- Advertising Archive dataset structure and coverage rules;
- archive layout and annual CSV naming;
- `reports_registry.csv` semantics;
- PREPARE/UPLOAD/BACKUP/COMMIT state machine;
- Redis/Valkey queue, rate limits and resource/job locks;
- Yandex Object Storage immutable candidates/job state/backups;
- Semantic Core and business calculations;
- FULL_COVERAGE checks.

Bridge-level locks MUST NOT replace Marketplaces resource locks. New Advertising Archive jobs should prefer resource keys at dataset + cabinet + period/file granularity so unrelated advertising resources can update concurrently.

## Bridge capabilities required

- authenticated/deep `health`;
- `stat` / `metadata_by_id`;
- bounded `read_small` / `write_small`;
- large binary resumable upload;
- direct/streaming large-file download through the Bridge v1 download broker;
- exact byte count + SHA256 verification;
- staged verified promotion;
- retry-safe/idempotent mutating actions;
- fail-closed root validation for every file-id action;
- shortcut rejection;
- safe staging/test cleanup.

Google Sheets chunked transport is not a current requirement for the advertising module.

## Required client changes after bridge v1 acceptance

Adapt once for the whole Marketplaces MCP:
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
Do not add a second advertising-specific bridge client while Advertising remains a Marketplaces subsystem.

## Cutover gate

Do not switch production until all pass:
1. correct project/root health;
2. wrong project id rejected;
3. wrong secret rejected;
4. foreign-root file-id rejected;
5. shortcut escape rejected;
6. small read/write exact hash;
7. large upload exact size/SHA256;
8. large download exact size/SHA256;
9. idempotency replay safe;
10. concurrent independent resources do not block each other;
11. retry after lost response does not create duplicate canonical state;
12. Marketplaces/Birzha cross-project isolation/concurrency acceptance passes.

After Marketplaces cutover, current and future Advertising Archive V1 consumers inherit the same accepted Bridge path automatically.
