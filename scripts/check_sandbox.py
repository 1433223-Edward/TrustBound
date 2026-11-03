"""Run two fixed Docker smoke checks; never execute caller-supplied code."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


DOCKER = shutil.which("docker") or str(
    Path(os.environ["LOCALAPPDATA"])
    / "Programs/DockerDesktop/resources/bin/docker.exe"
)


def docker(*arguments, timeout=30):
    return subprocess.run(
        [DOCKER, *arguments], capture_output=True, text=True, timeout=timeout
    )


def check_case(image, code, timeout_seconds):
    """Keep lifecycle control on the host and remove only this check's container."""
    name = "trustbound-check-" + uuid.uuid4().hex
    result = {"container_name": name, "timed_out": False}
    try:
        created = docker(
            "create", "--name", name, "--network", "none",
            "--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--memory", "128m",
            "--memory-swap", "128m", "--cpus", "0.5", "--pids-limit", "32",
            image, "python", "-I", "-B", "-u", "-c", code,
        )
        if created.returncode:
            raise RuntimeError(created.stderr)
        configuration = docker("inspect", name)
        configuration.check_returncode()
        inspected = json.loads(configuration.stdout)[0]
        host = inspected["HostConfig"]
        result["limits"] = {key: host[key] for key in (
            "NetworkMode", "ReadonlyRootfs", "CapDrop", "SecurityOpt",
            "Memory", "MemorySwap", "NanoCpus", "PidsLimit",
        )}
        result["user"] = inspected["Config"]["User"]
        result["mounts"] = inspected["Mounts"]
        started = docker("start", name)
        started.check_returncode()
        try:
            waited = docker("wait", name, timeout=timeout_seconds)
            waited.check_returncode()
        except subprocess.TimeoutExpired:
            result["timed_out"] = True
            killed = docker("kill", name)
            killed.check_returncode()
        state = docker("inspect", name, "--format", "{{json .State}}")
        state.check_returncode()
        result["state"] = json.loads(state.stdout)
        logs = docker("logs", name)
        logs.check_returncode()
        result.update(stdout=logs.stdout, stderr=logs.stderr)
    finally:
        removed = docker("rm", "-f", name)
        remaining = docker("ps", "-a", "--filter", "name=^/" + name + "$", "-q")
        result["cleanup_confirmed"] = (
            removed.returncode == 0 and remaining.returncode == 0
            and not remaining.stdout.strip()
        )
    return result


def main():
    # Resolve the downloaded tag to an immutable digest before either check.
    image_result = docker("image", "inspect", "python:3.12-slim")
    image_result.check_returncode()
    image = json.loads(image_result.stdout)[0]["RepoDigests"][0]
    normal_code = """import os, socket
print('sum:', sum([1, 2, 3]))
print('uid:', os.getuid())
print('interfaces:', socket.if_nameindex())
try:
    open('/write-probe', 'w').close()
except OSError as error:
    print('root_write_errno:', error.errno)
else:
    raise RuntimeError('Root filesystem unexpectedly writable')
"""
    normal = check_case(image, normal_code, 10)
    looping = check_case(image, "print('loop_started'); exec('while True: pass')", 3)
    health = docker("info", "--format", "{{.ServerVersion}}")
    report = {"image": image, "normal": normal, "timeout": looping,
              "engine_healthy_after_timeout": health.returncode == 0}
    report_path = Path(__file__).resolve().parents[1] / "docs/environment-smoke.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    passed = (
        normal["state"]["ExitCode"] == 0 and not normal["timed_out"]
        and normal["cleanup_confirmed"] and looping["timed_out"]
        and not looping["state"]["Running"] and looping["cleanup_confirmed"]
        and report["engine_healthy_after_timeout"]
    )
    if not passed:
        raise SystemExit("Environment smoke check failed; inspect recorded evidence")


if __name__ == "__main__":
    main()
