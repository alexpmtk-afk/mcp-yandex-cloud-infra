# GPT-PowerShell Bridge v2 — Operating Contract

Дата: 11.09.2026
Статус: WORK E2E VALIDATED / SERVICE HARDENED / PRODUCTION ISOLATION PENDING
Репозиторий: `alexpmtk-afk/mcp-yandex-cloud-infra`
Ветка: `tooling/powershell-bridge-v2`

## Назначение

Bridge v2 даёт ChatGPT управляемый доступ к PowerShell на Windows self-hosted runners без Desktop Commander и без ручного копирования обычных команд пользователем.

Канал:
`ChatGPT -> GitHub commit -> GitHub Actions -> Windows self-hosted runner -> guard.ps1 -> PowerShell -> Actions log -> ChatGPT`

## Компьютеры

HOME — отложен до отдельной проверки:
- Machine: `DESKTOP-7F6KPIL`
- Runner: `Codex-Bridge-Service-DESKTOP-7F6KPIL`
- Label: `codex-bridge-service`

WORK — E2E подтверждён:
- Machine: `MANAGER-MP2`
- Runner: `Codex-Bridge-Work-MANAGER-MP2`
- Label: `codex-bridge-work`
- Runner version: `2.337.0`
- Service account: `NT AUTHORITY\NETWORK SERVICE`

## Файлы

- `.github/workflows/powershell-bridge.yml` — транспорт и исполнение.
- `tools/powershell-bridge/guard.ps1` — политика безопасности.
- `tools/powershell-bridge/command.ps1` — одна исполняемая задача.
- `tools/powershell-bridge/bootstrap-runner-watchdog.ps1` — одноразовый elevated bootstrap Windows service.

Workflow делает checkout точного triggering commit через `${{ github.sha }}` и `actions/checkout@v7`. Command и guard всегда берутся из одного exact SHA. `persist-credentials: false`.

## Режимы

### SAFE
Префиксы: `bridge-safe-home:` / `bridge-safe-work:`.
Выполняется автоматически. Разрешён только узкий allowlist диагностических/read-only команд. Dynamic execution, file redirection, .NET method invocation, секретные чтения и неизвестные команды блокируются.

### WRITE
Префиксы: `bridge-write-home:` / `bridge-write-work:`.
Выполняется автоматически только после PASS guard и только в разрешённой области.

Текущий canonical writable root:
`C:\ProgramData\ChatGPT-PK`

Разрешены только явно allowlisted file cmdlets с literal path. Path traversal и запись вне canonical root блокируются. Destructive OS/admin/cloud/git operations блокируются.

### DANGEROUS
Префиксы: `bridge-danger-home:` / `bridge-danger-work:`.
Всегда fail-closed. Для опасных административных действий нужен отдельный явно одобренный maintenance path.

## Секреты

Никогда не помещать password/token/JWT/PAT/private key/OAuth secret/marketplace token/Lockbox payload в `command.ps1`, commit message или вывод.
Guard блокирует типовые literal secrets и секретные источники. Workflow дополнительно маскирует Bearer/password/api-key/client-secret/access-token/refresh-token/JWT-подобный output.

Redaction — только defense-in-depth. Главное правило: секрет вообще не должен попадать в Git или stdout/stderr.

## Порядок исполнения

`one task -> one commit -> one run -> terminal result -> next modifying task`

ChatGPT обязан дождаться terminal result и прочитать log перед следующим WRITE. После неопределённого WRITE запрещён слепой retry: сначала проверяется фактическое состояние.

## Concurrency / race

- `cancel-in-progress: false` — начатая команда не отменяется новой.
- HOME и WORK имеют отдельные concurrency groups.
- Exact triggering SHA исключает подмену command/guard более новым commit.
- GitHub concurrency не считается безграничной FIFO-очередью: штатный контроллер ChatGPT всё равно отправляет следующую изменяющую команду только после terminal result предыдущей.

## WORK — подтверждённые тесты

SAFE E2E: PASS.
- commit `f288fb14db39d592ba2f9ce94e31c1fbeb8f8259`
- run `34587014574`
- runner/computer/identity/service/git/filesystem проверены.
- `yc` на WORK отсутствует.

Guard destructive block: PASS.
- commit `c94f6c45b21c1a1e2037221050b214ebadade441`
- run `34587239400`
- `GUARD_RESULT=BLOCK`; target body не был исполнен.

WRITE sandbox: PASS.
- commit `a4487228f8d3d04b44de4b7e2621a7946a0f6d06`
- run `34587450331`
- создан `C:\ProgramData\ChatGPT-PK\bridge-v2-sandbox\smoke.txt`.
- subsequent SAFE verification run `34587523971` подтвердил содержимое.

Output redaction + checkout v7: PASS.
- commit `709c52dfd290ffaf6a554c056c77fb2f7a137b36`
- run `34587812381`
- fake access-token canary был выведен как `<REDACTED>`.
- checkout exact SHA через `actions/checkout@v7` подтверждён.

WRITE outside canonical root: BLOCK PASS.
- commit `4acb3b18a68437e959392cfe31b4bf04fd1b48f3`
- run `34588014896`
- попытка записи в `C:\Windows\Temp` заблокирована до исполнения.

Final WORK readiness: PASS.
- commit `35a93bc36c69c204adfe3795cba0654c175f5ac2`
- run `34588109067`
- runner online, service Running/Automatic, WRITE sandbox читается.

Runner recovery hardening: PASS.
- локально применено из elevated PowerShell по явному действию пользователя.
- verification commit `7f04684d95391b160dee8a4e01a0004c61938222`
- run `34590098087`
- reset period: `86400` sec
- restart delays: `5000 / 15000 / 60000` ms
- failure actions on non-crash failures: `TRUE`
- service: `Running`, StartType: `Automatic`

## Runner service WORK

Подтверждённое состояние:
- Status: `Running`
- StartType: `Automatic`
- reset period: `86400` sec
- restart delays: `5000 / 15000 / 60000` ms
- failureflag / non-crash failures: enabled

То есть runner переживает обычный reboot через Automatic startup и настроен на автоматический restart после аварийного завершения службы.

## Публичный репозиторий

Текущий repository PUBLIC. Поэтому текущий bridge использовать только для несекретных команд и несекретных тестовых данных.

Для production универсального PowerShell Bridge предпочтителен отдельный PRIVATE execution repository. Миграцию не выполнять без явного решения пользователя.

Важно: redaction защищает Actions logs, но не удаляет данные из Git history. Поэтому секретные или чувствительные payload нельзя коммитить даже в private bridge.

## Fail closed

- parse error -> BLOCK;
- unknown SAFE/WRITE command -> BLOCK;
- dynamic execution -> BLOCK;
- possible literal secret -> BLOCK;
- WRITE outside allowlisted root -> BLOCK;
- dangerous action -> BLOCK;
- uncertain previous WRITE -> audit before retry.

## Rollback

`tooling/powershell-bridge-v0.1` не изменять и не удалять до окончательного принятия v2.

## Remaining before production

1. Controlled reboot/recovery test WORK — только по явному решению пользователя.
2. Выбрать PRIVATE execution repository или иной production isolation.
3. Повторить E2E на HOME позже.
