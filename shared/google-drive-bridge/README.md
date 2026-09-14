# Yandex Cloud ↔ Google Drive Bridge v1

Shared infrastructure standard for isolated Yandex Cloud → Google Drive access used by multiple MCP projects.

## Design

One codebase, separate deployment per project.

Each project gets its own:
- `project_id`
- Google Apps Script deployment URL
- shared secret
- fixed Google Drive root
- Yandex Lockbox binding

Projects MUST NOT share a secret, deployment, or Drive root.

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
- no secret/session URI logging;
- mutating actions require idempotency keys;
- structured retryable errors;
- no global `ScriptLock` around the whole request;
- resource locking stays in the client project (Redis/Valkey for Marketplaces, YDB orchestration for Birzha);
- large binary writes use Drive resumable upload with Apps Script acting as control plane;
- large binary reads must avoid returning whole-file Base64 through Apps Script;
- Google Sheets updates use chunked/staged writes with verify/commit/rollback semantics.

## Client profiles

See:
- `clients/marketplaces.md`
- `clients/birzha.md`

## Deployment model

```text
shared bridge code
      ↓
project config
      ↓
project Apps Script deployment
      ↓
project secret + fixed root
      ↓
project Yandex runtime
```

Current implementation home: this directory in `mcp-yandex-cloud-infra`.

Future extraction to a dedicated repository is optional; protocol compatibility must be preserved.
