# Migration plan

## Phase 0 — freeze
- No production cutover while bridge v1 is under acceptance.
- Existing Marketplaces and Birzha business flows remain unchanged.

## Phase 1 — shared standard
- Land common protocol, config model, security rules, acceptance matrix.
- Build versioned Apps Script source and client helper.

## Phase 2 — Marketplaces reference migration
- Deploy isolated Marketplaces bridge v1 from shared source.
- Keep Marketplaces Redis/Valkey orchestration and Object Storage state.
- Adapt client calls to v1 envelope.
- Pass Drive small/large read-write, root isolation, idempotency and concurrency tests.

## Phase 3 — Birzha migration
- Provision Birzha-specific Apps Script deployment, secret, Lockbox and root.
- Remove Marketplaces bridge/secret/Lockbox dependency.
- Adapt Birzha bridge client to protocol v1 and Sheets extension.
- Pass staged/chunked Sheets parity and rollback tests.

## Phase 4 — cross-project acceptance
- Run Marketplaces large-file activity while Birzha updates a spreadsheet.
- Verify no cross-project blocking or credential/root overlap.

## Phase 5 — cutover
- Mark old shared Marketplaces/Birzha route deprecated.
- Switch production env bindings.
- Keep rollback references until post-cutover validation is complete.

## Phase 6 — cleanup
- Remove temporary shared credentials/addons only after both clients pass post-cutover checks.
- Archive obsolete bridge code paths and update system maps/docs.
