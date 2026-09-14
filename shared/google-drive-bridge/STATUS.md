# Implementation status

Current source of truth after merge: `main`, directory `shared/google-drive-bridge/`.

Candidate release: `protocol_version=1`, `bridge_release=1.0.0-alpha.2`.

Implemented in code:
- shared architecture and protocol v1;
- per-project isolation model;
- shared Apps Script runtime source;
- setup helpers and per-project deployment configs for Marketplaces and Birzha;
- reusable async Python client adapter;
- Drive small-file operations;
- Drive resumable large-upload control plane + direct Yandex chunk uploader;
- staged verified promotion with exact size/SHA256 checks;
- direct large-file read broker via Drive `files.download` long-running operations;
- opaque bridge download tickets for pending Drive download operations;
- direct Google download URI → Yandex client byte transport (Apps Script remains control plane);
- exact large-download byte count + SHA256 verification in the Python client;
- Google download URI hostname allowlist and no URI logging;
- Google Sheets staged/chunked write extension with verify/commit/abort;
- fixed-root file-id validation and shortcut rejection;
- `project_id`, `request_id`, `idempotency_key` contract;
- no global whole-request ScriptLock;
- common concurrency acceptance for independent resources;
- cross-project concurrency/root-isolation acceptance runner;
- Marketplaces and Birzha client profiles/handoff rules;
- executable common and Sheets acceptance runners;
- CI syntax/contract checks;
- migration and cutover documentation.

Client readiness received from projects:
- Birzha client protocol v1 / chunked Sheets / stage-verify-commit-rollback: READY; production cutover NO.
- Marketplaces client protocol v1 / idempotency / resumable upload / fixed-root security: READY; production cutover NO.
- Marketplaces previously reported large-read as the remaining common Bridge blocker; alpha.2 implements that transport in code, but it is not considered accepted until live exact-size/SHA256 download passes.

Still required before PRODUCTION READY:
- merge alpha.2 only after CI PASS;
- create real, separate Apps Script deployments from the shared source for each client;
- bootstrap separate bridge secrets into project-specific Yandex Lockbox bindings;
- live authenticated health/security acceptance on each deployment;
- live Drive small-file acceptance;
- live ~16 MiB or larger resumable upload + direct large-download exact byte/SHA256 acceptance on Marketplaces;
- harden/accept Google Sheets staged write behavior against live Sheets for Birzha;
- run `scripts/cross_project_acceptance.py` against live Marketplaces + Birzha deployments;
- execute project Terraform plans without cutover first;
- perform client-specific live E2E tests;
- only after all PASS update production system maps and remove legacy shared paths.

No production client has been cut over yet. This remains deliberate.
