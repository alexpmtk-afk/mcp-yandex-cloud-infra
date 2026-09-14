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

The deployment has configured Script Properties for project identity, fixed Drive root and secret. The request is rejected unless its `project_id` matches the deployment.

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

Secrets, resumable session URIs and large-download URIs MUST NEVER be logged or returned in user-facing MCP responses. Resumable/download capabilities may appear only in the authenticated control-plane call that needs them.

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
Mutating. Requires `idempotency_key`. Creates a non-canonical staging file and Drive resumable session for a large binary upload. Session URI is bearer-like and must not be logged.

### `promote_verified`
Mutating. Requires `idempotency_key`. Verifies expected bytes/SHA256 and promotes a staged file to canonical name, then cleans up the previous canonical file.

## Large binary download

Large reads use Google Drive `files.download` as a control-plane broker. Apps Script performs owner authentication and fixed-root validation but does **not** carry the file bytes.

### `large_download_start`
Payload: `file_id`.

Rules:
- `file_id` must pass fixed-root ancestry validation;
- shortcuts are rejected by the normal root guard;
- v1 direct download supports Drive blob files with exact Drive `size` and `sha256Checksum`;
- Google Workspace-native documents use the Sheets/document-specific path and are not treated as archive blobs;
- the bridge starts a Drive `files.download` long-running operation;
- if ready immediately, result contains a short-lived `download_uri` plus exact size/SHA256;
- if pending, result contains an opaque `download_ticket` bound server-side to the validated file/operation.

### `large_download_poll`
Payload: `download_ticket`.

Apps Script polls the Drive long-running operation using the owner's OAuth context. Before returning a ready URI it revalidates that the source file remains inside the project root and that size/SHA256/modified time have not changed.

When ready, the authenticated result contains:
- `download_uri`;
- `file_id`;
- `total_bytes`;
- `sha256`;
- MIME/modified metadata;
- optional Drive resource key;
- `partial_download_allowed`.

The Yandex client downloads bytes **directly from the Google download URI**, never through Apps Script/Base64, and MUST verify exact byte count and SHA256 before using the content. The download URI is bearer-like and MUST NOT be logged, persisted as ordinary business data, or returned to users.

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

All mutating actions require an idempotency key. The same `(project_id, action, idempotency_key)` must be safe to replay. Durable workflow state remains the client project's responsibility.

## Locking

The bridge MUST NOT hold a global ScriptLock over the entire `doPost()` lifecycle. Arbitrary resource serialization belongs to the caller's Yandex-side orchestration.

## Security

- Every deployment is single-project.
- Separate project secret.
- Separate fixed root.
- Every `file_id` action performs fail-closed ancestry validation.
- Shortcuts are rejected unless a future protocol explicitly revalidates their target.
- Path traversal (`.`, `..`, backslash) is rejected.
- Filename separators are rejected.
- Large download tickets are server-side bindings; arbitrary Drive operation names are not accepted from clients.
- Large download URIs are accepted by the Python client only from HTTPS Google endpoints and are never logged.
- Foreign-root negative tests are mandatory.
