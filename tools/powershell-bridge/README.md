# GPT-PowerShell Bridge — Canonical Operating Contract v1.0

Дата: 31.08.2026
Статус документа: CANONICAL
Проект: `GPT-ПК`
Управляющий чат: `GPT-PowerShell`

Этот файл является постоянной канонической инструкцией для ChatGPT по работе с PowerShell Bridge. Новый чат проекта должен в первую очередь читать этот файл и текущее состояние GitHub, а не полагаться на старые сообщения передачи контекста.

## 1. Назначение

PowerShell Bridge позволяет пользователю управлять Windows-ПК через обычный диалог с ChatGPT без ручного копирования PowerShell-команд.

Нормальный канал:

`Пользователь → ChatGPT → GitHub → GitHub Actions → self-hosted Windows runner → PowerShell → GitHub Actions logs → ChatGPT`

Пользователь не является техническим посредником. После утверждения команды ChatGPT самостоятельно обновляет GitHub, отслеживает workflow, читает stdout/stderr и анализирует результат.

## 2. Источники истины

При конфликте данных использовать приоритет:

1. текущий код ветки `tooling/powershell-bridge-v0.1`;
2. фактические GitHub Actions logs;
3. фактический PowerShell output;
4. этот документ;
5. старые сообщения/передачи контекста.

## 3. GitHub

Repository:

`alexpmtk-afk/mcp-yandex-cloud-infra`

Branch:

`tooling/powershell-bridge-v0.1`

Workflow:

`.github/workflows/powershell-bridge.yml`

Исполняемый файл:

`tools/powershell-bridge/command.ps1`

Каноническая инструкция:

`tools/powershell-bridge/README.md`

Обычный execution commit prefix:

`bridge-exec:`

Допустимый bootstrap prefix:

`bridge-bootstrap:`

Изменения инфраструктуры без исполнения команды должны использовать иной prefix, например:

- `bridge-hardening:`
- `bridge-maintenance:`
- `bridge-docs:`

## 4. Постоянный Windows runner

Runner name:

`Codex-Bridge-Service-DESKTOP-7F6KPIL`

Labels:

- `self-hosted`
- `Windows`
- `X64`
- `codex-bridge-service`

Workflow должен оставаться привязан к:

`runs-on: [self-hosted, Windows, X64, codex-bridge-service]`

Machine:

`DESKTOP-7F6KPIL`

Runner version на момент v1.0:

`2.337.0`

## 5. Windows service

Фактическое имя службы:

`actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Service-DES-4731`

Ожидаемое состояние:

- `Status = Running`
- `StartType = Automatic`

Runner directory:

`C:\Users\Win10_Game_OS\actions-runner\codex-bridge-service`

Work directory:

`C:\Users\Win10_Game_OS\actions-runner\codex-bridge-service\_work`

Diagnostics:

`C:\Users\Win10_Game_OS\actions-runner\codex-bridge-service\_diag`

## 6. Security identity и пользовательский профиль

Runner работает под:

`NT AUTHORITY\NETWORK SERVICE`

Его `USERPROFILE`:

`C:\Windows\ServiceProfiles\NetworkService`

Следствия:

1. `$HOME`, `$env:USERPROFILE`, `HKCU`, `%APPDATA%`, `%LOCALAPPDATA%` относятся не к интерактивному пользователю `Win10_Game_OS`, а к `NETWORK SERVICE`.
2. Для пользовательских файлов использовать явные абсолютные пути, например `C:\Users\Win10_Game_OS\...`.
3. Не предполагать, что mapped drives, OneDrive paths, сетевые credentials, пользовательский PATH или пользовательские environment variables доступны службе.
4. Перед использованием CLI проверять `Get-Command <name> -ErrorAction SilentlyContinue` или применять подтверждённый абсолютный путь.
5. Не считать, что запуск GUI-приложения из service session покажет окно пользователю. Service Session 0 и интерактивный desktop — разные контексты.
6. Не менять пользовательский `HKCU` через bridge, считая его hive пользователя. Если действительно требуется реестр пользователя, сначала определить корректный SID/hive и отдельно согласовать точное изменение.

Подтверждённые CLI на момент v1.0:

- `C:\Program Files\GitHub CLI\gh.exe`
- `C:\Program Files\Git\cmd\git.exe`
- `C:\Program Files\nodejs\node.exe`

`yc` в PATH service-runner на последней проверке не найден.

## 7. Строгий approval gate

Для каждой новой исполняемой PowerShell-команды действует обязательный контракт:

`показать точную команду → получить явное "да" → выполнить`

До `да` запрещено:

- обновлять `command.ps1` новым исполняемым содержимым;
- запускать новую команду;
- заменять показанную команду другой;
- использовать старое согласие для новой команды;
- добавлять побочные потенциально опасные действия.

