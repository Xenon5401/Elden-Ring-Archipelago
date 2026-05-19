import websockets
import asyncio
import json
import yaml
import re
import unicodedata
import urllib.request

with open('elden_ring.yaml', 'r') as f:
    config = yaml.safe_load(f)

server = config['server']
if not server.startswith(('ws://', 'wss://')):
    server = f'ws://{server}'


def clean_name(name: str) -> str:
    name = re.sub(r'^\[.*?\]\s*', '', name)
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = name.strip()
    if name == 'Terra Magicus':
        return 'Terra Magica'
    return name


class GameData:
    CACHE_FILE = 'datapackage_eldenring.json'

    def __init__(self):
        self._raw: dict = self._load_cache()
        self._flag_to_locs: dict[str, list[int]] | None = None  # cache interne

    def _load_cache(self) -> dict:
        try:
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def update(self, raw: dict):
        self._raw = raw
        self._flag_to_locs = None  # invalide le cache
        with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(raw, f, indent=4, ensure_ascii=False)
        print(f"DataPackage sauvegardé dans {self.CACHE_FILE}")

    @property
    def is_empty(self) -> bool:
        return not self._raw

    @property
    def _location_to_flag(self) -> dict:
        return (
            self._raw
            .get("data", {})
            .get("games", {})
            .get("EldenRing", {})
            .get("location_to_flag", {})
        )

    @property
    def flag_to_locs(self) -> dict[str, list[int]]:
        if self._flag_to_locs is None:
            result: dict[str, list[int]] = {}
            for loc_id, flag in self._location_to_flag.items():
                try:
                    result.setdefault(str(flag), []).append(int(loc_id))
                except (ValueError, TypeError) as e:
                    print(f"Warning: entrée invalide loc_id={loc_id} flag={flag}: {e}")
            self._flag_to_locs = result
        return self._flag_to_locs

    def watch_flags(self) -> list[int]:
        return [int(f) for f in self.flag_to_locs]

    def locs_for_flag(self, flag_id: int | str) -> list[int]:
        return self.flag_to_locs.get(str(flag_id), [])

    @property
    def item_name_to_id(self) -> dict[str, int]:
        return (
            self._raw
            .get("data", {})
            .get("games", {})
            .get("EldenRing", {})
            .get("item_name_to_id", {})
        )

    @property
    def item_id_to_name(self) -> dict[int, str]:
        return {v: k for k, v in self.item_name_to_id.items()}


with open('item_id_to_game_data.json', 'r', encoding='utf-8') as f:
    ITEM_GAME_DATA: dict[str, dict] = json.load(f)

_X_PAT = re.compile(r'^(.+) x(\d+)$')

secret = {"uuid": "afc006ee-e0f7-47b0-838b-7d2c37ed417b"}

queue_serv_to_dll = asyncio.Queue()
queue_dll_to_serv = asyncio.Queue()

game_data = GameData()


