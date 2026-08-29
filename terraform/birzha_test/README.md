# BIRZHA MCP Forecast TEST Terraform

This directory is deliberately isolated from the existing marketplace TEST configuration.
It manages only the BIRZHA Forecast MCP TEST environment.

## Safety rules

- No `terraform apply` is performed by the M1.3 preparation workflow.
- No Lockbox secret is created in M1.3.
- The Serverless Container remains private; only the dedicated gateway service account can invoke it.
- External ChatGPT-to-MCP authentication is not invented here. The first public TEST gateway exposes only the harmless `system.version` surface from the application.
- MCP DNS-rebinding protection stays enabled.

## Remote state

The already-proven central Yandex Object Storage backend bucket is reused, with an isolated key:

```text
birzha-mcp-forecast/test/terraform.tfstate
```

No marketplace state key is shared.

## Planned resources

```text
birzha-mcp-forecast-test folder
├── birzha-mcp-forecast Container Registry
├── birzha-mcp-forecast-runtime service account
├── birzha-mcp-forecast-gateway service account
├── private birzha-mcp-forecast-test Serverless Container
└── birzha-mcp-forecast-test-gateway API Gateway
```

No Lockbox resource is part of this configuration.

## Deployment phases after review

M1.3 PREP stops before all applies. If the plan is approved, deployment is intentionally phased:

1. **Foundation**: apply with `mcp_image_url = null` to create only folder, registry and service accounts/IAM needed for the runtime foundation.
2. **Immutable image**: build the exact approved `birzha-mcp-forecast` commit, tag it with the full Git SHA, push it to the BIRZHA registry, and record the registry digest.
3. **Remote bootstrap**: apply with the pushed immutable image and the fail-closed placeholder host. This creates the private container and API Gateway but does not yet authorize remote MCP Host traffic.
4. **Gateway host binding**: read the real `api_gateway_domain` output, then apply again with `mcp_allowed_hosts` set to that exact domain. Yandex Serverless Containers create a new revision when environment variables change.
5. **Remote acceptance**: verify `/healthz`, MCP discovery, `tools/list`, `system.version`, client/SDK identity and the actually negotiated MCP protocol version.

Yandex API Gateway forwards the caller-facing Gateway Host header to the container, so the exact Gateway domain is the intended MCP `allowed_hosts` value.

## Source commit -> image rule

Deployment must never refer only to `latest` or a mutable branch name. Required evidence chain:

```text
approved application commit SHA
-> Docker build from that exact SHA
-> image tag git-<40-char-sha>
-> pushed registry digest sha256:...
-> Terraform mcp_image_url pinned to that pushed image/digest
-> source_commit_sha stored in container metadata/environment
```

The final cross-private-repository checkout mechanism is a deployment ADR. Preferred direction is a narrowly scoped read-only mechanism (for example a repository-specific deploy key), not a broad PAT.
