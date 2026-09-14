# Yandex Cloud ↔ Google Drive Bridge v1 — FINAL STRUCTURE

Stable release: `protocol_version=1`, `bridge_release=1.0.0`.

## Canonical sources of truth

Only these `main` branches are canonical:

1. Shared transport/security/protocol:
   `alexpmtk-afk/mcp-yandex-cloud-infra/main/shared/google-drive-bridge/`
2. Marketplaces client/business integration:
   `alexpmtk-afk/marketplaces-mcp-ru/main`
3. Birzha client/business integration:
   `alexpmtk-afk/birzha-mcp-forecast/main`

Feature branches, old pinned worker SHAs and the former Birzha `birzha_*` Marketplaces Apps Script addon are not release sources.

## Final architecture

```text
                         COMMON CODE / PROTOCOL v1.0.0
                mcp-yandex-cloud-infra/shared/google-drive-bridge
                                   │
                 ┌─────────────────┴─────────────────┐
                 │                                   │
          MARKETPLACES                            BIRZHA
   marketplaces-mcp-ru/main              birzha-mcp-forecast/main
                 │                                   │
      project_id=marketplaces                 project_id=birzha
                 │                                   │
  own Apps Script deployment               own Apps Script deployment
                 │                                   │
 own gdrive_bridge_v1_secret              own gdrive_bridge_v1_secret
 in Marketplaces project Lockbox          in Birzha project Lockbox
                 │                                   │
 fixed Marketplaces Drive root            fixed Birzha Drive root
                 │                                   │
       Drive archive files                  Drive + Google Sheets mirror
```

There is no shared deployment, no shared project secret, no cross-project root, no global Bridge queue and no global whole-request ScriptLock.

## Ownership boundaries

### Shared Bridge
Owns protocol, authentication envelope, fixed-root sandbox, Drive/Sheets primitives, idempotency contract, resumable upload, verified large download, staged Sheets transaction and common acceptance.

### Marketplaces
Owns WB/Ozon business logic, archive layout, registry, PREPARE→UPLOAD→BACKUP→COMMIT, Redis/Valkey jobs/locks/rate limiting and Object Storage backup.

### Birzha
Owns MOEX/ALGOPACK, YDB Data Foundation and orchestration, contract selection, Forecast/Snapshot/Outcome, D1 mirror semantics and YDB↔Sheets parity rules.

## Required runtime activation order

No step may be skipped.

1. Google owner authorizes the Apps Script/Drive scopes required by the deployment bootstrap.
2. Bootstrap creates two separate Apps Script Web Apps from the exact shared Bridge `1.0.0` source.
3. Bootstrap generates two unrelated high-entropy secrets and stores each only in its own existing project Lockbox under `gdrive_bridge_v1_secret`.
4. Run Marketplaces live acceptance: health, wrong-project rejection, foreign-root rejection, small I/O, idempotent replay, resumable large upload, verified large download and concurrency.
5. Run Birzha live acceptance: health, wrong-project/foreign-root rejection, Sheets stage replay, chunk write, verify, commit, inspect and abort.
6. Run cross-project concurrent acceptance and prove both roots reject the other project's file IDs.
7. Publish immutable client images from each project's canonical `main` only.
8. Cut over Marketplaces to Protocol v1 and run post-cutover archive read/write verification.
9. Cut over Birzha to Protocol v1 with `BIRZHA_MARKET_MIRROR_REQUIRED=true` and run one controlled D1 YDB↔Sheets parity cycle.
10. Keep legacy credentials/routes only for the rollback window. After stable post-cutover evidence, delete retired legacy deployment/configuration paths.

## Rollback order

Rollback is explicit; there is no automatic silent fallback.

1. Disable the new project revision / restore the immediately previous known-good revision.
2. Restore the previous project's deployment variables/secret binding only for that project.
3. Do not alter the other project's deployment or secret.
4. Verify the restored business path.
5. Preserve failed v1 evidence for diagnosis; never expose secrets, resumable URIs or download URIs.

## Completion rule

Code is incomplete if any release path contains `NOT_IMPLEMENTED`, TODO/FIXME placeholders, an alpha release dependency, a shared Marketplaces/Birzha credential, a pinned retired worker source, or an automatic legacy fallback.

The only non-code gate permitted after repository completion is interactive Google owner authorization and the resulting live acceptance/cutover evidence.
