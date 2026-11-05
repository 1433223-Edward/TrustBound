# Gate D — one live recovery proposal, approval pending

No generation request or fresh Docker experiment was run during preflight. 84 offline/backend tests pass.
Parent evidence is artifacts/gate-c-0021d4ee71e74a2eb82499da86d5de9a.json, not the earlier truncated run.
Current double_rounding SHA256 matches 941584c0c21d177f69549876fde5c99583924275b2154367c525fb629849533b.
Existing recovery_eligibility validates formal test/artifact identities and Gate C stdout/oracle bindings;
two confirmed failures qualify: 1.23495 expected123 observed124, and -1.23495 expected-123 observed-124.
No non-confirmed challenge or adversary rationale enters recovery context.

Minimal changes: recovery.generate_recovery/run_recovery accept explicit completion_tokens and optional
reasoning_tokens; existing defaults remain1024/None and the host recovery cap remains two. The Gate D
entry selects max_attempts1, remaining attempts0, model deepseek-v4.1-flash-1017 (configured ID must match),
client timeout60/max_attempts1/output_limit4096, task budget one POST and4096 reserved output tokens.
reasoning.max_tokens1024 is requested only if catalog confirms support. Prior live observation reported
1029 reasoning tokens for1024 requested: this control is not claimed as an exact measured hard bound.

scripts/check_gate_d.py defaults to evidence/configuration checks only. After explicit paid authorization,
--allow-paid-inference uses the existing controller, JSON parser, AST restriction and formal verify_patch.
No fixture replaces the returned patch. New proposal hashes and previous-version diffs are recorded.
Existing Runner launches fresh public and protected acceptance containers. If formally VERIFIED,
confirmed Gate C amounts are fed through the existing adversarial validator in a new container using a
TRUSTED_GATE_C_REPLAY data adapter: no network, model calls or new discovery. Host oracle recomputes
expectations. Replay evidence is stored separately as gate_c_replay_report for that candidate hash.

A confirmed replay mismatch still causes FAILED. Successful replay does not substitute for a fresh
independent adversarial proposal: adversarial_report is UNAVAILABLE with reason
FRESH_ADVERSARIAL_REQUIRES_SEPARATE_AUTHORIZATION, final_decision INCONCLUSIVE and controller
stop EVIDENCE_INCONCLUSIVE. A later live review would require separate explicit authorization; this
script cannot perform it. Formal failures, malformed output, truncation, timeout, unsupported AST and
permission rejection follow existing stop rules. Failed generation preserves initial history and
records an unverified attempt; no extra repair attempt or request is made.

Token/cost plan: output<=4096 (includes reasoning), input measured after response. At previously confirmed
catalog rates ($0.15/million input, $0.60/million output), output cost component <=$0.0024576 plus input.
At illustrative1000 input tokens, estimate $0.0026076; unknown usage remains unknown, not an invoice.
No existing reports, formal acceptance or sandbox constraints were changed. No Git push/cloud resources.

Stage 5 minimal prerequisites after acceptance: user-approved VM region/size and cost; deployment
credentials handled outside source; protected Docker host and original sandbox settings; private backend
binding, reverse proxy/TLS and demo access restriction; backend secrets, pinned image and dependencies;
evidence storage/retention; startup and graceful cleanup checks; deployment/release review. No provisioning
or Stage 5 implementation is part of Gate D.
