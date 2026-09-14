# Implementation status

Current source of truth: `main`, directory `shared/google-drive-bridge/`.

Release status: `protocol_version=1`, `bridge_release=1.0.0-alpha.1`.

Implemented and merged:
- shared architecture and protocol v1;
- per-project isolation model;
- shared Apps Script runtime source;
- setup helpers and per-project deployment configs for Marketplaces and Birzha;
- reusable async Python client adapter;
- Drive small-file operations;
- Drive resumable large-upload control plane + direct Yandex chunk uploader;
- staged verified promotion with exact size/SHA256 checks;
- Google Sheets staged/chunked write extension with verify/commit/abort;
- fixed-root file-id validation and shortcut rejection;
- `project_id`, `request_id`, `idempotency_key` contract;
- no global whole-request ScriptLock;
- Marketplaces and Birzha client profiles/handoff rules;
- executable common and Sheets acceptance runners;
- CI syntax/contract checks;
- migration and cutover documentation.

CI status at merge: PASS for Google Drive Bridge v1 CI and Bootstrap Safety Gate.

Still required before PRODUCTION READY:
- create two real, separate Apps Script deployments from the shared source (Marketplaces and Birzha);
- bootstrap two separate bridge secrets into project-specific Yandex Lockbox bindings;
- live authenticated health/security acceptance on both deployments;
- live Drive small-file and ~16 MiB resumable upload tests;
- implement/accept the large-file read/download transport (alpha.1 currently reports this capability as unavailable);
- harden/accept Google Sheets staged write behavior against live Sheets;
- migrate Marketplaces client code to protocol v1;
- migrate Birzha M25 from the shared Marketplaces credential/deployment to its own Bridge v1 deployment;
- run simultaneous Marketplaces + Birzha concurrency/isolation acceptance;
- complete post-cutover validation before removing legacy shared paths.

No production client has been cut over yet. This is deliberate: the merged alpha establishes the common implementation and source of truth without changing current production bindings.
