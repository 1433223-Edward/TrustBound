# Workspace Recovery P0 reliability boundaries

> **Historical Stage Record — Not the Current Release State.** 本文记录 Recovery P0 的设计与测试边界；Recovery Agent 不是当前默认 Live Workspace 功能。当前边界见 [README](../README.md)。

The existing Workspace SQLite database gains run_requests and run_events. The quota database gains model_requests, model_request_events and run_admissions. All changes create new tables; existing projects, freezes, source archives, reports and aggregate quota counts are retained. Billing recovery remains a separate orchestration.

## Identities and state transitions

- Workspace run: project + idempotency_key + canonical request fingerprint. The durable claim precedes quota reservation and dispatch. The same key with different data returns 409. A repeated recovery request returns the existing child. Old API clients remain accepted, but should explicitly reuse an idempotency_key to deduplicate ordinary runs.
- Model request: run ID + agent role. CREATED -> RESERVED -> SENT -> RESPONSE_RECEIVED -> FINALIZED. Global model counters and RESERVED commit in one quota-database transaction. Request IDs, numerical call metadata, provider response ID and final verdict are recorded without hidden reasoning.
- On startup CREATED/RESERVED becomes PRE_SEND_FAILED. Only this confirmed pre-send reservation can be released, once. SENT becomes UNKNOWN_BILLING and retains its reservation. No automatic retransmission or provider-side refund is inferred, including from an HTTP error.
- Persisted QUEUED/RUNNING tasks become ERROR with WORKSPACE_RUN_INTERRUPTED. Received or old partial evidence never turns that interrupted task into VERIFIED. Legacy RUNNING rows without model journals are conservatively classified UNKNOWN_BILLING.
- Retry links are released only when every journaled model request was pre-send and no successful candidate was produced. A sent, received, or unknown-billing request keeps the parent locked. An explicit new request key is needed for a new attempt after a confirmed pre-send failure; the old key still returns the old failed child.

The frontend retains the request key across a lost submission response, using sessionStorage when available. Refresh discovers saved runs; it does not automatically pay for another generation.

## Deliberate limits

Startup reconciliation assumes the existing singleton, one-worker local service. It is not a multi-instance lease system or arbitrary Docker checkpoint continuation. Completed response metadata is durable, but there is no automatic reconstruction of an unfinished candidate from it. Unknown billing has no automatic unlock or refund path.

The execution request protocol applies to Workspace runs and their Executor/Adversarial/Recovery completions. Quick chat and plan-generation are advisory endpoints, not executable runs; their POST response replay is not part of this task protocol. Billing has not been migrated to Workspace task identities.

The reviewed Vultr Chat Completion reference does not document an idempotency guarantee:
https://api.vultrinference.com/docs/reference/create-chat-completion
No provider exactly-once guarantee is claimed. SENT is a conservative write-before-transport boundary, so a crash immediately before transport may also remain UNKNOWN_BILLING.

Restoring an editor draft, reverifying an accepted candidate, and writing back the user's original disk project remain separate operations. This change adds no host-file or Git rollback.

## Verification

Tests cover concurrent duplicate submission, changed-payload conflict, actual child-process exit before and after dispatch, durable startup interruption, quota sharing across parallel roles, timeout locking, pre-send retry-link release, evidence tampering, independent revalidation and historical snapshots. All model HTTP traffic in these tests is synthetic. No real paid inference is needed.
