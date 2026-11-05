# Gate B preflight — awaiting paid-call authorization

No real generation request was sent during this preparation.
Git worktree already contained Stage 1–4 uncommitted changes; they were preserved.
Stage 3 still uses a host-bounded loop with at most two recoveries, but Gate B never invokes it.

Executor previously made a smoke call before proposal and used 1024 output tokens. Added explicit
smoke_check/proposal_tokens options; defaults preserve existing behavior. Inference client has an
explicit output_limit option capped at 2048; default remains 1024. scripts/check_gate_b.py uses
model deepseek-v4.1-flash-1017, smoke_check=False, proposal_tokens=2048, client timeout60,
max_attempts=1, task max_requests=1 and reserved output cap2048. No model switching.
The timeout is the existing urllib network timeout, not a 60-second bound on catalog retrieval,
model generation plus Docker combined, nor a new strict wall-clock streaming watchdog.

Only the existing run_executor -> parse_proposal -> validate_billing_code -> service.verify_patch
-> Permission Gate -> original Docker Runner/public tests -> protected independent acceptance
path executes. There is no fixture replacement, adversarial call or recovery. Invalid JSON,
truncation, model mismatch, timeout or API error stops the flow. Reports keep model call metadata,
parsed proposal, candidate hash, diff, separate public/acceptance executions and verdict.
A parsed proposal, successful Docker termination and passing acceptance are separate observations.

Default script invocation only prints nonsecret configuration. Only after explicit user approval:
.\.venv\Scripts\python.exe -B scripts/check_gate_b.py --allow-paid-inference
The report uses a new UUID under artifacts/gate-b-*.json. No live result exists yet.

Expected price uses the previously read official catalog: input $0.15 / 1M tokens,
output $0.60 / 1M tokens. Max output component $0.0012288 plus actual input cost;
unknown usage remains unknown and estimates are not invoices.
