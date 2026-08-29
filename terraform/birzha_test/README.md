# BIRZHA MCP Forecast TEST Terraform

This directory is deliberately isolated from the existing marketplace TEST configuration.
It manages only the BIRZHA Forecast MCP TEST environment.

## Safety rules

- No `terraform apply` is performed by the M1.3 preparation workflow.
- No Lockbox secret is created in M1.3.
- The Serverless Container remains private; only the dedicated gateway service account can invoke it.
- External ChatGPT-to-MCP authentication is not invented here. The first public TEST gateway exposes only the harmless `system.version` surface from the application.
- MCP DNS-rebinding protection stays enabled.
- The Yandex Terraform provider is pinned and the generated `.terraform.lock.hcl` is committed.

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

M1.3 PREP stops before all applies. Deployment is intentionally split into two approval boundaries because a Yandex Registry digest cannot exist before the dedicated BIRZHA registry itself exists.

1. **Foundation apply**: create only the folder, registry, service accounts and foundation IAM with `mcp_image_url = null`.
2. **Immutable image**: the `birzha-mcp-forecast` application workflow builds the exact approved `main` commit, tags it with the full Git SHA, pushes it to the newly created BIRZHA registry and records the registry digest.
3. **Runtime plan**: update Terraform with the exact source SHA and immutable image digest, then produce a new plan for the private container, gateway invoker binding and API Gateway. This plan requires a second pre-apply check.
4. **Remote bootstrap apply**: apply the approved runtime plan initially with the fail-closed placeholder host. The Gateway exists but MCP Host traffic is not yet accepted.
5. **Gateway host binding**: read the real `api_gateway_domain`, then apply a new container revision with exactly:

```text
<gateway-domain>,<gateway-domain>:*
```

The `:*` form is a wildcard for the port only and does not authorize other Yandex API Gateway domains.
6. **Remote acceptance**: verify `/healthz`, MCP discovery, `tools/list`, `system.version`, client/SDK identity and the actually negotiated MCP protocol version.

Yandex API Gateway forwards the caller-facing Gateway Host header to the container, so the real Gateway domain and the same domain with wildcard port are the intended MCP `allowed_hosts` values.

## Source commit -> image rule

Deployment must never refer only to `latest` or a mutable branch name. Required evidence chain:

```text
approved application main commit SHA
-> Docker build in birzha-mcp-forecast CI from that exact SHA
-> image tag git-<40-char-sha>
-> push to the dedicated Yandex BIRZHA registry
-> immutable registry digest sha256:...
-> infra receives only source SHA + immutable image reference/digest
-> Terraform source_commit_sha records the same source SHA
```

The infra repository does not need read access to the private application repository. The application repository owns source checkout/build/push; the infrastructure repository owns Yandex resource deployment. See the source-to-image ADR in `docs/`.
