# mcp-yandex-cloud-infra

> **PC ACCESS NOTICE — 11.09.2026**  
> Для доступа ChatGPT к HOME/WORK Windows‑ПК этот репозиторий больше не является каноническим транспортом. Перед любой локальной задачей читать `CURRENT_PC_ACCESS.md`. Канонический путь: PRIVATE `alexpmtk-afk/gpt-powershell-bridge`, branch `bridge-v2`. `Remote_Desktop_Commander` не использовать как default по инерции.

Центральный приватный репозиторий для описания и автоматизации инфраструктуры MCP-сервисов в Yandex Cloud.

## Marketplace Archive Data Layer — обязательное правило

Архив маркетплейсов является multi-dataset системой. Ни один отдельный отчёт или годовой CSV не является полной базой Wildberries/Ozon.

Текущий `wb_weekly_finance_main` — только первый финансовый dataset. Он не является правильным источником для заказов покупателей, истории остатков, рекламы/продвижения или воронки продаж.

Перед любым историческим бизнес-запросом нужно сначала определить бизнес-метрику, затем выбрать канонический dataset через серверный Data Catalog, проверить покрытие периода и только после этого читать архив либо соответствующий официальный API.

Канонические источники правил:

- `app/core/system_map.py` — общая архитектура и обязательная маршрутизация;
- `app/core/data_catalog.py` — datasets, бизнес-метрики, покрытие и ограничения;
- `docs/MARKETPLACE_DATA_ARCHIVE.md` — полная спецификация Archive Data Layer.

Первый backfill: 2026 год. Целевая глубина после стабилизации: до 2024 года включительно, где это позволяет официальный API. Архив должен покрывать и Wildberries, и Ozon.

## Назначение

Репозиторий хранит инфраструктурный код и правила развёртывания. Код конкретных MCP-проектов хранится отдельно, например в `marketplace-mcp-bridge`.

Целевая схема:

```text
ChatGPT
   ↓
GitHub
   ↓
mcp-yandex-cloud-infra
   ↓
GitHub Actions
   ↓
Yandex Cloud API
   ↓
MCP infrastructure
```

## Принцип безопасности

На этапе bootstrap этот репозиторий **ничего не создаёт в Yandex Cloud автоматически**. Workflow выполняет только статические проверки Terraform. Подключение GitHub → Yandex Cloud и `terraform apply` будет добавлено отдельным изменением после настройки Workload Identity Federation и проверки прав.

Постоянные токены, OAuth-токены и service-account keys не должны храниться в репозитории.

### Обязательный bootstrap-gate

Пока `control/bootstrap.env` содержит `YC_OIDC_AUTH=PENDING`, любые облачные мутации должны оставаться `BLOCKED`.

Главное правило проекта:

```text
нет подтверждённой GitHub → Yandex Cloud авторизации
                 ↓
не создаём обычные ресурсы вручную в обход автоматизации
                 ↓
сначала завершаем OIDC / Workload Identity Federation
                 ↓
проверяем preflight
                 ↓
только затем разрешаем Terraform apply
```

Это правило автоматически проверяется workflow `Bootstrap Safety Gate`.

## Структура

```text
.github/workflows/        проверки инфраструктурного кода
docs/                     архитектура и правила
environments/test/        конфигурация TEST-окружения
terraform/                общий Terraform-каркас
control/bootstrap.env     машинно-читаемый статус bootstrap
```

## Текущий этап

`BOOTSTRAP_AUTH`: GitHub-репозиторий готов, Yandex Cloud OIDC-доверие ещё не подтверждено, облачные мутации заблокированы.
