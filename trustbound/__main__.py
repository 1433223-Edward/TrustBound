"""CLI for fixed Day 1 experiments; no shell or arbitrary code arguments."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .service import CANDIDATES, ROOT, TASK, run_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=[*CANDIDATES, "all"])
    args = parser.parse_args()
    reports = [run_task(TASK.task_id, candidate).to_dict()
               for candidate in (CANDIDATES if args.candidate == "all" else [args.candidate])]
    directory = ROOT / "artifacts" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                                     + "-" + reports[0]["run_id"][:8])
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "reports.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    for report in reports:
        print(f"{report['candidate_id']}: {report['status']}")
    print(f"Report: {directory / 'reports.json'}")
    expected = {"original": "FAILED", "fixed": "VERIFIED", "public_only": "FAILED",
                "timeout": "FAILED", "unauthorized": "REJECTED", "double_rounding": "VERIFIED"}
    if any(item["status"] != expected[item["candidate_id"]] for item in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
