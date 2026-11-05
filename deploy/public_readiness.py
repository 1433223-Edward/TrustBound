"""Fail-closed gate while public execution requirements remain incomplete."""
import json
import sys

BLOCKERS = [
    "The private runner deployment requires VM-level end-to-end acceptance",
    "No persistent global task/spend quotas or public request-rate limiter",
    "Ubuntu staging permissions and rootless cgroup/UID behavior unverified",
    "Crash recovery, evidence retention and deployment Host/Origin policy incomplete",
]
print(json.dumps({"public_execution_ready": False, "blockers": BLOCKERS}, indent=2))
sys.exit(2)
