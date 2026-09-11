# GPT-PowerShell Bridge — LEGACY ROUTING NOTICE

Дата: 11.09.2026
Статус: **WORK RETIRED HERE / HOME LEGACY ONLY**

## Важно для ChatGPT и старых чатов

Рабочий ПК `MANAGER-MP2` больше НЕ управляется через этот публичный репозиторий и ветку `tooling/powershell-bridge-v2`.

Для любых PowerShell-задач на WORK использовать только новый PRIVATE production-контур:

- Repository: `alexpmtk-afk/gpt-powershell-bridge` (PRIVATE)
- Execution branch: `bridge-v2`
- Runner: `GPT-PowerShell-Work-MANAGER-MP2`
- Label: `gpt-powershell-work`
- Canonical contract: `tools/powershell-bridge/README.md` в private repo

Старый WORK runner `Codex-Bridge-Work-MANAGER-MP2` остановлен и отключён. Не пытаться запускать WORK-команды через `codex-bridge-work` или через этот public repo.

HOME (`DESKTOP-7F6KPIL`) пока не мигрирован в private-контур и остаётся отдельной legacy-задачей до специальной команды пользователя.

Историческая реализация public bridge сохранена в Git history этой ветки только для аудита/rollback. Она больше не является каноническим WORK-контуром.

Короткое правило для любого старого чата:

`WORK PowerShell -> PRIVATE repo alexpmtk-afk/gpt-powershell-bridge -> branch bridge-v2 -> gpt-powershell-work`
