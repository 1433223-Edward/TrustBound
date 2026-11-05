"""Stage 4 local regression: offline proposals and real Docker, no paid requests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trustbound.web_tasks import execute_web_run

records = []
for name, mode, candidate, recovery, expected in [
    ("executor", "offline_executor", "fixed", "off", "VERIFIED"),
    ("L3", "fixture", "double_rounding", "off", "FAILED"),
    ("L4", "fixture", "double_rounding", "offline", "VERIFIED"),
]:
    result = execute_web_run("billing-rounding-01", mode, candidate, "offline", recovery_mode=recovery)
    records.append({"experiment": name, "result": result})
    (ROOT / "artifacts/stage4-offline-results.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    verdict = (result.get("recovery_report") or {}).get("final_status") or result["final_decision"]["status"]
    assert verdict == expected
    assert result["inference_usage"]["live_request_count"] == 0
    assert result["inference_usage"]["request_count"] <= 14
    print(name, verdict, "offline requests", result["inference_usage"]["request_count"], flush=True)
