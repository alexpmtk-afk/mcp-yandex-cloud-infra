# mcp-yandex-cloud-infra

Центральный приватный репозиторий для описания и автоматизации инфраструктуры MCP-сервисов в Yandex Cloud.

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

## Структура

```text
.github/workflows/        проверки инфраструктурного кода
docs/                     архитектура и правила
environments/test/        конфигурация TEST-окружения
terraform/                общий Terraform-каркас
```

## Текущий этап

`BOOTSTRAP`: создан безопасный каркас без облачных мутаций.
