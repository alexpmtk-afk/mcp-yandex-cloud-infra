# Yandex Cloud ↔ Google Drive Bridge v1

Shared infrastructure standard for isolated Yandex Cloud → Google Drive access used by multiple MCP projects.

## Design

One codebase, separate deployment per independent project boundary.

Each independent project gets its own:
- `project_id`
- Google Apps Script deployment URL
- shared secret
- fixed Google Drive root
- Yandex Lockbox binding

Projects MUST NOT share a secret, deployment, or Drive root across independent security/business boundaries.

A module inside an existing MCP is **not** a separate Bridge client merely because it has its own chat, business domain, or archive dataset. Subsystems inherit the Bridge identity of their parent MCP unless there is a deliberate architectural decision to split them into an independent runtime/security boundary.

Current boundaries:
- `project_id=marketplaces` — Marketplaces MCP, including the WB Advertising / `MCP Реклама` subsystem and future Advertising Archive datasets implemented through the shared Marketplaces archive layer;
- `project_id=birzha` — Birzha / Forecast MCP.

Therefore `MCP Реклама` MUST NOT create its own Apps Script deployment, secret, Drive root, Lockbox, or `project_id` while it remains a module of Marketplaces MCP. It must use the Marketplaces archive abstraction rather than call Apps Script directly from advertising business code.

The bridge is transport/security infrastructure only. Business logic, queues, orchestration, registries and domain-specific state remain inside each client project.

## Core protocol

Protected POST body:

```json
{
  "secret": "<project secret>",
  "project_id": "marketplaces|birzha|...",
  "request_id": "<correlation id>",
  "idempotency_key": "<required for mutating actions>",
  "action": "health",
  "payload": {}
}
```

Required invariants:
- fail-closed `project_id` validation;
- fail-closed fixed-root validation for path and `file_id` operations;
- no secret/session/download capability URI logging;
- mutating actions require idempotency keys;
- structured retryable errors;
- no global `ScriptLock` around the whole request;
- resource locking stays in the client project (Redis/Valkey for Marketplaces, YDB orchestration for Birzha);
- large binary writes use Drive resumable upload with Apps Script acting as control plane;
- large binary reads use the Bridge download broker/direct Google download path and must verify exact size + SHA256 without returning whole-file Base64 through Apps Script;
- Google Sheets updates use chunked/staged writes with verify/commit/rollback semantics.

## Client profiles

See:
- `clients/marketplaces.md`
- `clients/birzha.md`

## Deployment model

```text
shared bridge code
      ↓
independent project config
      ↓
project Apps Script deployment
      ↓
project secret + fixed root
      ↓
project Yandex runtime
      ↓
project subsystems reuse the parent archive/client layer
```

Current implementation home: this directory in `mcp-yandex-cloud-infra`.

Future extraction to a dedicated repository is optional; protocol compatibility and project-boundary rules must be preserved.