async def server_archi():
    received_idx = 0
    while True:
        try:
            async with websockets.connect(server) as websocket:
                raw = await websocket.recv()
                print(f"Received RoomInfo: {raw}")
                room_info = json.loads(raw)[0]
                server_version = room_info.get("version")

                if game_data.is_empty:
                    await websocket.send(json.dumps([{"cmd": "GetDataPackage", "games": ["EldenRing"]}]))
                    raw = await websocket.recv()
                    print(f"Received DataPackage: {raw[:200]}...")
                    game_data.update(json.loads(raw)[0])

                await websocket.send(json.dumps([{
                    "cmd": "Connect",
                    "password": config.get('password', ''),
                    "game": "EldenRing",
                    "name": config['name'],
                    "uuid": secret.get('uuid'),
                    "version": server_version,
                    "items_handling": 0b011,
                    "tags": [],
                    "slot_data": False
                }]))

                raw = await websocket.recv()
                response = json.loads(raw)[0]

                if response["cmd"] == "ConnectionRefused":
                    print(f"Refused: {response.get('errors')}")
                    return

                missing = response.get("missing_locations", [])
                checked = response.get("checked_locations", [])
                print(f"Connected! Team={response['team']} Slot={response['slot']}")
                print(f"Missing: {len(missing)} | Checked: {len(checked)}")

                async def send_loop():
                    while True:
                        msg = await queue_dll_to_serv.get()
                        print(f"[Server] Envoi vers AP: {msg}")
                        await websocket.send(json.dumps(msg))

                async def recv_loop():
                    nonlocal received_idx
                    id_to_name = game_data.item_id_to_name
                    async for message in websocket:
                        parsed = json.loads(message)
                        if isinstance(parsed, list) and parsed[0].get("cmd") == "ReceivedItems":
                            items = parsed[0].get("items", [])
                            index = parsed[0].get("index", 0)
                            print(f"[Server] ReceivedItems: index={index}, count={len(items)}")
                            for i, it in enumerate(items):
                                idx = index + i
                                if idx < received_idx:
                                    continue
                                item_id = it.get("item")
                                name = id_to_name.get(item_id)
                                if name is None:
                                    print(f"[Server]   [{idx}] item_id={item_id} inconnu, skip")
                                    continue
                                m = _X_PAT.match(name)
                                if m:
                                    base_name = m.group(1)
                                    qty = int(m.group(2))
                                else:
                                    base_name = name
                                    qty = 1
                                gd = ITEM_GAME_DATA.get(base_name)
                                if gd is None:
                                    print(f"[Server]   [{idx}] {name}: pas de game data, skip")
                                    continue
                                url = f"http://127.0.0.1:12999/give?base_id={gd['id']}&type={gd['type']}&qty={qty}"
                                try:
                                    urllib.request.urlopen(url, timeout=2)
                                    print(f"[Server]   [{idx}] {name} → /give OK (qty={qty})")
                                except Exception as e:
                                    print(f"[Server]   [{idx}] {name} → /give FAIL: {e}")
                                await asyncio.sleep(0.05)
                                received_idx = idx + 1
                        else:
                            print(f"[Server] Event AP: {parsed}")

                await asyncio.gather(send_loop(), recv_loop())

        except Exception as e:
            print(f"Connection error: {e}. Retry in 5s...")
            await asyncio.sleep(5)


async def dll():
    while True:
        try:
            async with websockets.connect("ws://127.0.0.1:12999/ws", ping_interval=20, ping_timeout=10) as websocket:
                print("[DLL] Connecté")

                flags = game_data.watch_flags()
                if flags:
                    loot_msg = {"set_flag_loot": flags}
                    print(f"[DLL] Envoi de {len(flags)} flags à surveiller")
                    await websocket.send(json.dumps(loot_msg))
                    try:
                        resp = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        print(f"[DLL] Réponse set_flag_loot: {resp}")
                    except asyncio.TimeoutError:
                        print("[DLL] Timeout set_flag_loot (continuant...)")

                async def recv_loop():
                    pending_locs: set[int] = set()

                    async def flush():
                        if pending_locs:
                            locs = list(pending_locs)
                            pending_locs.clear()
                            check_msg = [{"cmd": "LocationChecks", "locations": locs}]
                            print(f"[DLL] → LocationChecks batch: {len(locs)} locs")
                            await queue_dll_to_serv.put(check_msg)

                    async def reader():
                        async for message in websocket:
                            parsed = json.loads(message)
                            print(f"[DLL] Event: {parsed}")
                            if isinstance(parsed, dict) and parsed.get("type") == "flag_set":
                                if parsed.get("value") == 1:
                                    locs = game_data.locs_for_flag(parsed["flag_id"])
                                    print(f"[DLL] Flag {parsed['flag_id']} → locations: {locs}")
                                    pending_locs.update(locs)

                    async def flusher():
                        while True:
                            await asyncio.sleep(0.2)
                            await flush()

                    await asyncio.gather(reader(), flusher())

                await recv_loop()

        except Exception as e:
            print(f"[DLL] Error: {e}. Retry in 5s...")
            await asyncio.sleep(5)


async def main():
    await asyncio.gather(server_archi(), dll())

asyncio.run(main())