Даже read-only PowerShell-диагностика по умолчанию проходит тот же gate.

Чтение GitHub, workflow, commit history и Actions logs разрешено без отдельного approval, потому что оно не запускает новую команду на ПК.

## 8. Алгоритм выполнения после approval

После явного `да`:

1. Прочитать актуальный `tools/powershell-bridge/command.ps1` из branch и получить его blob SHA.
2. Записать в файл полный текст именно одобренной команды.
3. Commit message начать с `bridge-exec:`.
4. Получить commit SHA.
5. Найти workflow run ветки, у которого `head_sha` совпадает с этим commit SHA.
6. Получить job `execute`.
7. Дождаться terminal state `completed`.
8. Прочитать полный job log.
9. Проверить runner, computer, фактический `command.ps1`, output, PowerShell errors и итог исполнения.
10. Только после terminal result переходить к следующей команде.

Правило последовательности:

`one approved command → one commit → one workflow run → terminal result → next command`

Не отправлять новую команду, пока предыдущая не закончена.

## 9. Защита от race condition

Workflow обязан загружать `command.ps1` из triggering commit:

`?ref=$env:GITHUB_SHA`

Нельзя возвращаться к чтению команды по текущему имени branch. Это предотвращает ситуацию, когда run A получает более новую команду B.

## 10. Что проверять в job log

В корректном run должны быть подтверждены как минимум:

- `Runner name: 'Codex-Bridge-Service-DESKTOP-7F6KPIL'`
- `Machine name: 'DESKTOP-7F6KPIL'`
- `=== POWERSHELL_BRIDGE_BEGIN ===`
- правильный `Commit:`
- правильный `Runner:`
- правильный `Computer:`
- блок `--- command.ps1 ---` с одобренным пользователем кодом
- блок `--- output ---`
- отсутствие необработанных PowerShell exception/error records
- корректный итоговый exit code
- `=== POWERSHELL_BRIDGE_END ===`

ВАЖНО: GitHub `conclusion = success` сам по себе не доказывает успешность логической операции. Нужно читать полный log.

### Known issue v1.0

31.08.2026 выявлено, что нефатальная PowerShell-ошибка внутри `command.ps1` может быть напечатана в stderr, но workflow всё равно закончится `exit_code=0`, если скрипт продолжит выполнение. Поэтому до отдельного hardening workflow обязательна семантическая проверка логов на PowerShell errors/exceptions, а не только проверка `conclusion` и `exit_code`.

## 11. Проверка доступности bridge

Доступность проверяется в два уровня.

### 11.1 Passive health check — без запуска команды на ПК

ChatGPT самостоятельно:

1. читает текущий workflow;
2. читает последние workflow runs этой ветки;
3. проверяет последний фактический execution;
4. подтверждает runner name и machine name по log;
5. проверяет, нет ли незавершённого предыдущего bridge run.

Passive check подтверждает состояние GitHub control plane и последний известный successful contact с runner, но не гарантирует, что runner онлайн прямо сейчас.

### 11.2 Active health check — реальная проверка ПК

Если нужно доказать доступность bridge именно сейчас, используется обычный approval gate с минимальной read-only командой, например:

```powershell
Write-Host 'BRIDGE_HEALTH_OK'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
Get-Date
```

Эта команда также требует отдельного `да`.

Bridge считается активно доступным, если run принят правильным runner и лог содержит ожидаемый marker и terminal result.

## 12. Восстановление после сбоя

Всегда действовать fail-closed: не посылать следующую команду, пока состояние предыдущей не определено.

### Сценарий A — command завершился с PowerShell error

1. Прочитать полный log.
2. Выделить точный exception/error record.
3. Определить, были ли частично выполнены предыдущие строки команды.
4. Не повторять автоматически изменяющую команду.
5. Сформировать точную диагностическую или исправляющую команду.
6. Показать её пользователю и запросить новое `да`.

### Сценарий B — workflow failed/cancelled

1. Проверить run/job/steps/logs.
2. Определить, началось ли фактическое выполнение `command.ps1`.
3. Если факт выполнения неизвестен, считать состояние операции неопределённым и сначала диагностировать.
4. Не использовать blind retry для потенциально неидемпотентных операций.

### Сценарий C — run долго остаётся queued

1. Не создавать новый `bridge-exec` commit.
2. Проверить, нет ли уже running/queued bridge run.
3. Проверить последний подтверждённый runner contact.
4. Считать вероятной недоступность self-hosted runner, если job не получает runner.
5. Не утверждать, что команда не выполнилась, пока не проверено состояние run.

Если единственный self-hosted runner действительно offline, сам bridge не может восстановить свою Windows service через GitHub, потому что для выполнения команды нужен этот же runner. Это фундаментальная граница текущей архитектуры. В таком случае сначала искать альтернативный уже существующий канал/runner; ручное вмешательство пользователя допускается только как последний технически неизбежный вариант.

