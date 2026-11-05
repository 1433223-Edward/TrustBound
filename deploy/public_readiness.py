"""Fail-closed public-execution gate for the current in-process Docker architecture."""
import json
import sys

BLOCKERS = [
    "Web process directly controls Docker; isolated runner boundary not implemented",
    "No persistent global task/spend quotas or public request-rate limiter",
    "Ubuntu staging permissions and rootless cgroup/UID behavior unverified",
    "Crash recovery, evidence retention and deployment Host/Origin policy incomplete",
]
print(json.dumps({"public_execution_ready": False, "blockers": BLOCKERS}, indent=2))
sys.exit(2)
