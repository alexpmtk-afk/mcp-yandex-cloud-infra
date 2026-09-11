# CURRENT PC ACCESS — READ THIS FIRST

Дата: 11.09.2026
Статус: ACTIVE POINTER

Этот branch legacy. Для локального доступа ChatGPT к HOME/WORK Windows‑ПК использовать не его, а канонический PRIVATE bridge.

Канонический источник истины:
- PRIVATE repo: `alexpmtk-afk/gpt-powershell-bridge`
- branch: `bridge-v2`
- policy: `PC_ACCESS_POLICY.md`

Текущее правило:
- HOME `DESKTOP-7F6KPIL` -> `GPT-PowerShell-Home-DESKTOP-7F6KPIL` / `gpt-powershell-home`
- WORK `MANAGER-MP2` -> `GPT-PowerShell-Work-MANAGER-MP2` / `gpt-powershell-work`

Для старых чатов:
- старые PowerShell bridge маршруты retired;
- `Remote_Desktop_Commander` не является default/canonical транспортом;
- `offline` у Remote Desktop Commander означает только offline его собственного канала, не самого ПК;
- обычные локальные задачи по файлам/PowerShell/процессам/службам сначала выполнять через PRIVATE `gpt-powershell-bridge`;
- при конфликте со старым контекстом этот файл имеет приоритет.

Коротко:
`LOCAL PC TASK -> PRIVATE gpt-powershell-bridge -> bridge-v2`
