# Bridge v1 runtime provisioning status

Date: 2026-09-14

## Completed centrally

- Bridge v1 protocol/source is merged; current release `1.0.0-alpha.2`.
- Marketplaces client is READY for live acceptance; production remains on legacy Bridge v3.
- Birzha client is READY for infrastructure deployment/live acceptance; legacy dependency remains until cutover PASS.
- Marketplaces bootstrap/acceptance/cutover-gate workflows exist.
- Birzha bootstrap/acceptance/static-validation/cutover-gate workflows exist.
- Cross-project concurrency/root-isolation acceptance exists.
- MCP Advertising is documented as a Marketplaces subsystem (`project_id=marketplaces`), not a third deployment.

## External provisioning gates still open

### 1. Google Apps Script owner action

Two real Apps Script Web App deployments do not yet exist:

- Marketplaces Bridge v1 alpha.2
- Birzha Bridge v1 alpha.2

The available Google Drive connector cannot create Apps Script projects/deployments. Each deployment must be created/authorized by the Google Drive owner from the shared source in this directory and configured with the corresponding project config.

No production route is changed by this setup.

### 2. Yandex Lockbox creation policy

Desired dedicated empty Lockboxes:

- `marketplaces-google-drive-bridge-v1`
- `birzha-google-drive-bridge-v1`

Automated creation was attempted with the existing GitHub/Yandex deployer. `Secret.Create` returned `PermissionDenied` even after temporary TEST-folder `admin` and then service-specific `lockbox.admin` were granted and allowed time to propagate. All temporary elevated bindings were revoked after each failed attempt.

Read-only diagnostics confirmed:

- the deployer can list existing Lockboxes;
- `lockbox.admin`, `lockbox.editor`, and `lockbox.payloadViewer` roles exist;
- no cloud-level access-policy binding was returned;
- organization-level access-policy inspection itself is denied to the CI identity;
- therefore an organization-level policy / higher-level identity restriction remains the likely blocker.

Target Lockboxes MUST NOT be reported as created until actual resource IDs are observed.

## Existing project-specific Lockboxes (not the target dedicated Bridge v1 Lockboxes)

- Marketplaces: `marketplaces-mcp-api-credentials` (`e6qb8b3u57e71731j1os`)
- Birzha: `birzha-mcp-forecast-test-auth` (`e6q98dsvire45t1tiko7`)

These remain untouched by the Bridge v1 provisioning attempts.

## Next gate after the external resources exist

1. Validate each dedicated Apps Script identity/root/capabilities.
2. Bootstrap matching secret into its project-specific Bridge Lockbox without exposing the value.
3. Grant only the project runtime service account `lockbox.payloadViewer` to its own Bridge Lockbox.
4. Marketplaces live acceptance: deep health/security, resumable upload >=16 MiB, direct large-read exact size/SHA256, independent-resource concurrency.
5. Birzha live acceptance: deep health/security, staged/chunked Sheets, BR YDB -> Bridge -> Sheets parity.
6. Cross-project simultaneous concurrency/root-isolation acceptance.
7. Only after full PASS perform separate production cutover changes.

Production cutover status: **NO**.
