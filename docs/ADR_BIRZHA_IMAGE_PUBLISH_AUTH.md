# ADR — BIRZHA image publisher authentication

Status: PROPOSED FOR MCP-M1.3 IMAGE PUBLISHER IAM PREP

## Decision boundary

This ADR covers only how `alexpmtk-afk/birzha-mcp-forecast` will authenticate to Yandex Container Registry in order to push the Docker image built from the exact approved application commit.

It does not authorize creation of the Serverless Container, API Gateway, Lockbox, MOEX/ALGOPACK resources or Forecast resources.

## Dedicated publisher identity

Create a dedicated service account:

```text
birzha-mcp-forecast-publisher
```

It must not reuse:

- `birzha-mcp-forecast-runtime`;
- `birzha-mcp-forecast-gateway`;
- a broad central deployer identity for the actual image push.

The publisher receives only:

```text
container-registry.images.pusher
```

on the specific BIRZHA registry:

```text
crpk5qvf4p7kcqil2u3v
```

The Terraform provider does not expose a registry-level `*_iam_member` resource, so the registry-level `yandex_container_registry_iam_binding` resource is used. It is authoritative for `container-registry.images.pusher` on this registry; therefore no out-of-band members should be added to that role without first importing/declaring them in Terraform.

## GitHub Actions -> Yandex authentication

Preferred target: short-lived OIDC / Workload Identity Federation.

Current central infrastructure evidence still marks direct GitHub OIDC authentication as `PENDING`, while authorized service-account-key authentication is the proven fallback. Therefore the first image-publish implementation should use the fallback unless OIDC is separately repaired and proven before publishing.

Fallback contract:

1. After publisher IAM is approved and applied, create an authorized key only for `birzha-mcp-forecast-publisher`.
2. Store the JSON credential only as a GitHub Actions secret in `alexpmtk-afk/birzha-mcp-forecast`.
3. Do not store the credential in source, artifacts, Terraform state outputs, chat, logs or Docker image layers.
4. The publisher service account receives no additional IAM roles.
5. The workflow writes the credential to an ephemeral runner file only when required, uses it for Yandex authentication, and deletes the file in an `always()` cleanup step.
6. Docker build must use the exact approved application SHA, currently:

```text
e8463b8a034b2a7ed92ac06894ce960d9fa3a021
```

7. Image tag must include the full source SHA and must not use `latest` as deployment evidence.
8. After push, record the immutable Yandex Registry digest `sha256:...` and pass only `source SHA + immutable digest` to the infrastructure repository.

## Planned application CI flow after publisher IAM approval

```text
approved application main SHA
-> checkout exact SHA
-> existing tests / Docker smoke
-> authenticate as birzha-mcp-forecast-publisher
-> docker build
-> tag cr.yandex/crpk5qvf4p7kcqil2u3v/birzha-mcp-forecast:git-<40-char-SHA>
-> push
-> query/record immutable Yandex image digest sha256:...
-> publish non-secret evidence artifact containing source SHA, tag and digest
-> remove ephemeral credential
```

No Terraform apply and no runtime deployment belongs in the application image-publish workflow.
