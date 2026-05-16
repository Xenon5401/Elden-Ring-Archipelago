#!/usr/bin/env python3
import sys, os, json, termios, tty, select, asyncio
from websockets import connect

def load_flag_ids():
    path = os.path.join(os.path.dirname(__file__), "map_items.json")
    with open(path) as f:
        data = json.load(f)
    return sorted(int(k) for k in data.keys())

def fmt_flag(raw):
    import re
    m = re.search(r'"flag_id":(\d+).*?"value":(\d+)', raw)
    return f"flag={m.group(1)} val={m.group(2)}" if m else raw

async def main():
    ids = load_flag_ids()
    print(f"[archipelago] {len(ids)} locations loaded")

    async with connect("ws://127.0.0.1:12999/ws") as ws:
        msg1 = '{"set_flag_loot":[' + ",".join(str(i) for i in ids) + "]}"
        await ws.send(msg1)
        resp1 = await asyncio.wait_for(ws.recv(), timeout=5)
        print(f"[archipelago] {resp1}")

        msg2 = '{"set_watched_flag":[' + ",".join(str(i) for i in ids) + "]}"
        await ws.send(msg2)
        resp2 = await asyncio.wait_for(ws.recv(), timeout=5)
        print(f"[archipelago] {resp2}")

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setraw(fd)

        loop = asyncio.get_running_loop()
        stop = loop.create_future()

        def on_key():
            if select.select([sys.stdin], [], [], 0)[0]:
                k = sys.stdin.read(1)
                if k.lower() == 'n' or k == '\x03':
                    if not stop.done():
                        stop.set_result(True)

        loop.add_reader(fd, on_key)
        print("\r[archipelago] monitoring flags (press n to quit)")

        try:
            while not stop.done():
                try:
                    m = await asyncio.wait_for(ws.recv(), timeout=0.2)
                    if '"type":"flag_set"' in m:
                        print(f"\r[flag] {fmt_flag(m)}", flush=True)
                except asyncio.TimeoutError:
                    pass
        finally:
            loop.remove_reader(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    print("\n[done]")

asyncio.run(main())
