"""WhatsApp channel: the same Agent as the interactive REPL, driven by inbound messages
from the Node.js Baileys bridge (../whatsapp-bridge/) instead of a terminal input() loop.

Long-polls the bridge's GET /messages, runs each message's body through Agent.stream_run,
and posts the final reply back via POST /send. Access control (who's allowed to message
the bot at all) is enforced entirely inside the bridge via WHATSAPP_ALLOWED_USERS -- by the
time a message reaches this module it has already passed that gate, so nothing here
re-checks sender identity.

Runs as a long-lived background process (console script: hermes-whatsapp), unlike `hermes`
which is an interactive foreground REPL -- see whatsapp-bridge/README (start both together
via agent_dev's bin/miku-whatsapp launcher).
"""

from __future__ import annotations

import asyncio
import os

import httpx

from hermes.cli import HermesREPL
from hermes.config import load_config

BRIDGE_URL = os.environ.get("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3000")
POLL_INTERVAL_S = 2.0
RETRY_BACKOFF_S = 5.0


async def _handle_message(repl: HermesREPL, client: httpx.AsyncClient, msg: dict) -> None:
    chat_id = msg["chatId"]
    body = (msg.get("body") or "").strip()
    if not body:
        return
    who = msg.get("senderName") or chat_id
    print(f"[whatsapp] <- {who}: {body[:80]}")

    reply = ""
    try:
        async for event in repl.agent.stream_run(body):
            if event.type == "final":
                reply = event.data["content"]
    except Exception as exc:  # noqa: BLE001 - keep the channel alive across a bad turn
        reply = f"[error] {type(exc).__name__}: {exc}"

    if not reply:
        return
    resp = await client.post(f"{BRIDGE_URL}/send", json={"chatId": chat_id, "message": reply})
    resp.raise_for_status()
    print(f"[whatsapp] -> {who}: {reply[:80]}")


async def _run(repl: HermesREPL) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                resp = await client.get(f"{BRIDGE_URL}/messages")
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"[whatsapp] bridge unreachable ({exc}), retrying in {RETRY_BACKOFF_S:.0f}s")
                await asyncio.sleep(RETRY_BACKOFF_S)
                continue
            for msg in resp.json():
                await _handle_message(repl, client, msg)
            await asyncio.sleep(POLL_INTERVAL_S)


def main() -> None:
    # Keep the model resident between messages -- a WhatsApp reply shouldn't eat a ~40s
    # cold model load on top of inference. Doesn't touch the interactive REPL's behavior
    # (only applies here, and only if the user hasn't already set their own value).
    os.environ.setdefault("HERMES_OLLAMA_KEEP_ALIVE", "-1")

    config = load_config()
    repl = HermesREPL(config)

    async def _run_and_close() -> None:
        try:
            print(f"[whatsapp] polling {BRIDGE_URL} -- model: {repl.agent.model} (keep_alive={config.ollama_keep_alive})")
            repl.start_rag_scheduler()
            await _run(repl)
        finally:
            await repl.aclose()

    asyncio.run(_run_and_close())


if __name__ == "__main__":
    main()
