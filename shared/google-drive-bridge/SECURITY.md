# Security model

## Mandatory isolation

Every project has an independent Apps Script deployment, shared secret, fixed root and Yandex Lockbox binding.

`project_id` is defense-in-depth and routing/correlation metadata. It is NOT a substitute for deployment/secret/root isolation.

## Root sandbox

All path operations begin from the fixed root. All file-id operations must walk parents/ancestry and fail closed unless the object is inside the root.

Shortcuts are rejected by default. If later supported, both shortcut object and resolved target must pass root validation.

## Secrets

Never commit or log:
- bridge shared secret;
- Yandex Lockbox payload values;
- Drive resumable session URI.

The bridge secret lives in Script Properties and its Yandex copy lives in the client project's Lockbox binding.

## Concurrency

No global request lock. The bridge may protect a tiny local idempotency metadata critical section with a short lock; resource-level locks are owned by the client orchestration layer.

## Mutations

All mutations require an idempotency key and must be replay-safe. Canonical data must not be destroyed before staged content is verified.
