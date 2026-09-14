# Marketplaces MCP — Semantic Core TEST v17

Status: TEST runtime rollout candidate, 2026-09-14.

## Purpose

Add the server-side Semantic Core to the existing Marketplaces MCP TEST runtime without replacing the canonical multi-dataset archive, data catalog, advertising overlay, or Yandex/Google Drive storage architecture.

## Runtime entry

The single high-level business entry point is `marketplace_business_query`. The original natural-language question is preserved. The server resolves business meaning before source execution and fails closed when a safe binding is not available.

## Current WB semantic dataset

`wb_weekly_finance_main` is the audited 92-column Wildberries weekly realization archive. It is financial/realization data, not the complete customer-order funnel.

Approved archive executors are limited to penalties, paid storage, paid acceptance, sales/returns, logistics, deductions/adjustments, monetary WB reward, preliminary weekly acquiring, historical fulfillment observations, and historical warehouse-tariff context.

Every executable archive calculation requires `FULL_COVERAGE` from COMPLETE registry fragments and the corresponding canonical annual file. Different currencies are never combined and unrelated financial components are not silently netted.

## Hard semantic boundaries

- `orderDt` / `orderUid` in weekly finance are order context only; they cannot represent all customer orders.
- `deliveryMethod` is historical observed fulfillment, not current configuration.
- `dlvPrc` is the coefficient fixed when the supply was planned. After fixation expiry it is not proof of the coefficient actually charged and is never current live tariff truth.
- `warehouseLogisticsCoeff` is historical report context, not a current tariff source.
- current-state questions require a suitable live source or fail closed.
- Ozon semantic execution remains unbound in this phase and fails closed.
- `agencyVat` may exist in the current WB API response but is outside the audited 92-column canonical archive and has no approved Semantic Core binding.

## Storage/runtime unchanged

Google Drive remains canonical archive storage. Yandex Object Storage remains queue/job state, immutable candidate, staging/resume state and byte-for-byte backup. Google Apps Script remains the owner-operated Drive bridge/session broker. Yandex Cloud remains the runtime platform.

## Acceptance

Before merge, branch tests must validate the 92-field registry, Semantic Core guardrails and architecture map. After merge to infra `main`, the TEST deployment workflow must prove:

1. `marketplace_business_query` is exposed by the live MCP tool list.
2. architecture map version is `2026-09-14.v17` and advertises Semantic Core.
3. a current warehouse-tariff question fails closed with `source_not_suitable` and route `current_warehouse_tariff`.
4. existing archive, WB/Ozon connectivity, Redis limiter and security acceptance remain passing.

Production deployment is outside this change.
