# Google Drive Bridge Protocol v1

Protocol version: `1`

## Envelope

All protected operations use `POST` JSON.

```json
{
  "secret": "<project secret>",
  "project_id": "<stable project id>",
  "request_id": "<caller-generated correlation id>",
  "idempotency_key": "<required for mutating actions>",
  "action": "<action>",
  "payload": {}
}
```

The deployment has compile-time/configured constants:

```text
PROJECT_ID
ARCHIVE_ROOT_ID
ARCHIVE_ROOT_NAME
BRIDGE_PROTOCOL_VERSION=1
```

The request is rejected unless `project_id == PROJECT_ID`.

## Response envelope

Success:

```json
{
  "ok": true,
  "protocol_version": 1,
  "project_id": "...",
  "request_id": "...",
  "action": "...",
  "result": {}
}
```

Failure:

```json
{
  "ok": false,
  "protocol_version": 1,
  "project_id": "...",
  "request_id": "...",
  "action": "...",
  "error": {
    "code": "...",
    "message": "...",
    "retryable": false
  }
}
```

Secrets and resumable session URIs MUST NOT appear in responses other than the explicit authenticated session-start result, and MUST NEVER be logged.

## Core actions

### `health`
Authenticated deep health. Returns configured project/root/protocol/capabilities.

### `stat`
Payload: `path`, `filename`.

### `metadata_by_id`
Payload: `file_id`. Must verify file ancestry under fixed root.

### `read_small`
Payload: `path`, `filename`. Intended only for bounded small objects. A deployment MUST enforce a maximum byte size and return `LARGE_READ_REQUIRED` above it.

### `write_small`
Mutating. Requires `idempotency_key`. Payload: `path`, `filename`, `mime_type`, `content_base64`, `sha256`.

### `trash_by_id`
Mutating. Requires `idempotency_key`; fixed-root ancestry required.

### `resumable_start`
Mutating. Requires `idempotency_key`. Creates a non-canonical staging file and Drive resumable session for a large binary upload. Session URI is a bearer-like capability and must not be logged.

### `promote_verified`
Mutating. Requires `idempotency_key`. Verifies expected bytes/SHA256 and atomically-at-bridge-level promotes a staged file to canonical name, then cleans up the previous canonical file.

### `large_download_start`
Returns a short-lived/capability-style authenticated download path or metadata required for the Yandex client to stream directly from Google without carrying whole-file Base64 through Apps Script. Exact implementation may evolve, but the contract must preserve fixed-root validation and no server refresh-token requirement.

## Google Sheets extension

### `sheet_ensure`
Finds or creates a spreadsheet inside fixed root according to project policy.

### `sheet_stage_begin`
Creates/initializes staged update state for a target spreadsheet.

### `sheet_write_chunk`
Mutating, idempotent. Writes one bounded range/chunk.

### `sheet_verify`
Returns parity metadata such as row count, digest, first/last date and caller-requested verification fields.

### `sheet_commit`
Mutating, idempotent. Commits a verified staged state.

### `sheet_abort`
Mutating, idempotent. Cleans staged state after failure.

## Idempotency

All mutating actions require an idempotency key. The same `(project_id, action, idempotency_key)` must be safe to replay. The bridge may use Script Properties/Cache for small bounded replay records, but durable workflow state remains the client project's responsibility.

## Locking

The bridge MUST NOT hold a global ScriptLock over the entire `doPost()` lifecycle.

Short ScriptLock sections are allowed only where Apps Script must protect its own tiny metadata/idempotency critical section. Arbitrary resource serialization belongs to the caller's Yandex-side orchestration.

## Security

- Every deployment is single-project.
- Separate project secret.
- Separate fixed root.
- Every `file_id` action performs fail-closed ancestry validation.
- Shortcuts must be rejected or resolved only with a second ancestry validation of the target.
- Path traversal (`.`, `..`, backslash) is rejected.
- Filename separators are rejected.
- Foreign-root negative tests are mandatory.
