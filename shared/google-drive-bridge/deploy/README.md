# Per-project Apps Script deployment

Deploy the SAME `bridge.gs`, `setup.gs` and `appsscript.json` for every project, plus exactly one project config file.

## Marketplaces
Use `marketplaces_config.gs`.

Expected identity:
- `project_id=marketplaces`
- root `1UVKUcFfDhCDk6nMHX1mWg9cRL05DT-OJ`
- Google Sheets extension disabled

## Birzha
Use `birzha_config.gs`.

Expected identity:
- `project_id=birzha`
- root `1A7IzjXYSCWReZXdtrPZgZgLTnFIifsT2`
- Google Sheets extension enabled

## Setup sequence

1. Create a NEW Apps Script project for this client. Do not reuse another project's deployment.
2. Add `bridge.gs`, `setup.gs`, `appsscript.json`, and the correct project config.
3. Run `installBridgeConfig()` manually and authorize Drive/Sheets scopes.
4. Run `createBridgeSecretOnce()` manually. Copy the returned secret only into the temporary secure bootstrap channel used to populate the project's Yandex Lockbox. Never paste it into ChatGPT/Git/issues/source files.
5. Deploy Web App as the owner and make it callable by the Yandex runtime without interactive Google login.
6. Run `bridgeSetupCheck()`.
7. Bootstrap the secret to the PROJECT-SPECIFIC Lockbox binding.
8. Run authenticated deep health and all applicable acceptance tests.
9. Delete the temporary bootstrap secret after Lockbox/runtime validation.

The Marketplaces and Birzha deployments must have different URLs and different secrets.
