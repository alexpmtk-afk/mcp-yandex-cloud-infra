# Chat 1 — Marketplaces MCP: правила работы с общим Bridge v1

Эта инструкция становится обязательной после отдельной команды на cutover.
До этой команды production-конфигурацию не менять.

## Роль общего bridge

`Yandex Cloud ↔ Google Drive Bridge v1` — только транспорт и security boundary к Google Drive.
Он НЕ заменяет Marketplaces archive/orchestration.

## Обязательная схема

```text
Marketplaces MCP
→ Marketplaces Redis/Valkey + job state
→ project_id=marketplaces
→ отдельный Marketplaces Apps Script deployment Bridge v1
→ отдельный Marketplaces secret
→ fixed root: MCP архив базы данных
→ Google Drive
```

## Жёсткие правила

1. Никогда не использовать Apps Script deployment, secret, Lockbox или Drive root проекта Birzha.
2. Каждый protected bridge request передаёт `project_id=marketplaces` и новый `request_id`.
3. Любая мутация (`write`, `trash`, `resumable_start`, `promote` и т.п.) передаёт стабильный `idempotency_key` на одну логическую операцию. При retry тот же ключ сохраняется.
4. Durable job state, очередь, rate limits и resource locks остаются в Marketplaces Redis/Valkey/Object Storage.
5. Bridge не должен знать WB/Ozon, кабинеты, registry, FULL_COVERAGE, Semantic Core или бизнес-расчёты.
6. Большие CSV записываются через resumable upload: Apps Script только открывает/проверяет session; bytes идут Yandex → Google напрямую.
7. Canonical файл нельзя уничтожать до проверки staging `size + SHA256` и выполнения проектной backup/commit policy.
8. Любая операция по `file_id` считается допустимой только после fail-closed fixed-root validation со стороны bridge.
9. Secret и resumable session URI запрещено выводить в stdout/logs/ChatGPT.
10. При `retryable=true` использовать bounded exponential backoff; не менять бизнес-состояние до подтверждённого результата.

## Что остаётся главным внутри Marketplaces

- Drive остаётся canonical archive storage согласно Marketplaces system map.
- Yandex Object Storage остаётся candidate/job state/backup согласно проектной политике.
- `reports_registry.csv`, dedup, PREPARE/UPLOAD/BACKUP/COMMIT, WB/Ozon API и Semantic Core остаются внутри Marketplaces.

## Startup / deep health

До разрешения архивных write операция должна проверить:

```text
protocol_version = 1
project_id = marketplaces
root_id = ожидаемый Marketplaces root
fixed_root_file_id_guard = true
```

Несовпадение любого поля = fail closed.

## Production cutover разрешён только после

- wrong secret → denied;
- wrong project_id → denied;
- foreign-root file_id → denied;
- shortcut escape → denied;
- small read/write exact SHA256 → PASS;
- resumable large upload exact size/SHA256 → PASS;
- idempotency replay → PASS;
- независимые ресурсы не блокируют друг друга → PASS;
- утверждён механизм large read для годовых CSV → PASS.

Источник стандарта: `alexpmtk-afk/mcp-yandex-cloud-infra`, `shared/google-drive-bridge/`, Protocol v1.
