# AGENTS — Yandex Cloud ↔ Google Drive Bridge

This directory is the source of truth for the shared bridge standard.

## Non-negotiable architecture

1. One source/protocol, separate deployment per client project.
2. Never share Apps Script URL, shared secret, Lockbox binding or fixed Drive root between independent projects.
3. `project_id` is defense-in-depth, not the primary security boundary.
4. Every ID-based Drive/Sheets operation must prove ancestry under the configured fixed root and fail closed.
5. Drive shortcuts are forbidden unless a future version explicitly implements double ancestry validation.
6. No global whole-request `ScriptLock`.
7. Resource locks, queues and durable jobs remain in the client project's Yandex orchestration.
8. Mutations require a stable `idempotency_key`; retries of the same logical mutation reuse it.
9. Never log secrets or Drive resumable session URIs.
10. Apps Script is control plane for large binary upload; bulk bytes must not be sent through Apps Script JSON.
11. Business/domain logic must not enter this shared bridge.

## Clients

- Marketplaces: see `clients/marketplaces.md` and `handoff/CHAT1_MARKETPLACES.md`.
- Birzha: see `clients/birzha.md` and `handoff/CHAT2_BIRZHA.md`.

## Change control

Any breaking protocol change requires a new `protocol_version` and updated acceptance tests for all active clients.

Do not mark a bridge release production-ready until `ACCEPTANCE.md` passes for every enabled capability and cross-project isolation/concurrency has been tested.
