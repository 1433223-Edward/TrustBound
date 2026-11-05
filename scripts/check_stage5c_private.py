"""Prove the public profile's admission controls over VM loopback, before Caddy."""
import argparse
import json
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("before-restart", "after-restart"))
    parser.add_argument("domain", help="Same host name as TRUSTBOUND_PUBLIC_DOMAIN, without scheme")
    args = parser.parse_args()
    opener = build_opener(ProxyHandler({}))
    origin = f"https://{args.domain}"
    body = {"task_id": "billing-rounding-01", "mode": "fixture", "candidate_id": "fixed"}

    def call(path, payload=None, request_origin=origin):
        headers = {"Content-Type": "application/json"}
        if request_origin is not None:
            headers["Origin"] = request_origin
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request("http://127.0.0.1:8000/api" + path, data=data, headers=headers)
        try:
            with opener.open(request, timeout=5) as response:
                return response.status, json.load(response), response.headers
        except HTTPError as error:
            return error.code, json.load(error), error.headers

    def expect_denied(status, code, *, payload=body, request_origin=origin):
        actual, reply, headers = call("/runs", payload, request_origin)
        assert (actual, reply.get("error", {}).get("code")) == (status, code), (actual, reply)
        print(f"{status} {code}", flush=True)
        return headers

    def run_fixed():
        status, reply, _ = call("/runs", body)
        assert status == 202, (status, reply)
        run_id = reply["run_id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            _, record, _ = call("/runs/" + run_id)
            if record["state"] in ("COMPLETED", "ERROR"):
                break
            time.sleep(.2)
        else:
            raise AssertionError(f"Run still pending: {run_id}")
        evidence = record.get("verification") or {}
        executions = evidence.get("executions", [])
        assert (record["state"] == "COMPLETED" and evidence.get("status") == "VERIFIED"
                and record["llm_source"] == "NONE"), (run_id, evidence)
        assert len({item["container_name"] for item in executions}) == 2
        assert all(item["cleanup_confirmed"] and item["limits_verified"] for item in executions)
        print(f"VERIFIED {run_id} · 2 cleaned containers", flush=True)

    _, health, _ = call("/health")
    assert health["status"] == "ok" and health["public_demo"] and health["persistent_quota"]
    assert not health["modes"]["live_executor"]["enabled"] and not health["custom_task"]["enabled"]
    if args.stage == "after-restart":
        expect_denied(429, "RUN_QUOTA_EXHAUSTED")
        return
    expect_denied(403, "ORIGIN_DENIED", request_origin=None)
    expect_denied(403, "PUBLIC_OFFLINE_ONLY", payload={"task_id": body["task_id"], "mode": "live_executor"})
    run_fixed()
    headers = expect_denied(429, "RUN_RATE_LIMITED")
    time.sleep(int(headers["Retry-After"]) + 1)
    run_fixed()
    expect_denied(429, "RUN_QUOTA_EXHAUSTED")


if __name__ == "__main__":
    main()
