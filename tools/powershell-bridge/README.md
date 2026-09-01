# GPT-PowerShell Bridge — Canonical Operating Contract v1.1

Дата: 01.09.2026
Статус: CANONICAL
Проект: `GPT-ПК`
Управляющий чат: `GPT-PowerShell`

Этот файл — постоянная инструкция для ChatGPT. При конфликте данных приоритет: текущий код ветки → фактические GitHub Actions logs → фактический PowerShell output → этот документ → старые сообщения.

## 1. Назначение

PowerShell Bridge позволяет управлять Windows-ПК через обычный диалог с ChatGPT без ручного копирования команд после первичной установки runner.

Канал:

`Пользователь → ChatGPT → GitHub → GitHub Actions → self-hosted Windows runner → PowerShell → Actions logs → ChatGPT`

## 2. GitHub

Repository: `alexpmtk-afk/mcp-yandex-cloud-infra`

Branch: `tooling/powershell-bridge-v0.1`

Workflow: `.github/workflows/powershell-bridge.yml`

Исполняемый файл: `tools/powershell-bridge/command.ps1`

Каноническая инструкция: `tools/powershell-bridge/README.md`

## 3. Два компьютера и маршрутизация

### Домашний компьютер

Machine: `DESKTOP-7F6KPIL`

Runner: `Codex-Bridge-Service-DESKTOP-7F6KPIL`

Labels: `self-hosted`, `Windows`, `X64`, `codex-bridge-service`

Execution prefix: `bridge-exec-home:`

Для обратной совместимости старый prefix `bridge-exec:` также направляется на домашний компьютер.

### Рабочий компьютер

Machine: `MANAGER-MP2`

Runner: `Codex-Bridge-Work-MANAGER-MP2`

Labels: `self-hosted`, `Windows`, `X64`, `codex-bridge-work`

Runner version при установке: `2.337.0`

Runner directory: `C:\ProgramData\ChatGPT-PK\powershell-work-runner`

Service: `actions.runner.alexpmtk-afk-mcp-yandex-cloud-infra.Codex-Bridge-Work-MANAGER-MP2`

Ожидаемое состояние: `Running`, `Automatic`.

Execution prefix: `bridge-exec-work:`

### Выбор компьютера

Перед execution ChatGPT обязан определить целевой ПК из явного запроса или текущего контекста. Если целевой ПК действительно неоднозначен, нужно уточнить его до запуска.

Нельзя отправлять одну команду сразу на оба ПК без отдельного явного согласования.

## 4. Префиксы commit

- `bridge-exec-home:` — выполнить одобренную команду на домашнем ПК.
- `bridge-exec-work:` — выполнить одобренную команду на рабочем ПК.
- `bridge-exec:` — legacy, выполнить на домашнем ПК.
- `bridge-bootstrap:` — bootstrap домашнего контура, только когда это действительно требуется.
- `bridge-maintenance:` / `bridge-hardening:` / `bridge-docs:` — изменения инфраструктуры без исполнения PowerShell-команды.

## 5. Строгий approval gate

Для каждой новой PowerShell-команды действует обязательная схема:

`показать точную команду → получить явное "да" → выполнить именно её`

До `да` запрещено:

- записывать новую исполняемую команду в `command.ps1`;
- запускать её;
- подменять показанный текст другой командой;
- переносить старое согласие на новую команду;
- добавлять скрытые побочные действия.

Даже read-only диагностика по умолчанию требует отдельного `да`.

Чтение GitHub, commit history, workflow и Actions logs не запускает команду на ПК и отдельного approval не требует.

## 6. Алгоритм после approval

1. Прочитать текущий `command.ps1` и получить blob SHA.
2. Записать полный текст именно одобренной команды.
3. Использовать prefix целевого ПК: `bridge-exec-home:` или `bridge-exec-work:`.
4. Получить commit SHA.
5. Найти workflow run с тем же `head_sha`.
6. Получить job `execute`.
7. Дождаться `completed`.
8. Прочитать полный job log.
9. Проверить runner, computer, фактический текст `command.ps1`, stdout/stderr и exit code.
10. Только после terminal result переходить к следующей команде.

Правило: `one approved command → one commit → one run → terminal result → next command`.

## 7. Защита от race condition

Workflow обязан загружать `command.ps1` из triggering commit через `?ref=$env:GITHUB_SHA`, а не из текущего HEAD ветки.

