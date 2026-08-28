# Bootstrap authorization: GitHub ↔ Yandex Cloud

## Goal

The only manual bootstrap work is establishing trust between GitHub Actions and Yandex Cloud. Normal infrastructure (for example `mcp-test`) must **not** be created manually during bootstrap.

## Non-negotiable sequence

1. Create a dedicated Yandex Cloud service account for GitHub automation.
2. Configure Workload Identity Federation / OIDC trust for the GitHub repository.
3. Bind only the minimum required roles to that service account.
4. Add the federation identifiers required by the GitHub workflow as repository variables/secrets where appropriate.
5. Run `Yandex Auth Preflight`.
6. Only when that workflow returns PASS may the bootstrap state be changed to `YC_OIDC_AUTH=PASS` and cloud-mutating Terraform workflows be enabled.

## Rule preventing the previous mistake

Do not ask the user to manually create normal managed resources (folders, registries, containers, buckets, Lockbox secrets) merely because GitHub has not yet been authenticated. If GitHub authentication is missing, the correct action is to finish authentication, not to bypass automation with manual provisioning.

## Safety

- No long-lived Yandex service-account key should be pasted into ChatGPT.
- Prefer short-lived OIDC / workload identity federation credentials.
- Production permissions must remain narrower than account-wide admin whenever practical.
- `terraform apply` remains disabled until auth preflight passes.
