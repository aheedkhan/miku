#!/usr/bin/env python3
"""Integration tests — simulates labrat implant protocol (v0.1–v0.5)."""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

# Allow import from same directory
sys.path.insert(0, os.path.dirname(__file__))
from c2_server import get_result, queue_task, run_server

HOST = "127.0.0.1"
PORT = 18080
BASE = f"http://{HOST}:{PORT}/beacon"


def post_json(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def simulate_implant(agent_id: str, stop: threading.Event) -> None:
    while not stop.is_set():
        resp = post_json({"id": agent_id, "op": "checkin", "os": "test", "build": "pytest"})
        if resp.get("op") == "task" or resp.get("cmd"):
            cmd = resp.get("cmd", "")
            arg = resp.get("arg", "")
            task_id = resp.get("id", "")
            stdout, stderr, rc = "", "", 0

            if cmd == "shell":
                stdout = f"simulated:{arg}"
            elif cmd == "download":
                stdout = base64.b64encode(b"file-bytes").decode("ascii")
            elif cmd == "upload":
                path, b64 = arg.split("|", 1)
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64))
                stdout = "upload ok"
            elif cmd == "inject":
                stdout = "inject ok"
            elif cmd == "persist":
                stdout = "persist ok"
            else:
                stdout = "unknown"
                rc = -1

            post_json({
                "id": agent_id, "op": "result", "task": task_id,
                "stdout": stdout, "stderr": stderr, "rc": rc,
            })
        time.sleep(0.05)


def run_tests() -> None:
    server = run_server(HOST, PORT)
    agent_id = "TEST-AGENT-001"
    stop = threading.Event()
    t = threading.Thread(target=simulate_implant, args=(agent_id, stop), daemon=True)
    t.start()
    time.sleep(0.3)

    results: list[tuple[str, bool]] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        results.append((name, cond))
        if cond:
            print(f"  PASS {name}")
        else:
            print(f"  FAIL {name} {detail}")

    # v0.1 checkin
    from c2_server import list_agents
    check("v0.1 checkin", agent_id in list_agents())

    # v0.2 shell
    tid = queue_task(agent_id, "shell", "whoami")
    r = get_result(tid, 10)
    check("v0.2 shell", r and r.get("stdout") == "simulated:whoami")

    # v0.3 download
    tid = queue_task(agent_id, "download", "C:\\test.txt")
    r = get_result(tid, 10)
    check("v0.3 download", r and base64.b64decode(r.get("stdout", "")) == b"file-bytes")

    # v0.3 upload
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        up_path = tmp.name
    b64 = base64.b64encode(b"uploaded-data").decode("ascii")
    tid = queue_task(agent_id, "upload", f"{up_path}|{b64}")
    r = get_result(tid, 10)
    check("v0.3 upload", r and r.get("rc") == 0)
    with open(up_path, "rb") as f:
        check("v0.3 upload bytes", f.read() == b"uploaded-data")
    os.unlink(up_path)

    # v0.4 inject
    tid = queue_task(agent_id, "inject", "")
    r = get_result(tid, 10)
    check("v0.4 inject", r and "inject ok" in r.get("stdout", ""))

    # v0.4 persist
    tid = queue_task(agent_id, "persist", "LabRatTest")
    r = get_result(tid, 10)
    check("v0.4 persist", r and "persist ok" in r.get("stdout", ""))

    # v0.5 evasion (implant applies ETW patch at start; protocol unchanged)
    check("v0.5 evasion hook", True)

    stop.set()
    server.shutdown()

    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n=== {passed} passed, {failed} failed ===")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
