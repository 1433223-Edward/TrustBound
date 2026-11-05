# Gate C preflight — awaiting explicit paid-request approval

No generation request sent. Existing dirty worktree and earlier reports preserved.
Model deepseek-v4.1-flash-1017; one generation request; max_completion_tokens2048;
client network timeout60; max_attempts1; task budget one request and 2048 reserved output tokens.
No Executor generation or Recovery. Up to four structured amount/requirement/reason proposals.

Audit found the existing system template included 1.00499, an already-known counterexample.
Replaced that format example with neutral 0.00 and added a context regression guard. No known
failure inputs, expected outputs, Executor history or acceptance implementation enter the prompt.
Candidate bytes are unchanged, including the original descriptive docstring; this is code review
with source clues, not blind bug discovery. Existing historical results were not rewritten.

Added an optional completion_tokens parameter to run_adversarial (default remains768), actual
request budget metadata in AdversarialReport and scripts/check_gate_c.py. The default invocation
only checks configuration/context and does not execute Docker or inference. After approval,
re-run formal acceptance first; if VERIFIED and hash matches, generate live proposals once,
validate input/rule, derive trusted oracle values and execute valid data in a new existing Runner
sandbox. Only observed mismatches downgrade VERIFIED. No valid inputs is incomplete, not failure;
no confirmed mismatch is bounded evidence only, not proof of universal correctness.
The existing parser's 6000-character response cap still applies; oversized JSON is rejected.

Expected catalog pricing: $0.15 / million input tokens and $0.60 / million output tokens.
Output component <=$0.0012288; input depends on actual token usage. Estimates are not invoices.
Timeout/failed provider responses may leave usage and billing unknown. No retries or substitutions.
Raw records use a fresh artifacts/gate-c-UUID.json and preserve actual proposals and evidence.
Gate D remains separately authorized; a minimal future test would repair a candidate with confirmed
failure evidence once, then repeat permission/public/independent/adversarial verification.
