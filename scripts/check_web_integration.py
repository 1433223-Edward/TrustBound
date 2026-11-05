"""Exercise real HTTP -> task service -> Docker; never mock business evidence."""
import argparse
import json
from pathlib import Path
import time
from urllib import error, request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, choices=[8000, 5173], default=5173)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}/api"

    def http(path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        # Local integration must not traverse a configured external HTTP proxy.
        with request.build_opener(request.ProxyHandler({})).open(req, timeout=10) as response:
            return json.load(response)

    tasks = http("/tasks")["tasks"]
    task_id = tasks[0]["spec"]["task_id"]
    assert http("/tasks/" + task_id) == tasks[0]
    expected = {"original": "FAILED", "fixed": "VERIFIED", "public_only": "FAILED",
                "unauthorized": "REJECTED", "timeout": "FAILED"}
    snapshots = []
    cases = [("fixture", candidate) for candidate in expected] + [("offline_executor", "fixed")]
    for mode, candidate in cases:
        body = {"task_id": task_id, "mode": mode, "candidate_id": candidate}
        accepted = http("/runs", body)
        deadline = time.monotonic() + 120
        saw_active_health = False
        while time.monotonic() < deadline:
            snapshot = http("/runs/" + accepted["run_id"])
            health = http("/health")
            assert health["status"] == "ok"
            saw_active_health |= health["active_run_id"] == accepted["run_id"]
            if snapshot["state"] in ("COMPLETED", "ERROR"):
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Real HTTP run exceeded integration deadline")
        snapshots.append(snapshot)
        # Save real evidence even if an assertion later fails.
        output = Path(__file__).resolve().parents[1] / "artifacts/web-integration-results.json"
        output.write_text(json.dumps(snapshots, indent=2, ensure_ascii=False), encoding="utf-8")
        assert snapshot["state"] == "COMPLETED", snapshot["error"]
        report = snapshot["verification"]
        assert report["status"] == expected[candidate]
        assert all(e["cleanup_confirmed"] and e["workspace_unchanged"] and e["limits_verified"] for e in report["executions"])
        if candidate == "public_only":
            assert [e["exit_code"] for e in report["executions"]] == [0, 1]
        if candidate == "timeout":
            assert report["executions"][0]["status"] == "TIMED_OUT"
            assert report["executions"][0]["exit_code"] == 137
            assert saw_active_health
        if candidate == "unauthorized":
            assert report["executions"] == []
        assert snapshot["llm_source"] == ("OFFLINE_TEST" if mode == "offline_executor" else "NONE")
        print(f"{mode}/{candidate}: {report['status']} · actual executions={len(report['executions'])}", flush=True)
    if http('/health')['modes']['live_executor']['enabled']:
        print('live_executor configured: not invoked by this offline integration test')
        print(f"Evidence: {output}")
        return
    try:
        http("/runs", {"task_id": task_id, "mode": "live_executor"})
    except error.HTTPError as exc:
        assert exc.code == 503
        print("live_executor: unavailable (503); no paid model call attempted", flush=True)
    else:
        raise AssertionError("Expected unconfigured Vultr to be unavailable; stop and inspect environment")
    print(f"Evidence: {output}")


if __name__ == "__main__":
    main()
