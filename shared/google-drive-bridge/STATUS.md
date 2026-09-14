# Implementation status

Source of truth: `main`, directory `shared/google-drive-bridge/`.

Release: `protocol_version=1`, `bridge_release=1.0.0`.

## Implementation state

**CODE COMPLETE. No protocol action is a stub or `NOT_IMPLEMENTED`.**

Implemented and covered by static/contract CI:
- project-isolated Apps Script deployments;
- separate project secrets and fixed Drive roots;
- `project_id`, `request_id`, and idempotent mutation contract;
- bounded small-file read/write;
- resumable large upload with direct Yandex → Drive byte transport;
- staged verify/promote with exact size/SHA256 checks;
- large verified download through Drive `files.download` LRO with direct Google → Yandex byte transport;
- fixed-root ancestry validation and shortcut rejection;
- Google Sheets ensure/stage/chunk/verify/commit/inspect/abort;
- non-destructive replay of `sheet_stage_begin`;
- independent post-commit canonical-sheet read-back via `sheet_inspect`;
- rollback attempt on Sheets commit failure;
- no whole-request global ScriptLock;
- reusable Python Protocol-v1 client;
- Marketplaces and Birzha bootstrap/acceptance/cutover gates;
- cross-project concurrency and root-isolation acceptance.

## Runtime activation order

1. Owner authorizes Google Apps Script API / Drive scopes once.
2. Bootstrap creates two separate Apps Script Web Apps from the same `1.0.0` source.
3. Each project receives its own secret in its own existing project Lockbox under `gdrive_bridge_v1_secret`.
4. Marketplaces live acceptance runs: health, root isolation, small I/O, resumable upload, large direct download, SHA256, concurrency.
5. Birzha live acceptance runs: health, root isolation, staged/chunked Sheets, verify/commit/abort/replay.
6. Cross-project acceptance proves concurrent isolation.
7. Client cutover is enabled project-by-project with legacy rollback retained until post-cutover verification passes.
8. After post-cutover PASS, legacy routes may be retired.

The only item that cannot be performed by repository automation alone is the interactive Google owner consent. That is an external authorization gate, not unfinished code.
