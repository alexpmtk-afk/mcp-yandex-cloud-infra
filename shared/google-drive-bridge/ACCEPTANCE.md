# Acceptance matrix — Bridge v1

A bridge release is not production-ready until the client deployment passes the applicable rows.

## Common security/transport

- [ ] authenticated deep health returns expected `project_id`, root and protocol version
- [ ] wrong shared secret rejected
- [ ] wrong `project_id` rejected
- [ ] invalid/traversal path rejected
- [ ] foreign-root `file_id` rejected
- [ ] shortcut escape rejected or safely revalidated
- [ ] secret never appears in response/logs
- [ ] resumable session URI never appears in logs/user-facing MCP responses
- [ ] large-download URI never appears in logs/user-facing MCP responses
- [ ] `request_id` echoed for correlation
- [ ] mutating action without `idempotency_key` rejected
- [ ] exact idempotency replay is safe
- [ ] structured error includes stable code + retryable flag
- [ ] independent resources can execute concurrently
- [ ] no whole-request global ScriptLock

## Drive file transport

- [ ] small write/read exact bytes and SHA256
- [ ] small read above configured threshold returns `LARGE_READ_REQUIRED`
- [ ] resumable large upload exact bytes and Drive SHA256
- [ ] interrupted chunk upload resumes from Drive-confirmed offset
- [ ] expired resumable session restarts safely from immutable candidate
- [ ] existing canonical remains untouched until verification
- [ ] verified promotion is replay-safe
- [ ] previous canonical cleanup is confirmed
- [ ] `large_download_start` validates fixed root and returns exact Drive size/SHA256
- [ ] pending large download can be polled only by its opaque bridge ticket
- [ ] source mutation between start/poll fails closed
- [ ] final file bytes travel Google download URI → Yandex client, not Apps Script/Base64
- [ ] direct large download exact byte count matches Drive metadata
- [ ] direct large download SHA256 matches Drive `sha256Checksum`
- [ ] non-Google/HTTP download URI is rejected client-side

The common runner checks large upload + direct large download when:

```text
GDRIVE_BRIDGE_RUN_LARGE=1
GDRIVE_BRIDGE_LARGE_BYTES=16777216
```

The recommended Marketplaces acceptance size is the real annual-file class (~16 MiB or larger).

## Google Sheets extension

- [ ] approved spreadsheet found/created under root
- [ ] pre-bound spreadsheet is not duplicated
- [ ] bounded chunk write works
- [ ] repeated same chunk/idempotency key is safe
- [ ] stage can be aborted after partial failure
- [ ] verify returns row count and requested parity fields
- [ ] normalized digest matches expected content
- [ ] commit only succeeds after verify
- [ ] failed stage never silently becomes canonical

## Cross-project test

Run two live deployments simultaneously (initially Marketplaces and Birzha) with `scripts/cross_project_acceptance.py`.

Required environment groups:

```text
BRIDGE_A_URL
BRIDGE_A_SECRET
BRIDGE_A_PROJECT_ID
BRIDGE_A_ROOT_ID

BRIDGE_B_URL
BRIDGE_B_SECRET
BRIDGE_B_PROJECT_ID
BRIDGE_B_ROOT_ID
```

Acceptance:
- [ ] project IDs differ
- [ ] fixed roots differ
- [ ] both authenticated health checks pass concurrently
- [ ] independent writes/read-backs pass concurrently
- [ ] project A rejects project B file id with `OUTSIDE_ROOT`
- [ ] project B rejects project A file id with `OUTSIDE_ROOT`
- [ ] no shared ScriptLock serialization dependency exists
- [ ] one project's retry/failure does not corrupt the other

## Production cutover gate

Do not change a client's production system map or remove its legacy route until all applicable live rows are PASS. Client-side code readiness alone is not a production acceptance.
