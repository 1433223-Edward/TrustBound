# Stage 3 — Bounded Recovery

> **Historical Stage Record — Not the Current Release State.** Recovery 不是当前默认 Live Workspace 功能；本文保留阶段设计与实验记录。

## Audit and minimal change

Stage 2's trusted overall decision is `adversarial.final_decision`, attached by
`web_tasks.execute_web_run`. Confirmed challenge rows carry amount/expected/actual/type,
and their execution binds both candidate artifact_hash and trusted driver_hash.
`executor.run_executor` is a one-proposal flow with no retry loop. Stage 3 reuses its
parse_proposal and validate_billing_code, the same verify_patch Permission Gate, original
Runner, formal tests and adversarial validator. No core sandbox or acceptance rule changed.

The Stage 1/2 worktree was already dirty at entry. Those changes remain in place; no baseline
commit, reset, push, dependency installation or remote action was performed. Existing Stage 2
JSON evidence was not overwritten. This document describes Stage 3 additions only.

## Actual call chain and states

The existing `/api/runs` job first executes its original Stage 1/2 flow. Recovery defaults off.
When requested, `web_tasks.execute_web_run` passes the outcome, a formal+adversarial validation
callback and an injected client factory into `recovery.run_recovery`. This is the same single
worker and server-generated run ID; it does not create another job manager or agent framework.

Attempt 0 is the initial artifact. The host's explicit for-loop permits attempts 1 and 2 only.
Eligibility first checks task/artifact/test identities, normal process termination, cleanup,
workspace integrity and limits. A confirmed mismatch must agree with structured stdout and
`reference_cents`, not model rationale or unittest text. Each proposal uses a fresh context/client,
then existing JSON schema, AST, Permission Gate, public tests, formal acceptance, and independent
adversarial validation. A formal failure still stops downstream formal/adversarial work according
to Stage 1/2 rules; it cannot count as a successful full validation.

For a safe formal business-test failure with no structured observations, a fresh trusted fixed
four-input diagnostic runs through the existing adversarial harness and Docker Runner. It checks
1.005, -1.005, 1.239 and 1.00499. This is trusted deterministic diagnostic data, not model inference.
The diagnostic report is separate from the original formal/adversarial reports. It never upgrades
formal acceptance and never discloses protected test implementation to the recovery context.
If it cannot confirm a business mismatch (including unsupported candidate AST), recovery stops.

Stop conditions:

- VERIFIED: the last actual version has complete matching formal and adversarial evidence.
- RECOVERY_LIMIT_REACHED: two attempted repairs still failed; preserve FAILED and all evidence.
- FORMAL_REJECTED / unsupported AST: permission or code restrictions stop recovery immediately.
- EVIDENCE_INCONCLUSIVE / missing confirmed observations: no repair request is authorized.
- Unsafe termination, timeout, cleanup/integrity/limits failures, wrong hashes/tests: stop without repair.
- Malformed JSON/schema, empty output, API error, timeout, missing key or request budget: count the
  attempted model proposal and stop immediately. These failures are not business counterexamples.
- DUPLICATE_CANDIDATE: a previously seen code hash consumes one attempt and stops; no stale test reuse.

Invalid proposal and model failures use INCONCLUSIVE; unsupported AST uses REJECTED. Security/system
failure stop reasons never authorize another proposal. No failure can be converted to success from a
model's claim. No recursive calls, model-controlled attempt limit, debate or autonomous test changes.

## Allowlisted recovery context

`build_recovery_context` receives only the trusted requirement constant, fixed task ID, current
billing.py content and SHA-256, at most four confirmed input/expected/actual/type observations,
sanitized sandbox identity/exit/cleanup flags, and remaining attempts after the current request.
First recovery carries remaining=1; second remaining=0. No full executor/adversary conversation,
private rationale, raw formal stderr, protected acceptance source, API key or Docker interface
is sent. `recovery_messages` treats candidate text as untrusted user data and creates new messages.
Host-owned permissions and budgets are not editable model context.

This is application-level context separation. It is not proof against model prompt injection;
schema/AST/Permission Gate and real evidence remain authoritative even if a model follows bad text.

## Backward-compatible report contract

POST adds recovery_mode=off|offline|live and recovery_fixture=fixed|exhausted|unauthorized|
invalid_json|empty|failure|timeout. Default mode is off; max attempts is always host-owned two.
Recovery requires adversarial_mode!=off. Error presets require explicit offline mode.
Requests still cannot upload code, failure evidence, histories, policies, limits or commands.

Snapshots add recovery_report and current_attempt. Progress is persisted through the same
RunManager snapshot path. `recovery_report` contains run_id, max_attempts, status RUNNING/
STOPPED/COMPLETED, current_attempt, validated_attempt_index, stop_reason, final_status,
final_decision and independent attempts. Each attempt contains:

- run_id, attempt_index, candidate_hash, previous_candidate_hash;
- recovery_trigger, confirmed_failure_evidence, allowlisted context;
- candidate/proposal, diff_from_previous and model source/call metadata;
- its own verification, adversarial_report, optional diagnostic_report and final_decision;
- stop_reason; failed model generation has null verification and no borrowed execution evidence.

