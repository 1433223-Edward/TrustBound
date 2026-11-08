# TrustBound handbook

TrustBound is a secure AI development workspace for developers who want agents to propose changes and need evidence they can inspect. An agent can act, but cannot certify its own success.

> VERIFIED applies to the declared acceptance scope. User feedback, regression tests and evaluations can improve coverage over time.

## Why verification is independent

A convincing patch can miss an edge case. In the Billing experiment, the double-rounding candidate passed public and formal tests. Independent adversarial checks found inputs that violated the trusted business rule. TrustBound separates the proposal, permissions, execution and verdict so each can be inspected.

## System architecture

```text
User goal → Agent proposal → Permission Gate → Isolated Runner
                                                      ↓
Evidence Report ← Trusted Verifier ← Actual Sandbox observation
```

- The Executor proposes a structured change. The host checks writable paths and source policy before starting a container.
- FastAPI handles admission and orchestration. The deployed runner accepts allowlisted messages over a Unix socket. A separate account owns Rootless Docker.
- The runner uses a fixed image, an unprivileged container user, no network, a read-only root filesystem and CPU, memory and process limits. Public and independent checks run separately.
- Evidence records candidate and test hashes, exit status, logs, timeout and cleanup.

## Adversarial verification and recovery

The independent Billing adversary receives the task requirements and candidate. It proposes constrained inputs. The host computes trusted expected outputs and compares actual Docker results. A confirmed counterexample can turn a formal pass into FAILED.

Bounded Recovery is triggered by a confirmed business failure. The host caps attempts and binds failure evidence to the candidate hash. Every replacement runs through the same gates. Permission denial, insufficient evidence and infrastructure failures prevent automatic recovery.

## From prototype to Vultr

- The prototype used a fixed Billing bug and patch to verify public checks, independent acceptance, policy rejection and timeout cleanup. Vue and FastAPI then exposed that flow.
- Stage 2 separated adversarial context. Docker confirmed that input 1.00499 produced 101 cents where the trusted result was 100.
- Stage 3 added bounded recovery. Real containers covered recovery, exhausted attempts and failure paths with explicit offline proposals.
- Stage 4 connected Vultr Serverless Inference. One live response exhausted its output budget. The client rejected the truncated result and recorded INCONCLUSIVE. A later test tightened the response format and raised the limit.
- Stage 5 separated the Web service and Rootless runner on a Vultr Ubuntu VM. The HTTPS public demo uses authentication, rate limits and a persistent quota for bounded Billing execution. Live tests use separate private authorization.

## Try the workflows

- Billing Rounding is available in Demo Replay. Inspect recorded scenarios including the baseline bug, verified patch, policy rejection and timeout. The Local API tab can run controlled Billing cases on deployments that allow it.
- In the private Workspace, import a ZIP or folder, describe the goal and approve the writable files and distinct public and independent cases. Freeze the plan, run the original or an offline candidate, and inspect the evidence. Accept a verified change to export a patch or ZIP.
- Import Inventory Reconciliation to inspect stock shortages, repeated items, negative stock and atomic failure.
- Import Application Log Summary to inspect log-level parsing, malformed entries and half-open time boundaries.

## Read the evidence

| Status | Meaning |
| --- | --- |
| VERIFIED | The candidate passed declared checks with evidence bound to its identity. |
| FAILED | Trusted evidence shows a violation of the acceptance criteria. |
| REJECTED | The request violated permission or policy. |
| INCONCLUSIVE | The request, execution or evidence was insufficient for a passing verdict. |

Replay, offline proposals, live Vultr calls and real sandbox execution are labeled separately. An offline proposal may run in real Docker. A replay creates no new container.

## Safety boundaries and roadmap

Public access is limited to built-in scenarios. Private imports have ownership, size and path restrictions. Changes to frozen acceptance criteria require another user approval. Expected values and the verdict stay with the verifier. Review the source disclosure before authorizing a Vultr request.

Inventory and Log Summary passed offline acceptance with real local Docker. The next gates are manual VM checks for Rootless Docker, A1–A5 and persistent admission, followed by a separately authorized non-Billing live test. Project-level adversarial verification, recovery and Git delivery need their own implementation and acceptance. Semantic Context Reconstruction is a future plug-in outside the competition build.

## References

- README.md describes the fixed repair, Web API and agent controls.
- docs/EXPERIMENTS.md records the experiment stages and evidence sources.
- docs/GATE_C_DIAGNOSIS.md documents the truncated model response. docs/SECURITY_ATTACK_SUITE.md documents A1–A5.
- deploy/PRIVATE_RUNNER.md and deploy/STAGE5C.md document deployment and admission.
- docs/TRUSTBOUND_WORKSPACE_VISION_2026-11-06.md records product decisions and acceptance criteria.
