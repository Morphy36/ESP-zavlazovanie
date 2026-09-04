#!/usr/bin/env python3
"""Malý WebSocket klient pre Home Assistant.

Použitie:
    python3 ha_ws.py <typ_prikazu> [json_payload]
    python3 ha_ws.py --file payload.json      # payload vrátane "type"

Token sa číta z ~/.ha_token, URL z HA_URL (default http://192.168.0.10:8123).
"""
import asyncio, json, os, sys
import websockets

HA_URL = os.environ.get("HA_URL", "http://192.168.0.10:8123")
WS_URL = HA_URL.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
TOKEN = open(os.path.expanduser("~/.ha_token")).read().strip()


async def call(payload):
    async with websockets.connect(WS_URL, max_size=None) as ws:
        assert json.loads(await ws.recv())["type"] == "auth_required"
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth = json.loads(await ws.recv())
        if auth["type"] != "auth_ok":
            return {"success": False, "error": auth}
        await ws.send(json.dumps({"id": 1, **payload}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == 1 and msg.get("type") == "result":
                return msg


def main():
    if sys.argv[1] == "--file":
        payload = json.load(open(sys.argv[2]))
    else:
        payload = {"type": sys.argv[1]}
        if len(sys.argv) > 2:
            payload.update(json.loads(sys.argv[2]))
    res = asyncio.run(call(payload))
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(0 if res.get("success") else 1)


if __name__ == "__main__":
    main()
