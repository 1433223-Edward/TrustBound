# Gate D final independent review — awaiting paid-request authorization

Parent Gate D report gate-d-31e9eb19bc60432fac260d96b6a092aa.json remains unchanged.
Recovered artifact69226f0e9244d6dfedde7d8c2a9a5f3a1e5091b1f569ebe5053bc9817d088eb8
matches code bytes and formal/public/acceptance/replay evidence. Parent replay observations agree with
host oracle. Known inputs, answers, executor/recovery messages and history are not sent to the model.
Only build_context allowlisted task_id/requirement_id/requirement/artifact_hash/candidate are supplied.

Prepared check_gate_d_final.py defaults to local evidence/configuration checks only. No model or Docker
request was made during preflight. After approval it invokes the existing run_adversarial compact mode:
model deepseek-v4.1-flash-1017, one POST, max_completion_tokens4096, reasoning.max_tokens1024,
strict JSON schema with1..3 candidates, timeout60, max_attempts1. No recovery or alternate model.
Prior provider observation slightly exceeded reasoning1024; do not claim an exact hard thinking bound.
Capability must still be advertised at request time; unsupported controls abort before generation.

Valid proposed inputs run in a fresh original restricted Docker Runner. Formal/replay evidence is retained
separately with the new independent report and candidate hash in a new UUID report; no old report rewritten.
VERIFIED requires intact matching prior formal and replay evidence plus complete new adversarial execution
with at least one valid observed test and no confirmed mismatch. Confirmed mismatch gives FAILED;
invalid-only proposals, truncation, API error or missing execution gives INCONCLUSIVE. No fixed input fill-in.

Output cost component <=$0.0024576 plus input at previously read catalog $0.15/million tokens;
completion price $0.60/million already includes thinking. Actual usage/estimate will be recorded, not invoice.
86 backend tests pass, including parent-code mismatch, cleanup failure and corrupted observations.
Stage 4 recovery evidence closure is pending this live result. Broader Web live-report demonstration and
any deployment remain separate acceptance activities; no cloud resources or Git Push.
