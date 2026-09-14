# Bridge v1 — external owner gates

## Yandex Cloud

No manual Yandex resource creation is required for Bridge v1.

The final design reuses the already isolated project Lockboxes and adds one new key per project:

- Marketplaces: `marketplaces-mcp-api-credentials` → `gdrive_bridge_v1_secret`
- Birzha: `birzha-mcp-forecast-test-auth` → `gdrive_bridge_v1_secret`

Bootstrap creates a new Lockbox version from the current base version and verifies that every pre-existing key is preserved. The legacy Bridge keys remain available for rollback until final cutover is accepted.

## Google owner interaction

One owner-interactive Google authorization is unavoidable because Apps Script projects/web-app deployments must be created and authorized as the Google Drive owner.

Use:

```text
python tools/bootstrap_bridge_v1_apps_script.py --credentials <Google Desktop OAuth credentials.json>
```

The helper performs the rest:

1. requests Drive / Sheets / Apps Script scopes with PKCE;
2. verifies both fixed Drive roots;
3. creates separate Marketplaces and Birzha Apps Script projects;
4. uploads the canonical Bridge v1 source plus private per-project deployment configuration;
5. creates immutable versions and Web App deployments;
6. generates separate high-entropy Bridge secrets without printing them;
7. transfers each secret to a temporary GitHub Environment `test` secret via stdin;
8. bootstraps each project Lockbox key;
9. runs project acceptance;
10. deletes the temporary GitHub secrets in a `finally` block;
11. writes only non-secret deployment IDs/URLs/run IDs to the local control result file.

If Google requires first-run script authorization, the helper opens the Apps Script editor and asks the owner to execute `bridgeAuthorizeOwner()` once. This consent cannot be delegated to CI or a service account.

Do not paste any Bridge secret, refresh token, OAuth client secret, resumable URI, or Lockbox payload into chat, GitHub source, logs, or documentation.
