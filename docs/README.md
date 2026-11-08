# TrustBound documentation index

Start with the root [README](../README.md) for the current product position and capability boundary.

## Current operational references

- [Deployment and operations guide](TrustBound_Deployment_Operations_Guide_2026-11-08.md): public/offline and private/live profiles, environment files, systemd operation, release activation, rollback, backups, and limits of the available VM evidence.
- [Verification modes](VERIFICATION_MODES.md): functional versus security-only execution. Security-only success is `EXECUTED_UNVERIFIED`, not business verification.
- [Local Workspace flow](WORKSPACE_LOCAL_FLOW.md): local developer preview and how to explicitly keep it offline.

## Historical records and experiments

These documents retain original evidence, designs, and stage decisions. They are not descriptions of the current release unless the current references say so.

- [Experiments](EXPERIMENTS.md)
- [Workspace vision, 2026-11-06](TRUSTBOUND_WORKSPACE_VISION_2026-11-06.md)
- [Billing Web API contract](WEB_API_CONTRACT.md)
- [Adversarial verification](ADVERSARIAL_VERIFICATION.md)
- [Recovery reliability](RECOVERY_RELIABILITY.md)
- `GATE_*`, `STAGE4_LIVE_INFERENCE.md`, `SECURITY_ATTACK_SUITE.md`, `BOUNDED_RECOVERY.md`, and `CUSTOM_TASK_V1.md` preserve stage-specific evidence and proposals.

## Deployment-stage records

Deployment documents in [`deploy/`](../deploy/) retain Stage 5A–5C records and Runner installation material. Consult the deployment operations guide first when operating the current two-profile layout.
