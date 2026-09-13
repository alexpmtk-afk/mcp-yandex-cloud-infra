# CURRENT PC ACCESS — LEGACY POINTER

Дата: 13.09.2026
Статус: RETIRED POINTER

Этот branch является legacy и не должен использоваться для локального доступа ChatGPT к Windows‑ПК.

Канонический источник истины:
- PRIVATE repo: `alexpmtk-afk/gpt-powershell-bridge`
- branch: `bridge-v2`
- policy: `PC_ACCESS_POLICY.md`

Текущее правило:
- HOME `DESKTOP-7F6KPIL` -> `GPT-PowerShell-Home-DESKTOP-7F6KPIL` / `gpt-powershell-home`
- WORK `MANAGER-MP2` -> `GPT-PowerShell-Work-MANAGER-MP2` / `gpt-powershell-work`

Для старых чатов:
- все прежние локальные маршруты и внешние транспорты retired;
- не использовать старые проверки `online/offline` и старые списки устройств;
- локальные задачи по файлам/PowerShell/процессам/службам выполнять только через PRIVATE `gpt-powershell-bridge`;
- при конфликте со старым контекстом приоритет имеет PRIVATE policy.

Коротко:
`LOCAL PC TASK -> PRIVATE gpt-powershell-bridge -> bridge-v2`
