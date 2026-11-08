# Stage 2 — Independent adversarial verification

> **Historical Stage Record — Not the Current Release State.** 本文保存 Stage 2 的离线/实验验证记录；Adversarial Agent 不属于当前默认 Live Workspace 功能。当前边界见 [README](../README.md)。

## Scope and execution

Stage 1 formal acceptance, Permission Gate, Runner constraints and VerificationReport remain intact.
`web_tasks.execute_web_run` first invokes `_execute_base_run`, which runs fixed candidates or
`run_executor`. Only a formally VERIFIED candidate is eligible for the requested adversarial stage.
`adversarial.run_adversarial` verifies its SHA-256 and the existing restricted AST, creates an
independent model context, parses bounded test data, computes a trusted oracle, then calls the
existing `runner._execute_fixed_tests` with phase adversarial. Candidate Python is imported only
inside a new restricted Docker container. The host never executes candidate code.

`final_decision` binds task/artifact identity and produces an additive overall decision.
It does not mutate the original formal report. Evidence requires observed results, consistent
exit code, artifact/driver hashes, unchanged workspace, verified limits and confirmed cleanup.
An incomplete run cannot confirm a counterexample. No formal failure can be upgraded.

## Context construction and provenance

Executor: existing `executor.run_executor` supplies the original task and allowed source;
its proposal, messages and call ledger stay in the executor record.
Adversary: `adversarial.build_context` creates a new allowlist: task ID, trusted requirement ID
and requirement text from module constants, candidate billing.py content and its verified hash.
`build_messages` creates exactly a fresh system message plus JSON user data. No executor
conversation, internal analysis, defense, protected acceptance implementation or API key is passed.
Candidate comments/strings are explicitly untrusted data, never higher-priority instructions.
`web_tasks.execute_web_run` creates a fresh client for the adversary and forwards only the artifact.
Automatic tests check both the context builder and this actual orchestration boundary with sentinels.

The isolation is an application data boundary, not a claim that a model cannot follow injected
text. Even if it does, the host accepts only bounded structured input data. It cannot change
permissions, candidate files, oracle or formal tests. Model claims and rationale are not evidence.

## Data, oracle and limits

Only billing-v1.round-half-up is accepted: decimal amounts become integer cents, nearest rounding,
with ties away from zero for either sign. `reference_cents` uses integer digits independently of
the candidate Decimal implementation. Current supported challenge subset is an optional ASCII sign,
1–10 integer digits and optional 1–8 fractional digits. Unsupported formatting is not a new business
failure. No scientific notation, NaN or Infinity. At most four challenges, strict JSON envelope,
6000-character parsed response cap, reason up to 300 characters. Extra expected/script fields,
untrusted requirement IDs, invalid amounts and duplicate strings are rejected before execution.
The trusted harness embeds only validated amount/ID/oracle JSON, not model reasons or scripts.

Each adversarial completion uses at most 768 output tokens. Reuses Vultr client timeout 30 seconds,
maximum two attempts (only the client's existing limited retry policy); one completion per stage.
The existing Runner keeps its 3-second container deadline and all resource/security restrictions.
No extra dependencies or new arbitrary execution endpoint were added. No secrets are passed as
container environment or volumes. Docker control stays exclusively with the host runner process.

## Modes and UI

Local API execution mode and adversarial mode are separate selectors. Off preserves formal-only
behavior. Offline uses deterministic model responses (including invalid/timeout/failure presets),
but public, protected acceptance and valid challenge execution are real Docker operations.
Live reuses Vultr credentials/model configuration and explicit TRUSTBOUND_ENABLE_LIVE=1 opt-in.
Missing configuration is UNAVAILABLE, not a successful live call. No paid fallback is used.
The Vue Evidence Panel adds an Adversarial tab, counts, per-input validity, expected/observed values,
source labels, real sandbox stdout/stderr and formal-to-overall decision. Report identity and
complete evidence are checked before display. Reload starts idle; no persisted RUNNING state.

## Experiments and reproducibility

Run API with `.\.venv\Scripts\python.exe -B -m uvicorn trustbound.api:app --host 127.0.0.1 --port 8000 --workers 1`.
In frontend run `npm run dev`. Docker Desktop must be running with the existing Python image.
Run `.\.venv\Scripts\python.exe -B scripts/check_adversarial_integration.py` against the Vite proxy.
Raw captured HTTP snapshots are archived in `docs/adversarial-integration-results.json`.
Use `scripts/check_web_integration.py --port 5173` for the six Stage 1 regression scenarios.
Unit tests with injected model/execution doubles are separate from these real-container experiments.

The double_rounding fixture performs a premature four-decimal quantization. It is accepted by the
existing AST and all existing formal tests, without changing them, yet returns 101 for 1.00499
(reference 100) and -101 for -1.00499 (reference -100). It demonstrates the coverage gap with a
reviewed fixed artifact, not arbitrary user code. Offline standard proposes these two inputs plus
NaN and an untrusted bankers-rounding property; the latter two never execute.

## Guarantees, limitations and next interface

Bounded challenges are additional evidence, not a proof of correctness or broad security audit.
Live model success, adversarial prompt robustness and real Vultr cost remain unverified without
credentials. Failure/timeout coverage currently injects model transport errors; Docker remains real.
The current local single-worker API is not a public arbitrary-code service; it has no user auth,
durable scheduler or host-crash recovery. No sandbox restriction was relaxed for this stage.

A future bounded recovery request could contain task_id, parent formal_report_id, artifact_hash,
confirmed challenge IDs with trusted expected/observed evidence, and a host-controlled remaining
attempt count (initially one). The executor would receive only this structured evidence, generate
one new candidate, then repeat unchanged permissions, formal acceptance and fresh adversarial
validation. This is an interface suggestion only: no recovery loop or automatic repair exists here.
