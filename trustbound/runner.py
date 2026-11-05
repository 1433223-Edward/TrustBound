"""Trusted controller for fixed Python tests in disposable Linux containers."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from .contracts import ExecutionResult


IMAGE = "python@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def docker(*arguments, timeout=30):
    executable = shutil.which("docker")
    if not executable and os.name == "nt":
        executable = str(Path(os.environ["LOCALAPPDATA"])
                         / "Programs/DockerDesktop/resources/bin/docker.exe")
    if not executable:
        raise RuntimeError("Docker CLI not found")
    return subprocess.run([executable, *arguments], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def checked(*arguments):
    result = docker(*arguments)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def _execute_fixed_tests(code: bytes, tests: bytes, phase: str, timeout_seconds: int, *, work_root=None):
    """Internal primitive: only the fixed-task service selects payloads and tests.

    The host stages exactly two files, never executes them, and mounts only that
    temporary directory read-only. Independent verification calls this again with
    a fresh workspace and a new container; no executor outputs are trusted as tests.
    """
    name = "trustbound-" + uuid.uuid4().hex
    state, stdout, stderr, reason, error = {}, "", "", None, None
    status, cleanup, limits_verified = "ERROR", False, False
    with tempfile.TemporaryDirectory(prefix="trustbound-", dir=work_root) as directory:
        workspace = Path(directory)
        (workspace / "billing.py").write_bytes(code)
        (workspace / "checks.py").write_bytes(tests)
        if work_root is not None:
            # The host-only parent stays private. The mapped container UID can
            # traverse and read just the directory exposed by the bind mount.
            for filename in ("billing.py", "checks.py"):
                (workspace / filename).chmod(0o444)
            workspace.chmod(0o755)
        try:
            checked(
                "create", "--pull", "never", "--name", name,
                "--network", "none", "--read-only", "--user", "65534:65534",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--memory", "128m", "--memory-swap", "128m", "--cpus", "0.5",
                "--pids-limit", "32", "--log-driver", "local",
                "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
                "--mount", f"type=bind,src={workspace},dst=/work,readonly",
                IMAGE, "python", "-I", "-B", "-u", "/work/checks.py",
            )
            inspected = json.loads(checked("inspect", name))[0]
            host, mounts = inspected["HostConfig"], inspected["Mounts"]
            limits_verified = (
                host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
                and inspected["Config"]["User"] == "65534:65534"
                and host["CapDrop"] == ["ALL"]
                and "no-new-privileges" in host["SecurityOpt"]
                and host["Memory"] == host["MemorySwap"] == 134217728
                and host["NanoCpus"] == 500000000 and host["PidsLimit"] == 32
                and len(mounts) == 1 and mounts[0]["Destination"] == "/work"
                and not mounts[0]["RW"] and mounts[0]["Type"] == "bind"
                and not host["Privileged"]
            )
            if not limits_verified:
                raise RuntimeError("Sandbox configuration did not match trusted policy")
            checked("start", name)
            try:
                waited = docker("wait", name, timeout=timeout_seconds)
                if waited.returncode:
                    raise RuntimeError(waited.stderr)
                status = "EXITED"
            except subprocess.TimeoutExpired:
                status = "TIMED_OUT"
                reason = f"Host deadline exceeded: {timeout_seconds} seconds after start"
                checked("kill", name)
            state = json.loads(checked("inspect", name, "--format", "{{json .State}}"))
            logs = docker("logs", name)
            if logs.returncode:
                raise RuntimeError(logs.stderr)
            stdout, stderr = logs.stdout, logs.stderr
        except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            status, error = "ERROR", str(exc)
        finally:
            # A controller failure must not skip removal or become a success result.
            try:
                removed = docker("rm", "-f", name)
                remaining = docker("ps", "-a", "--filter", f"name=^/{name}$", "-q")
                cleanup = (removed.returncode == 0 and remaining.returncode == 0
                           and not remaining.stdout.strip())
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                error = f"{error or ''} Cleanup error: {exc}"
        unchanged = ((workspace / "billing.py").read_bytes() == code
                     and (workspace / "checks.py").read_bytes() == tests)
    return ExecutionResult(
        phase, name, IMAGE, sha256(code), sha256(tests), status,
        state.get("ExitCode"), stdout, stderr, reason, cleanup, unchanged,
        limits_verified, error,
    )
