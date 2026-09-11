# GPT-PowerShell Bridge v0.1 — LEGACY ROUTING NOTICE

Дата: 11.09.2026
Статус: **WORK RETIRED HERE / HOME LEGACY ONLY**

## Важно для ChatGPT и старых чатов

Рабочий ПК `MANAGER-MP2` больше НЕ управляется через ветку `tooling/powershell-bridge-v0.1` и старый runner `Codex-Bridge-Work-MANAGER-MP2`.

Для любых PowerShell-задач на WORK использовать только новый PRIVATE production-контур:

- Repository: `alexpmtk-afk/gpt-powershell-bridge` (PRIVATE)
- Execution branch: `bridge-v2`
- Runner: `GPT-PowerShell-Work-MANAGER-MP2`
- Label: `gpt-powershell-work`
- Canonical contract: `tools/powershell-bridge/README.md` в private repo

Префиксы и схема `bridge-exec-work:` для WORK считаются устаревшими и не должны использоваться.

HOME (`DESKTOP-7F6KPIL`) пока остаётся legacy-контуром до отдельной миграции пользователя. Поэтому эта ветка сохраняется только ради HOME/истории и не является канонической для WORK.

Исторический v0.1 сохранён в Git history. При необходимости аудита использовать историю commit, а не пытаться возобновлять старый WORK runner.

Короткое правило для любого старого чата:

`WORK PowerShell -> PRIVATE repo alexpmtk-afk/gpt-powershell-bridge -> branch bridge-v2 -> gpt-powershell-work`
