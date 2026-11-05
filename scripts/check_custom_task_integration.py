"""Private VM checks for Custom Task v1 using the real Runner and no model."""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener


BASE = "http://127.0.0.1:8000/api"
SOURCE = "def solve(value):\n    return value\n"
FIX = "def solve(value):\n    return -value if value < 0 else value\n"
TASK = {"source": SOURCE, "requirements": "Return the absolute value of an integer.",
        "public": [{"input": 2, "expected": 2}], "acceptance": [{"input": -3, "expected": 3}],
        "challenges": [{"input": -9, "expected": 9}]}


def main():
    opener = build_opener(ProxyHandler({}))

    def http(path, payload=None):
        request = Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"})
        with opener.open(request, timeout=5) as response:
            return json.load(response)

    health = http("/health")
    assert health["custom_task"]["enabled"] and not health["modes"]["live_executor"]["enabled"]
    cases = (("fixed", {"replacement": FIX}, "VERIFIED", "VERIFIED"),
             ("original", {}, "FAILED", "FAILED"),
             ("counterexample", {"replacement": "def solve(value):\n    return 3 if value == -3 else value\n"},
              "VERIFIED", "FAILED"),
             ("no-acceptance", {"replacement": FIX, "acceptance": []}, "INCONCLUSIVE", "INCONCLUSIVE"),
             ("unsafe", {"replacement": "import os\n" + SOURCE}, "REJECTED", "REJECTED"))
    for label, changes, formal, final in cases:
        run_id = http("/custom-runs", dict(TASK, **changes))["run_id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            record = http("/custom-runs/" + run_id)
            if record["state"] in {"COMPLETED", "ERROR"}:
                break
            time.sleep(.4)
        else:
            raise AssertionError(f"{label}: still running; run_id={run_id}")
        assert record["state"] == "COMPLETED", record
        assert record["llm_source"] == "NONE"
        report, evidence = record["verification"], record["custom_evidence"]
        assert (report["status"], record["final_decision"]["status"]) == (formal, final), record
        executions = report["executions"] + ([evidence["challenge_execution"]] if evidence["challenge_execution"] else [])
        if label == "unsafe":
            assert not executions
        else:
            assert executions and len({row["container_name"] for row in executions}) == len(executions)
            assert all(row["cleanup_confirmed"] and row["workspace_unchanged"] and row["limits_verified"]
                       and row["artifact_hash"] == report["artifact_hash"] for row in executions)
        print(f"{label}: formal={formal} final={final} containers={len(executions)} run_id={run_id}", flush=True)

    try:
        http("/custom-runs", dict(TASK, command="docker run"))
    except HTTPError as error:
        assert error.code == 422
        print("command override: rejected (422)")
    else:
        raise AssertionError("Unexpected acceptance of arbitrary command")


if __name__ == "__main__":
    main()
