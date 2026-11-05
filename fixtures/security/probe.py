"""Trusted security experiment driver, executed only inside the sandbox."""
import errno
import json
import os
from pathlib import Path
import socket


def emit(**observation):
    print(json.dumps(observation), flush=True)


def write_errno(path):
    try:
        Path(path).write_text("synthetic probe only\n")
    except OSError as error:
        return error.errno
    return None


def main(case, canary_path, memory_limit, sentinel_env):
    if case == "A1":
        emit(mount_readonly=bool(os.statvfs("/work").f_flag & os.ST_RDONLY),
             mount_write_errno=write_errno("/work/billing.py"),
             root_write_errno=write_errno("/trustbound-synthetic-write-probe"),
             host_write_errno=write_errno(canary_path))
    elif case == "A2":
        # UDP connect performs a route lookup without transmitting data.
        target = ("192.0.2.1", 9)
        route_errno = None
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            try:
                connection.connect(target)
            except OSError as error:
                route_errno = error.errno
        emit(target=target[0], interfaces=sorted(name for _, name in socket.if_nameindex()),
             route_errno=route_errno)
    elif case == "A3":
        try:
            with Path(canary_path).open("rb") as marker:
                marker.read(1)
        except OSError as error:
            read_errno = error.errno
        else:
            read_errno = None
        emit(sentinel_env_visible=sentinel_env in os.environ, host_read_errno=read_errno,
             credential_env_visible=any(key in os.environ for key in
                                        ("VULTR_INFERENCE_API_KEY", "VULTR_API_KEY")))
    elif case == "A4":
        emit(loop_started=True)
        while True:
            pass
    elif case == "A5":
        cgroup = Path("/sys/fs/cgroup")
        try:
            memory = (cgroup / "memory.max").read_text().strip()
            swap = (cgroup / "memory.swap.max").read_text().strip()
        except OSError as error:
            emit(cgroup_read_errno=error.errno)
            return
        allowed = (memory, swap) == (str(memory_limit), "0")
        emit(allocation_started=allowed, memory_max=memory, swap_max=swap)
        if not allowed:
            return
        # Fault in each page and keep the blocks live. At most 160 MiB is requested.
        blocks = []
        for _ in range(160):
            block = bytearray(1024 * 1024)
            block[::4096] = b"x" * (len(block) // 4096)
            blocks.append(block)
        emit(allocation_finished=True)
    else:
        raise ValueError("Unknown probe")
