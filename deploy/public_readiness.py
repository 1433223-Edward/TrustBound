"""Fail-closed gate while public execution requirements remain incomplete."""
import json
import sys

BLOCKERS = [
    "Operator must verify the active release, persistent quota and public profile on the VM",
    "Authenticated HTTPS, route allowlist and external firewall checks require live VM evidence",
    "Validate owned-container crash recovery and the static 503 rollback on the VM",
]
print(json.dumps({"public_execution_ready": False, "blockers": BLOCKERS}, indent=2))
sys.exit(2)
