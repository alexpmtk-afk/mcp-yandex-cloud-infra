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
- [ ] large download exact bytes/SHA256 without whole-file Base64 through Apps Script

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

Run Marketplaces and Birzha simultaneously:
- [ ] independent secrets
- [ ] independent fixed roots
- [ ] no cross-root visibility
- [ ] no shared ScriptLock serialization
- [ ] one project's retries/failure do not corrupt the other
