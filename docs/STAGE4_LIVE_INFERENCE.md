# Stage 4 preflight and offline validation

> **Historical Stage Record — Not the Current Release State.** 本文的配置检查与离线验证不构成当前私有 Workspace 真实 Vultr 调用成功的验收。

Status: BLOCKED_FOR_LIVE_CREDENTIALS_AND_APPROVAL. No paid inference was requested.
Process and user configuration presence checks found no VULTR_INFERENCE_API_KEY or VULTR_MODEL.
Cloud credit receipt does not establish Inference subscription or model access; neither was authenticated.

Public GET /v1/models?format=openrouter succeeded without a key. Captured catalog is
artifacts/stage4-model-catalog.json. Proposed model deepseek-v4.1-flash-1017 is actually present,
text output and response_format/structured_outputs are advertised. Prompt price 0.00000015 USD/token,
completion 0.0000006 USD/token. This confirms advertised capabilities, not successful JSON inference.
Official reference: https://api.vultrinference.com/docs/models . Catalog prices are estimates, not invoices.

## Changes

inference.py previously bounded only individual clients. TaskInferenceBudget and task_inference_budget
now share reservations across all clients in one Web task, using ContextVar, without sharing messages.
At most 14 generation HTTP attempts and 14336 reserved output tokens; requests reserve before transport,
including retries and errors. No refund for unknown billing. Per-request existing caps remain 1024 tokens,
30 seconds, two attempts, retry only explicit 429. Catalog reads are not generation requests.
web_tasks.py wraps the existing flow and adds inference_usage. Existing Executor, adversarial validator,
Recovery loop, Permission Gate, tests and Runner security settings are reused.
Frontend workspace/App/EvidencePanel add live/offline call counts, actual model IDs, token usage,
estimated cost and billing status, including failed API outcomes. Unknown values stay unknown.
No real Live report was available for browser verification; this remains L7 pending.
New test_task_budget.py covers cross-client caps, failed-request reservation, scope reset and unknown cost.
check_stage4_offline.py exercises real containers with only injected model responses.
check_stage4_live.py defaults to configuration-only and requires --allow-paid-inference for smoke or e2e.

## Verification

72 backend regression tests, including Stage 1–3, passed; 46 frontend tests and production build passed.
New real Docker experiments: offline executor VERIFIED (public/acceptance/adversarial),
L3 double_rounding FAILED despite formal VERIFIED, L4 one repair to VERIFIED after fresh full validation.
Total 12 actual container executions, with zero live model calls. Raw records: docs/stage4-offline-results.json.
L5 error handling uses unit transport doubles; actual provider rate-limit/timeout behavior untested.
Historical Stage 1–3 evidence has not been overwritten. No Git commit or push.

## Approval plan, not yet executed

First L1: one READY request, output 64 tokens, at most two HTTP attempts (reserve <=128).
Only after it succeeds, L2/e2e: live Executor, live adversary and eligible live recoveries within one task.
Typical path three completions: Executor smoke64 + proposal1024 + adversary768. At most seven
logical completions with two recoveries; at most fourteen HTTP attempts and 14336 reserved output tokens.
Separate L1 plus E2E maximum sixteen attempts / 14464 reserved output tokens.
For an illustrative 2000 input tokens per attempt at current catalog rates, estimate <=0.014 USD;
actual prompt tokenization, provider behavior and invoice cannot be confirmed in advance.
No hard dollar cap is claimed. Usage/prices missing or failed requests keep billing unknown.

User must configure the Inference key locally, VULTR_MODEL to the catalog-approved ID,
TRUSTBOUND_ENABLE_LIVE=1 and (for recovery) TRUSTBOUND_ENABLE_RECOVERY_LIVE=1 in the backend
process environment. Never send the key in chat or put it in source/frontend/Git.
After explicit user paid-inference approval, run check_stage4_live.py --phase smoke --allow-paid-inference,
then the separately bounded --phase e2e command. Each writes a fresh UUID report under artifacts.
Do not substitute fixtures when real generation fails. L1/L2/live adversary/recovery and L7 remain pending.

Stage 5 prerequisites remain user-approved Vultr VM provisioning, credentials and spending scope,
loopback/reverse-proxy and TLS/access controls, safe Docker host configuration, report retention and
an explicit deployment review. No VM service was provisioned in this stage.
