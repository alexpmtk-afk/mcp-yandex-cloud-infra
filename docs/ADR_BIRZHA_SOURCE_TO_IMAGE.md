# ADR — BIRZHA source commit to immutable Yandex image

Status: PROPOSED FOR M1.3 PRE-APPLY REVIEW

## Decision

The application repository owns source checkout, Docker build and image publication. The infrastructure repository owns Yandex Cloud resource deployment.

```text
alexpmtk-afk/birzha-mcp-forecast
  approved main commit SHA
  -> GitHub Actions checkout of that exact SHA
  -> Docker build
  -> tag git-<40-char-sha>
  -> push to dedicated BIRZHA Yandex Container Registry
  -> capture immutable registry digest

alexpmtk-afk/mcp-yandex-cloud-infra
  receives exact source SHA + immutable image reference/digest
  -> terraform plan
  -> pre-apply review
  -> terraform apply
```

The infrastructure repository MUST NOT clone/read the private application repository during deployment. This avoids introducing a broad cross-private-repository PAT or deploy key.

## Reproducibility rule

A deployable image is identified by both:

- the exact 40-character application commit SHA; and
- the immutable registry digest (`sha256:...`).

Mutable references such as `main`, `latest`, or a tag alone are not deployment evidence.

## Approval boundaries

A dedicated BIRZHA Container Registry does not exist before the foundation is applied, therefore a real Yandex registry digest cannot be produced before that registry exists. M1.3 is split deliberately:

### Gate A — Foundation

Terraform plan with `mcp_image_url = null` may create only:

- `birzha-mcp-forecast-test` folder;
- dedicated BIRZHA Container Registry;
- runtime service account;
- gateway service account;
- required foundation IAM binding(s).

No Serverless Container, API Gateway, Lockbox or market/forecast resource is created in Gate A.

### Gate B — Immutable image

After Gate A is approved and applied, the application repository builds the approved `main` SHA and pushes it to the dedicated BIRZHA registry. The workflow records the returned registry digest.

### Gate C — Runtime

The infrastructure repository receives the exact source SHA and digest and creates a fresh Terraform plan. Only that reviewed plan may create:

- private Serverless Container;
- gateway-to-container IAM binding;
- API Gateway.

Remote Host security is initially fail-closed, then rebound in a subsequent container revision to:

```text
<gateway-domain>,<gateway-domain>:*
```

## Authentication for image publication

Preferred end-state: GitHub OIDC / Workload Identity Federation with least privilege.

Current Yandex bootstrap has an approved authorized-key fallback because OIDC remains pending. If the fallback is used for the first TEST image publication, the credential must be stored only as a GitHub Actions secret, never in source, logs, Terraform plan or ChatGPT. Its IAM scope must be reviewed before use.

No new permanent application-level authorization scheme is introduced by this ADR.

## Consequences

Positive:

- no cross-private-repository checkout;
- exact source provenance;
- immutable deployment evidence;
- clear separation of application CI and infrastructure deployment;
- no fabricated/local-only image digest presented as a Yandex registry digest.

Trade-off:

- deployment has a deliberate foundation approval before the first image digest can exist.
