"""Bounded local IPC for the deployed Web process and its sandbox worker."""
from dataclasses import fields
import json
import os
import socket
import struct
import time

from .contracts import ExecutionResult
from .runner import IMAGE, sha256


TASK_ID = "billing-rounding-01"
MAX_REQUEST = 64 * 1024
MAX_RESPONSE = 512 * 1024
MAX_CANDIDATE_BYTES = 32_000
MAX_OUTPUT_CHARS = 32_768
REQUEST_DEADLINE = 250


def _read_exact(connection, size, deadline):
    data = bytearray()
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("IPC read deadline")
        connection.settimeout(remaining)
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise ValueError("Incomplete IPC frame")
        data.extend(chunk)
    return data


def read_message(connection, limit, seconds):
    deadline = time.monotonic() + seconds
    size, = struct.unpack("!I", _read_exact(connection, 4, deadline))
    if not 0 < size <= limit:
        raise ValueError("IPC frame exceeds size limit")
    return json.loads(_read_exact(connection, size, deadline))


def write_message(connection, payload, limit, seconds):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(data) > limit:
        raise ValueError("IPC frame exceeds size limit")
    connection.settimeout(seconds)
    connection.sendall(struct.pack("!I", len(data)) + data)


def worker_enabled():
    return "TRUSTBOUND_RUNNER_SOCKET" in os.environ


def _connect(path):
    if not hasattr(socket, "AF_UNIX"):
        raise OSError("Unix sockets are unavailable")
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.settimeout(3)
        connection.connect(path)
    except OSError:
        connection.close()
        raise
    return connection


def run_through_worker(code, tests, phase, *, cases=None):
    """Bind evidence to the exact bytes the Web verifier expected."""
    artifact_hash, test_hash = sha256(code), sha256(tests)
    request = {"task_id": TASK_ID, "phase": phase, "candidate": code.decode("utf-8"),
               "candidate_sha256": artifact_hash}
    if cases is not None:
        request["cases"] = cases
    try:
        with _connect(os.environ["TRUSTBOUND_RUNNER_SOCKET"]) as connection:
            write_message(connection, request, MAX_REQUEST, 3)
            reply = read_message(connection, MAX_RESPONSE, REQUEST_DEADLINE)
        if (type(reply) is not dict or set(reply) != {field.name for field in fields(ExecutionResult)}
                or (reply["phase"], reply["image"], reply["artifact_hash"], reply["test_hash"])
                != (phase, IMAGE, artifact_hash, test_hash)
                or any(type(reply[key]) is not bool for key in
                       ("cleanup_confirmed", "workspace_unchanged", "limits_verified"))
                or (reply["exit_code"] is not None and type(reply["exit_code"]) is not int)
                or any(type(reply[key]) is not str for key in ("container_name", "stdout", "stderr"))
                or any(reply[key] is not None and type(reply[key]) is not str
                       for key in ("timeout_reason", "error"))):
            raise ValueError("Invalid or mismatched execution evidence")
        return ExecutionResult(**reply)
    except (OSError, ValueError, TypeError, RecursionError):
        # Never fall back to local Docker, and never expose socket paths or OS errors.
        return ExecutionResult(phase, "", IMAGE, artifact_hash, test_hash, "ERROR", None,
                               "", "", None, False, False, False, "RUNNER_IPC_EVIDENCE_UNAVAILABLE")
