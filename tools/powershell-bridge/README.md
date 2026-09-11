# GPT-PowerShell Bridge v2 — Operating Contract

Дата: 11.09.2026
Статус: ACTIVE CANDIDATE
Репозиторий: `alexpmtk-afk/mcp-yandex-cloud-infra`
Ветка: `tooling/powershell-bridge-v2`

## Назначение

Bridge v2 даёт ChatGPT управляемый доступ к PowerShell на зарегистрированных Windows self-hosted runners без Desktop Commander и без ручного копирования каждой команды пользователем.

Канал:

`ChatGPT -> GitHub commit -> GitHub Actions -> Windows self-hosted runner -> guard.ps1 -> PowerShell -> Actions log -> ChatGPT`

## Компьютеры

Домашний ПК:
- Machine: `DESKTOP-7F6KPIL`
- Runner: `Codex-Bridge-Service-DESKTOP-7F6KPIL`
- Label: `codex-bridge-service`

Рабочий ПК:
- Machine: `MANAGER-MP2`
- Runner: `Codex-Bridge-Work-MANAGER-MP2`
- Label: `codex-bridge-work`

## Файлы

- `.github/workflows/powershell-bridge.yml` — транспорт и исполнение.
- `tools/powershell-bridge/guard.ps1` — техническая политика безопасности.
- `tools/powershell-bridge/command.ps1` — одна исполняемая команда/задача.

Workflow всегда загружает `guard.ps1` и `command.ps1` из точного triggering commit (`GITHUB_SHA`).

## Режимы

### SAFE

Префиксы:
- `bridge-safe-home:`
- `bridge-safe-work:`

SAFE выполняется без отдельного подтверждения пользователя.
Разрешены только диагностические/read-only PowerShell-команды из allowlist, read-only git/yc операции и сетевые диагностические утилиты.
Динамическое выполнение, файловая запись, .NET method invocation и потенциально секретные чтения блокируются.

### WRITE

Префиксы:
- `bridge-write-home:`
- `bridge-write-work:`

WRITE может выполняться без отдельного подтверждения пользователя, когда действие прямо следует из поставленной пользователем задачи.
Разрешены обычные изменения файлов, репозитория и прикладной конфигурации в пределах прав runner.
Guard блокирует удаление, дисковые операции, reboot/shutdown, ACL/user/service/firewall/Defender mutations, destructive git, Terraform apply/destroy и cloud delete/remove.

### DANGEROUS

Префиксы:
- `bridge-danger-home:`
- `bridge-danger-work:`

В текущей версии всегда fail-closed. Для опасных административных действий должен использоваться отдельный явно одобренный maintenance-механизм. Автоматически такие команды не исполняются.

## Секреты

Никогда не помещать секреты в `command.ps1`, commit message или Actions logs.
Guard блокирует типовые literal secrets, JWT, private keys, чтение Yandex Lockbox payload и обращения к типовым secret/token/password-файлам.
Workflow дополнительно редактирует типовые секретные значения в stdout/stderr.

Секрет должен попадать на ПК/в облако через отдельный secret channel, а bridge может оперировать только ссылкой/именем секрета.

## Порядок исполнения

1. ChatGPT определяет целевой ПК и режим.
2. Записывает ровно одну задачу в `command.ps1`.
3. Делает один commit с соответствующим prefix.
4. GitHub Actions выбирает runner по prefix.
5. Runner загружает command и guard из triggering SHA.
6. `guard.ps1` разрешает или блокирует команду.
7. При PASS команда выполняется.
8. stdout/stderr проходят redaction.
9. ChatGPT читает terminal log до запуска следующей изменяющей команды.

Правило: `one command -> one commit -> one run -> terminal result -> next command`.

## Надёжность

`cancel-in-progress: false`: уже начатая изменяющая команда не прерывается новым запросом.
Jobs одного bridge выполняются последовательно.
Runner остаётся Windows service и не зависит от GUI-сессии пользователя.

## Ограничения service account

Runner обычно работает как `NT AUTHORITY\NETWORK SERVICE`.
Поэтому пользовательский HKCU, mapped drives и интерактивный GUI не считаются доступными автоматически. Для файлов использовать подтверждённые абсолютные пути.

## Fail closed

- parse error -> deny;
- неизвестная SAFE-команда -> deny;
- dynamic execution -> deny;
- возможный literal secret -> deny;
- dangerous operation -> deny;
- предыдущий WRITE run с неопределённым результатом -> сначала аудит log, затем следующая команда.

## Миграция

Старый `tooling/powershell-bridge-v0.1` не изменяется и остаётся rollback-контуром до подтверждённого E2E v2.
После успешного SAFE health test и WRITE smoke test v2 становится основным bridge.
