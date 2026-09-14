# Chat 2 — Birzha Forecast MCP: правила работы с общим Bridge v1

Эта инструкция становится обязательной после отдельной команды на cutover.
До этой команды production-конфигурацию не менять.

## Роль общего bridge

`Yandex Cloud ↔ Google Drive Bridge v1` — транспорт/security boundary для Drive/Sheets.
Он НЕ заменяет YDB Data Foundation, orchestration или Forecast System.

## Обязательная схема

```text
Yandex Timer / Birzha Worker
→ YDB orchestration
→ project_id=birzha
→ отдельный Birzha Apps Script deployment Bridge v1
→ отдельный Birzha secret
→ отдельный Birzha Lockbox binding
→ fixed root: утверждённый корень Биржа / Архив рыночных данных
→ Google Drive / Google Sheets
```

## Жёсткие правила

1. После cutover запрещено использовать Marketplaces Apps Script URL, Marketplaces secret, Marketplaces Lockbox или Marketplaces Drive root.
2. Каждый protected request передаёт `project_id=birzha` и новый `request_id`.
3. Любая мутация использует стабильный `idempotency_key`; retry той же операции использует тот же ключ.
4. YDB orchestration/job state и resource-level serialization остаются внутри Birzha.
5. Bridge не должен знать MOEX/ALGOPACK, SECID/contract policy, D1/H1/M15, Snapshot/Forecast/Outcome или M23.
6. Любой `file_id`/spreadsheet_id должен проходить fail-closed ancestry validation внутри fixed Birzha root.
7. Drive shortcuts наружу из root запрещены.
8. Google Sheets обновляются через staged/chunked flow; прямое разрушительное перезаписывание canonical sheet без stage/verify запрещено.
9. После chunked write обязательны read-back/parity проверки, включая утверждённые row count/digest/first-last date проверки.
10. Commit выполняется только после verify; при частичной ошибке использовать abort/rollback.
11. Secret запрещено выводить в stdout/logs/ChatGPT.

## Что остаётся главным внутри Birzha

- YDB является Data Foundation согласно архитектуре проекта.
- Решение, что и когда зеркалировать в Sheets, остаётся в Birzha.
- `D1 / SESSIONS / VERIFIED_RANGES / SYNC_STATUS`, instrument mapping и parity policy остаются внутри Birzha.
- Forecast/Snapshot/Outcome не переносятся в bridge.

## Startup / deep health

Перед разрешением mirror write проверить:

```text
protocol_version = 1
project_id = birzha
root_id = ожидаемый Birzha root
google_sheets_chunked = true
fixed_root_file_id_guard = true
```

Несовпадение любого обязательного поля = fail closed.

## Production cutover разрешён только после

- отдельный Birzha deployment создан;
- отдельный Birzha secret/Lockbox создан;
- wrong secret → denied;
- wrong project_id → denied;
- foreign-root spreadsheet/file → denied;
- shortcut escape → denied;
- chunked stage write → PASS;
- read-back parity/digest → PASS;
- idempotency replay → PASS;
- mid-write abort/rollback → PASS;
- совместный тест с работающим Marketplaces не показывает shared locking → PASS.

Источник стандарта: `alexpmtk-afk/mcp-yandex-cloud-infra`, `shared/google-drive-bridge/`, Protocol v1.
