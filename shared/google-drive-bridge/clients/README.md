# Client integration rules

Client projects consume Bridge v1 through an adapter. They do not fork protocol semantics.

## Required call fields

Every protected request:
- `project_id`
- `request_id`
- `action`
- `payload`

Every mutating request additionally:
- `idempotency_key`

## Required client-side behavior

- generate a unique request id for each logical attempt chain;
- reuse the same idempotency key when retrying the same logical mutation;
- use bounded exponential backoff with jitter for retryable errors;
- never retry non-idempotent legacy writes after an ambiguous timeout;
- never log bridge secret or resumable session URI;
- keep resource locks and durable workflow state in the project orchestration layer;
- validate returned project/root/protocol during startup/deep health.

## Migration principle

Do not rewrite business logic to fit the bridge. Replace only the transport/security boundary and retain the project's existing orchestration and domain semantics.
