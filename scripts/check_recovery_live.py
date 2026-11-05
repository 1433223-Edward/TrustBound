"""Opt-in paid recovery experiment. Default invocation only checks configuration presence."""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trustbound.web_tasks import execute_web_run, live_availability


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-paid-inference", action="store_true",
                        help="Explicitly authorize up to two recovery proposals (1024 output tokens each, client retry cap two).")
    args = parser.parse_args()
    configured = live_availability()
    permitted = os.environ.get("TRUSTBOUND_ENABLE_RECOVERY_LIVE") == "1"
    print(json.dumps({"configuration": configured, "recovery_opt_in": permitted,
                      "recovery_attempt_limit": 2, "output_tokens_per_completion": 1024,
                      "timeout_seconds": 30, "client_attempt_limit": 2,
                      "adversarial_model": "OFFLINE_TEST", "paid_request_authorized": args.allow_paid_inference}))
    if not args.allow_paid_inference:
        print("Configuration-only check; no Docker or model requests made.")
        return
    if not configured["enabled"] or not permitted:
        raise SystemExit("Missing live configuration or separate recovery opt-in; no inference requested.")
    run_id = uuid.uuid4().hex
    outcome = execute_web_run("billing-rounding-01", "fixture", "double_rounding", "offline",
                              recovery_mode="live", run_id=run_id)
    directory = ROOT / "artifacts" / ("recovery-live-" + run_id)
    directory.mkdir(parents=True)
    output = directory / "report.json"
    output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Recovery result:", outcome["recovery_report"]["final_status"], "Evidence:", output)


if __name__ == "__main__":
    main()
