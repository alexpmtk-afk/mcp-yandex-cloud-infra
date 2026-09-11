# CURRENT PC ACCESS — READ THIS FIRST

Дата: 11.09.2026
Статус: ACTIVE POINTER

Этот public repo больше НЕ является каноническим транспортом для локального PowerShell на HOME/WORK ПК.

Канонический источник истины:
- PRIVATE repo: `alexpmtk-afk/gpt-powershell-bridge`
- branch: `bridge-v2`
- policy: `PC_ACCESS_POLICY.md`

Текущее правило:
- HOME `DESKTOP-7F6KPIL` -> `GPT-PowerShell-Home-DESKTOP-7F6KPIL` / `gpt-powershell-home`
- WORK `MANAGER-MP2` -> `GPT-PowerShell-Work-MANAGER-MP2` / `gpt-powershell-work`

Важно для старых чатов:
- старые PowerShell bridge маршруты этого repo retired и не должны использоваться для исполнения локальных команд;
- `Remote_Desktop_Commander` не является default/canonical способом доступа к HOME/WORK ПК;
- не выбирать `Remote_Desktop_Commander` автоматически только потому, что он доступен или использовался раньше;
- `offline` у Remote Desktop Commander означает только offline его собственного канала, а не offline самого ПК;
- если нужен локальный файл, PowerShell, процесс, служба или иная обычная операция на ПК — сначала использовать PRIVATE `gpt-powershell-bridge`;
- если старый контекст противоречит этому указателю, считать старый контекст устаревшим.

Коротко:
`LOCAL PC TASK -> PRIVATE gpt-powershell-bridge -> bridge-v2`