Top-level Stage 2 fields project the last formally evaluated candidate for compatibility.
Recovery's terminal overall verdict is recovery_report.final_status / final_decision. When generation
fails, validated_attempt_index still identifies the previous evaluated candidate; the final attempted
entry remains unverified with its own INCONCLUSIVE/REJECTED status. Frontend gives the recovery
verdict priority and labels which attempt the main code pane displays. Every candidate's execution
hash must match its own version; the old report is never rewritten to claim a new artifact passed.

## UI and tests

The existing Task Panel adds recovery mode/preset selectors. The existing Evidence Panel adds
Recovery with attempt history, trigger, confirmed input evidence, previous-version diff, per-round
formal/adversarial results, logs and stop reason. A running job shows the backend attempt index.
Offline repair proposals are labeled OFFLINE / MOCK. There is no persistence of a stale RUNNING
state on reload, and changing options clears the previous history. UI guards validate attempt
chains, a maximum three entries including initial, per-version report identities and final verdict.

Local startup commands remain unchanged (single loopback API worker and Vite). Run
`.\.venv\Scripts\python.exe -B scripts/check_recovery_integration.py` for ten real HTTP/Docker
experiments. It writes only new Stage 3 artifacts. Unit tests use explicit verification doubles;
they are not claimed as fresh container execution. See EXPERIMENTS.md for measured outcomes.

## Live Vultr entry: prepared, not exercised

Configuration presence was checked without printing values or contacting the model service.
No effective VULTR_INFERENCE_API_KEY or VULTR_MODEL was present; live inference is untested.
`check_recovery_live.py` defaults to a configuration-only check with no Docker/network operations.
Only after explicit user authorization should the user set backend environment variables locally:
VULTR_INFERENCE_API_KEY, VULTR_MODEL, TRUSTBOUND_ENABLE_LIVE=1 and
TRUSTBOUND_ENABLE_RECOVERY_LIVE=1. Never place keys in frontend, chat, source or Git.
Then run `.\.venv\Scripts\python.exe -B scripts/check_recovery_live.py --allow-paid-inference`.
The prepared experiment starts from the fixed double_rounding fixture and retains OFFLINE
adversarial proposals, so only recovery completions consume model inference. Real sandbox tests
are still mandatory. Web live recovery also checks the separate host opt-in.

Each recovery completion caps output at 1024 tokens, 30-second client timeout, at most two transport
attempts (existing policy retries explicit 429 only), at most two recovery proposals. The existing
client also limits serialized request size to 12000 characters. Token usage and estimated USD from
catalog pricing are recorded per call; absent usage/rates remain unknown, never invented as zero.
Timeout billing can be unknown. No hard dollar/invoice guarantee or real cost measurement was made.

## Ownership: functions to read in order

1. formal_evidence_problem — safety and identity prerequisite before repair.
2. confirmed_failures — bind observed data to the trusted business oracle.
3. recovery_eligibility / diagnostic_client — decide whether a repair request is justified.
4. build_recovery_context / recovery_messages — minimal data and context isolation.
5. generate_recovery / offline_recovery_client — bounded injectable model proposal.
6. complete_verification (web_tasks) — reuse Stage 2 after each formal validation.
7. run_recovery — explicit host loop, attempt snapshots and stopping.
8. complete_success — final candidate-specific proof obligations.
9. RunManager.work — one existing API job, live progress and persistence.
10. validateRecoveryReport / RecoveryPanel.vue — UI evidence guards and presentation.

No Stage 4, new task type, cloud deployment, arbitrary uploads or safety-policy changes are included.


## Stage 3 file changes and rationale

- trustbound/recovery.py (new): the project had no bounded repair control; adds eligibility,
  sanitized context, injectable single-proposal generation, strict version binding and finite history.
- trustbound/web_tasks.py: extracts the existing Stage 2 report attachment into complete_verification
  and adds an optional recovery wrapper. Existing off-mode behavior and core execution stay intact.
- trustbound/api.py: adds narrow recovery flags, separate live authorization and progress fields
  to the existing job. No client-controlled attempt count or extra scheduler/command interface.
- frontend/src/state/workspace.js: one recovery state source, progress, option resets and final validation.
- frontend/src/api/adapter.js: rejects broken attempt chains and unrelated success evidence.
- frontend/src/api/client.js: bounded polling becomes 300 seconds to accommodate full revalidation.
- frontend/src/App.vue: wires existing components and uses recovery overall verdict/source labels.
- frontend/src/components/TaskPanel.vue: explicit recovery modes/presets; existing layout retained.
- frontend/src/components/RecoveryPanel.vue (new): per-attempt evidence, diffs, source and stop reasons.
- frontend/src/components/EvidencePanel.vue: adds the Recovery tab and prioritizes recovery verdict.
- frontend/src/components/CodeWorkspace.vue: labels the actual recovery attempt/source so a repaired
  candidate cannot be mistaken for the originally selected fixed fixture or for live inference.
- tests/test_recovery.py (new), tests/test_api.py, frontend/tests/recovery.test.js (new): cover control,
  context/credential/policy boundaries, bounded failures and UI evidence/version guards.
- scripts/check_recovery_integration.py (new): ten actual HTTP/Docker experiments, separate from unit doubles.
- scripts/check_recovery_live.py (new): default read-only config check; paid inference requires explicit flag.
- README.md, docs/WEB_API_CONTRACT.md, docs/EXPERIMENTS.md and this document describe the implemented
  behavior. New Stage 3 JSON snapshots preserve old Stage 1/2 historical reports.
