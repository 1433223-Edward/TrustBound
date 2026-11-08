"""Private HTTP acceptance with Docker and no model requests."""
import argparse
from io import BytesIO
import json
import os
import time
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5173)
    port = parser.parse_args().port
    token = os.environ.get("TRUSTBOUND_WORKSPACE_TOKEN")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    http = build_opener(ProxyHandler({}))

    def request(path, body=None, expected=200, raw=False):
        req = Request(f"http://127.0.0.1:{port}/api/workspace/projects{path}",
                      data=None if body is None else json.dumps(body).encode(),
                      headers=headers)
        try:
            response = http.open(req, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            if response.status != expected:
                raise AssertionError(f"{path}: HTTP {response.status} (expected {expected})")
            return response.read() if raw else json.load(response)

    def run(project, mode, replacements=None):
        body = {"revision": project["revision"], "mode": mode}
        if replacements is not None:
            body["files"] = replacements
        route = f"/{project['project_id']}/runs"
        started = request(route, body, 202)
        route += "/" + started["run_id"]
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            result = request(route)
            if result["state"] not in ("QUEUED", "RUNNING"):
                assert result["state"] == "COMPLETED", result.get("error")
                report = result["workspace_report"]
                assert report["frozen_hash"] == project["frozen_hash"]
                assert report["inference_usage"] is None
                print(mode, report["status"], report["reason"], report["run_id"],
                      f"containers={len(report['cases'])}", flush=True)
                for case in report["cases"]:
                    evidence = case["execution"]
                    assert evidence["artifact_hash"] == report["artifact_hash"]
                    assert evidence["container_name"] and evidence["cleanup_confirmed"] and evidence["limits_verified"]
                return route, report
            time.sleep(0.5)
        raise AssertionError("Workspace run exceeded acceptance deadline")

    for name in ("inventory", "logs"):
        draft = request("/samples/" + name, {}, 201)
        project = request(f"/{draft['project_id']}/freeze", {"revision": draft["revision"], "confirm_acceptance": True})
        _, original = run(project, "original")
        assert original["status"] == "FAILED"
        route, fixed = run(project, "offline", draft["offline_files"])
        assert fixed["status"] == "VERIFIED" and len(fixed["cases"]) >= 4
        assert all(case["status"] == "MATCHED" for case in fixed["cases"])
        request(route + "/export/zip", expected=409)
        request(route + "/review/ACCEPTED", {})
        assert request(route + "/export/patch", raw=True).startswith(b"--- a/")
        with ZipFile(BytesIO(request(route + "/export/zip", raw=True))) as archive:
            for path, content in draft["offline_files"].items():
                assert archive.read(path).decode() == content
        if name == "inventory":
            _, forbidden = run(project, "offline", {"rules.py": "raise RuntimeError()"})
            assert forbidden["status"] == "REJECTED" and not forbidden["cases"]
            _, fake = run(project, "offline", {
                "inventory.py": 'import os\nos.write(1, b"tests passed\\n")\nos._exit(0)\n',
            })
            assert fake["status"] == "INCONCLUSIVE" and fake["reason"] == "INVALID_WORKSPACE_OBSERVATION"


if __name__ == "__main__":
    main()
