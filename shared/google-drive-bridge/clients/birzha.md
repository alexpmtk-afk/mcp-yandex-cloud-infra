# Client profile — Birzha Forecast MCP

Project id: `birzha`

## Required deployment isolation

Birzha MUST use its own:
- Apps Script deployment;
- shared secret;
- fixed Drive root (`Биржа / Архив рыночных данных` or the approved current root);
- Yandex Lockbox credential binding.

Birzha MUST NOT use the Marketplaces Apps Script URL, Marketplaces shared secret, or Marketplaces Lockbox key.

## Existing project responsibilities that stay inside Birzha

- MOEX/ALGOPACK access;
- YDB Data Foundation;
- SECID/contract selection;
- D1/H1/M15 policies;
- `D1 / SESSIONS / VERIFIED_RANGES / SYNC_STATUS` domain structure;
- BR/SBER/Si/GOLD/IMOEX/RTSI mapping;
- Forecast/Snapshot/Outcome logic;
- M23 validation;
- YDB orchestration and job state;
- YDB↔Sheets parity policy and decision of what/when to mirror.

## Bridge capabilities required

Core:
- authenticated/deep `health` with `project_id`, root, protocol and release;
- fail-closed file/spreadsheet ancestry validation;
- `request_id` correlation;
- idempotent mutating actions;
- structured retryable errors;
- resource-level serialization remains in YDB/client orchestration.

Google Sheets extension:
- find/ensure approved spreadsheet under fixed root;
- chunked/bounded range writes;
- staged update lifecycle;
- read-back/parity verification;
- digest/SHA256 or stable equivalent over normalized staged data;
- row count and first/last date verification where requested;
- commit/abort/rollback semantics;
- no duplicate creation for pre-bound instruments such as BR.

## Required client changes after bridge v1 acceptance

Adapt:
- `src/birzha/storage/google_sheets_bridge.py`
- `src/birzha/application/market_mirror_sync.py`
- `src/birzha/worker.py`
- config binding
- `terraform/birzha_test/m25_market_mirror.tf`
- `terraform/birzha_test/m24_autonomous_worker.tf`
- M25 tests/acceptance

Remove dependency on:
- Marketplaces Apps Script deployment;
- Marketplaces shared secret;
- Marketplaces Lockbox credential;
- Birzha-specific addon code embedded in the Marketplaces deployment.

Add on every call:
- `project_id=birzha`
- caller-generated `request_id`
- `idempotency_key` for mutating actions

## Cutover gate

Do not switch production until all pass:
1. correct project/root health;
2. wrong project id rejected;
3. wrong secret rejected;
4. foreign-root spreadsheet/file rejected;
5. shortcut escape rejected;
6. chunked Sheets write completes;
7. read-back parity/digest passes;
8. repeated idempotency key is safe;
9. failure mid-write can abort/rollback without corrupting canonical state;
10. Marketplaces and Birzha can operate concurrently without shared locking.
