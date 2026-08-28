# Architecture

## Role of this repository

`mcp-yandex-cloud-infra` is the infrastructure control plane for MCP services hosted in Yandex Cloud.

It does not contain marketplace or trading business logic. Those services remain in their own repositories.

## Target control path

```text
User
  ↓
ChatGPT
  ↓
GitHub repository changes
  ↓
GitHub Actions
  ↓
OIDC / Workload Identity Federation
  ↓
Yandex Cloud API
  ↓
TEST resources
  ↓
validation
  ↓
FINAL resources only after explicit promotion
```

## Security model

1. No long-lived Yandex Cloud credentials in Git.
2. Prefer GitHub OIDC / Workload Identity Federation.
3. Use a dedicated service account with least privilege.
4. Scope permissions to the TEST folder where possible.
5. No automatic `terraform apply` during bootstrap.
6. Production changes require a separate controlled promotion path.

## Initial Yandex Cloud resource model

Planned, not yet created by this repository:

```text
Cloud
└── mcp-test folder
    ├── Container Registry
    ├── Serverless Container(s)
    ├── runtime service account(s)
    ├── deploy service account
    └── Lockbox secrets (later)
```

## Repository boundaries

```text
marketplace-mcp-bridge     → application code
birzha-mcp-bridge          → application code (future)
birzha-bonds-mcp-bridge    → application code (future)
mcp-yandex-cloud-infra     → infrastructure definitions and deployment automation
```

## Bootstrap gate

The initial gate is passed when:

- Terraform files are syntactically valid;
- CI checks pass;
- no cloud resource is created;
- GitHub access to this private repository is verified.

Only after that do we configure GitHub ↔ Yandex Cloud federation.