### Сценарий D — runner онлайн, но service/permissions ограничивают операцию

Получить фактическую ошибку и перейти к правилам административных операций ниже. Не эскалировать привилегии автоматически.

## 13. Административные операции

Текущий bridge — постоянный канал, но не полноценный административный broker.

Подтверждённое ограничение: `NETWORK SERVICE` может получить `Access is denied` при управлении процессами интерактивного пользователя или другими защищёнными объектами.

Правила:

1. Сначала пытаться решить задачу через текущий bridge, если операция разумно может быть доступна service account.
2. При `Access is denied` прочитать точную ошибку и определить, действительно ли нужен elevation.
3. Искать неадминистративный эквивалент или корректный сервисный API до вовлечения пользователя.
4. Не переводить runner на `LocalSystem` и не выдавать широкие ACL только ради обхода конкретной ошибки без отдельного архитектурного решения.
5. Не хранить пароль администратора, PAT, токены или иные секреты в `command.ps1`.
6. Будущий privileged/admin broker должен быть отдельным компонентом с минимальными правами, allowlist/contract действий, аудитом и отдельным approval gate.

## 14. Секреты

`command.ps1` хранится в Git history. stdout/stderr сохраняются в Actions logs.

Запрещено помещать или печатать открытым текстом:

- passwords;
- API keys;
- OAuth tokens;
- GitHub PAT;
- Yandex Cloud secrets;
- marketplace API tokens;
- private keys;
- recovery codes.

Для проверки наличия секрета использовать только булевы/метаданные, например:

```powershell
Write-Host ("SECRET_TOKEN_PRESENT=" + [bool]$env:SECRET_TOKEN)
```

Не выводить содержимое credentials-файлов.

## 15. Поведение с пользователем

Нельзя заставлять пользователя быть техническим посредником, если bridge способен выполнить задачу.

Нормальный интерфейс:

```text
Для этого нужна команда:

<точная PowerShell-команда>

Она сделает X и не затронет Y.

Запустить? Да / нет.
```

После `да` ChatGPT выполняет весь GitHub/Actions/log workflow самостоятельно.

Фраза пользователя `сделай сам` означает использовать доступные инструменты самостоятельно, но не отменяет approval gate для новой PowerShell-команды.

## 16. Синхронизация нового чата GPT-PowerShell

При первом подключении нового управляющего чата не просить технические данные у пользователя.

Выполнить read-only sync:

1. открыть этот `README.md`;
2. открыть `.github/workflows/powershell-bridge.yml`;
3. открыть `tools/powershell-bridge/command.ps1`;
4. прочитать последние Actions runs ветки;
5. открыть job/log последнего фактического execution;
6. подтвердить runner `Codex-Bridge-Service-DESKTOP-7F6KPIL` и machine `DESKTOP-7F6KPIL`;
7. проверить текущую архитектуру и known issues;
8. ничего не запускать на ПК во время синхронизации.

После успешной синхронизации сообщить кратко:

`GPT-PowerShell синхронизирован. Постоянный bridge найден и готов к работе.`

## 17. Подтверждённый E2E baseline

Ранее подтверждён полный канал:

`ChatGPT → GitHub commit → GitHub Actions → Windows service runner → PowerShell → stdout → GitHub → ChatGPT`

Baseline machine:

`DESKTOP-7F6KPIL`

Baseline runner:

`Codex-Bridge-Service-DESKTOP-7F6KPIL`

Windows PowerShell baseline:

`5.1.19041.6456`

## 18. Устаревший runner

Старый временный runner:

`Codex-Bridge-DESKTOP-7F6KPIL`

не является рабочим bridge и не должен восстанавливаться или использоваться как основной.

Основной runner только:

`Codex-Bridge-Service-DESKTOP-7F6KPIL`

## 19. Будущее развитие

Допустимые направления развития проекта `GPT-ПК`:

- filesystem broker;
- user-session broker для интерактивных приложений;
- privileged/admin broker;
- локальные скрипты;
- Git/Codex integration;
- browser automation;
- cloud CLI;
- Windows diagnostics;
- workflow automation.

Каждый новый канал должен иметь отдельные security boundaries, минимальные права, аудит и понятный approval contract.

## 20. Короткая формула

`Пользователь формулирует задачу → GPT-PowerShell показывает точную команду → пользователь говорит "да" → GPT-PowerShell обновляет command.ps1 → bridge-exec commit → GitHub Actions → Codex-Bridge-Service-DESKTOP-7F6KPIL → PowerShell → GPT-PowerShell читает полный log → сообщает результат.`

Пользователь не копирует команды между ChatGPT и PowerShell.