Workflow использует общий concurrency group `powershell-bridge` с `cancel-in-progress: true`.

Нельзя создавать следующую исполняемую команду до определения terminal state предыдущей.

## 8. Что проверять в log

Корректный run должен содержать:

- ожидаемый Runner name целевого ПК;
- ожидаемый Machine name;
- `=== POWERSHELL_BRIDGE_BEGIN ===`;
- правильный `Commit:`;
- правильный `Runner:`;
- правильный `Computer:`;
- блок `--- command.ps1 ---` с одобренным текстом;
- блок `--- output ---`;
- отсутствие необработанных PowerShell exceptions/errors;
- корректный `exit_code`;
- `=== POWERSHELL_BRIDGE_END ===`.

`conclusion=success` само по себе недостаточно: лог нужно читать семантически.

Known issue: нефатальная PowerShell-ошибка иногда может быть напечатана, а общий exit code остаться 0. Поэтому stdout/stderr проверяются всегда.

## 9. Active health check

Минимальная проверка доступности конкретного ПК также проходит approval gate, например:

```powershell
Write-Host 'BRIDGE_HEALTH_OK'
Write-Host "Runner=$env:RUNNER_NAME"
Write-Host "Computer=$env:COMPUTERNAME"
Get-Date
```

Bridge считается активно доступным, только если run принят нужным runner и завершён с ожидаемым log.

## 10. Security identity

Оба service-runner по умолчанию работают в сервисном контексте Windows (`NT AUTHORITY\NETWORK SERVICE`).

Следствия:

- `$HOME`, `$env:USERPROFILE`, `HKCU`, `%APPDATA%` относятся к service account, а не к интерактивному пользователю;
- mapped drives и пользовательский PATH могут отсутствовать;
- для пользовательских файлов нужны явные абсолютные пути;
- перед вызовом CLI сначала проверять `Get-Command` или использовать подтверждённый абсолютный путь;
- GUI из Session 0 не считается интерактивным окном пользователя;
- не менять пользовательский HKCU, не определив корректный SID/hive.

## 11. Секреты

`command.ps1` хранится в Git history, stdout/stderr — в Actions logs.

Запрещено помещать или печатать открытым текстом passwords, API keys, OAuth tokens, PAT, Yandex Cloud secrets, marketplace tokens, private keys и recovery codes.

Проверять только факт наличия, например:

```powershell
Write-Host ("SECRET_PRESENT=" + [bool]$env:SECRET_TOKEN)
```

## 12. Сбои

Действовать fail-closed.

Если PowerShell дал ошибку — определить, какие строки могли уже выполниться, и не повторять изменяющую команду автоматически.

Если workflow failed/cancelled — сначала определить, началось ли выполнение `command.ps1`.

Если run долго `queued` — не отправлять новую исполняемую команду; проверить целевой label/runner и последний контакт.

Если нужный self-hosted runner offline, сам этот runner не может восстановить собственную Windows service через GitHub. Сначала искать другой уже существующий канал; ручное вмешательство пользователя — последний технически неизбежный вариант.

## 13. Административные операции

Текущий bridge не является универсальным административным broker.

При `Access is denied` сначала искать безопасный неадминистративный способ. Не переводить runner на LocalSystem и не расширять ACL без отдельного архитектурного решения и approval.

## 14. Поведение с пользователем

Если bridge способен выполнить задачу, пользователь не должен быть техническим посредником.

Нормальный интерфейс:

```text
Для этого нужна команда:

<точная PowerShell-команда>

Она сделает X и не затронет Y.

Запустить? Да / нет.
```

После `да` ChatGPT самостоятельно делает commit, отслеживает Actions, читает полный log и сообщает результат.

## 15. Baseline

Домашний E2E baseline ранее подтверждён для `DESKTOP-7F6KPIL` / `Codex-Bridge-Service-DESKTOP-7F6KPIL`.

Рабочий runner зарегистрирован 01.09.2026: `MANAGER-MP2` / `Codex-Bridge-Work-MANAGER-MP2`; служба установлена и запущена. Полный E2E для рабочего ПК считается подтверждённым только после отдельного active health check через `bridge-exec-work:`.

## 16. Короткая формула

`Пользователь формулирует задачу → ChatGPT выбирает целевой ПК → показывает точную команду → пользователь говорит "да" → command.ps1 → target-specific bridge-exec commit → GitHub Actions → нужный Windows runner → PowerShell → полный log → ChatGPT сообщает результат.`
