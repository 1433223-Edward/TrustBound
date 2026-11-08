# Workspace verification modes

Settings -> Agent workflow -> Code Correctness Verification defaults to **OFF** for new browser preferences. Existing browser preferences and old run requests without an explicit value are interpreted as functional verification for compatibility. This preference affects new Workspace runs; fixed Billing evaluations, Demo Replay evidence and system regression/security tests do not consult the browser preference.

## FUNCTIONAL (default)

The approved write scope, protected public/independent acceptance and approved challenge cases retain their existing behavior. VERIFIED remains a functional acceptance verdict for this declared scope. Frozen acceptance criteria cannot be changed by Executor, Adversarial or Recovery.

## SECURITY_ONLY

The user approves one bounded JSON execution input. The same fixed Python entry driver runs once in the same Runner, with unchanged network isolation, read-only root, container user, memory/CPU/PID/time limits and cleanup. Scope, candidate hash, driver/input hash, image and execution evidence are checked. No expected business output is compared and no public, independent acceptance or adversarial business test runs.

A successful intact execution is EXECUTED_UNVERIFIED, never VERIFIED. A program exception/unsuccessful run is EXECUTION_FAILED; missing or inconsistent security evidence is INCONCLUSIVE. Security Evidence confirms the declared sandbox controls and evidence integrity, not universal absence of software vulnerabilities.

Adversarial analysis is configured independently. It may propose inputs under the approved reference rules, but those suggestions are not confirmed counterexamples when functional verification is disabled. Business Recovery is unavailable for security-only results, including execution failures.

A plan approved only for security execution may omit business cases and trusted expected results. Enabling functional verification on it requires updating and approving functional acceptance first. Turning functional tests off on an already fully approved plan preserves its frozen criteria without executing them. Restoring tests later uses the original approved criteria.

Evidence reports separately contain security_evidence and functional_verification. Both queued run metadata and completed reports record verification_mode (FUNCTIONAL or SECURITY_ONLY). Existing timestamps, inference usage and execution records remain available for cost/performance ablations. Changing modes changes task request identity; unchanged default requests preserve legacy idempotency fingerprints.

No new database tables, host-file writeback, Git rollback or deployed Runner privilege changes are required.
