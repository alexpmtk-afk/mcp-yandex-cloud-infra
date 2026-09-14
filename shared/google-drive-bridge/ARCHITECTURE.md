# Architecture — Yandex Cloud ↔ Google Drive Bridge v1

## Goal

Provide a reusable, isolated, versioned transport/security layer between Yandex Cloud workloads and Google Drive/Google Sheets without storing a long-lived Google OAuth refresh token in Yandex.

## Non-goals

The bridge is NOT:
- a business database;
- a scheduler;
- a marketplace/birzha registry;
- a queue service;
- a replacement for client project orchestration;
- a cross-project shared credential.

## Isolation model

Each client project receives an independent deployment:

```text
Marketplaces MCP
→ project-specific Yandex orchestration
→ Marketplaces Apps Script deployment
→ Marketplaces fixed Drive root

Birzha Forecast MCP
→ project-specific Yandex/YDB orchestration
→ Birzha Apps Script deployment
→ Birzha fixed Drive root
```

The two deployments share source code and protocol version only.

## Trust boundaries

1. Yandex runtime authenticates to its own Apps Script deployment with a high-entropy shared secret.
2. Apps Script executes as the Google Drive owner.
3. Compile-time/configured `PROJECT_ID` and `ARCHIVE_ROOT_ID` restrict the deployment.
4. Every path and file-id operation is checked against the fixed root.
5. Client project orchestration is responsible for resource-level serialization and durable workflow state.

## Concurrency

Global `ScriptLock` around request processing is forbidden.

Reason: it serializes unrelated calls in the same deployment and becomes a bottleneck. Short critical locks may protect tiny idempotency metadata sections only.

## Large binary data

Apps Script is control plane, not bulk-byte transport.

Upload:

```text
Yandex worker
→ bridge/resumable_start
→ Drive resumable session
→ Yandex uploads chunks directly
→ bridge/metadata + verification
→ Yandex backup (if project policy requires)
→ bridge/promote_verified
→ client project COMMIT
```

Download:

```text
Yandex worker
→ bridge validates file/root
→ direct/streaming Google download capability
→ Yandex consumes bytes directly
```

Whole large files must not be returned as Base64 in Apps Script JSON.

## Google Sheets

Google Sheets needs a separate extension because Drive resumable file upload does not provide safe range-level spreadsheet updates.

The Sheets extension provides:
- ensure/find spreadsheet in fixed root;
- bounded chunk/range writes;
- staged update lifecycle;
- read-back/parity verification;
- commit/abort semantics.

## Client responsibilities

Marketplaces keeps Redis/Valkey queues, archive job state, registry, WB/Ozon semantics, backup/candidate policy and calculations.

Birzha keeps YDB orchestration, Data Foundation, MOEX/ALGOPACK semantics, instrument mapping, parity rules, Forecast/Snapshot/Outcome logic.

## Versioning

Two values are exposed:
- `protocol_version` — wire compatibility;
- `bridge_release` — source implementation release.

Breaking wire changes require a new protocol version. Non-breaking fixes increment release only.
