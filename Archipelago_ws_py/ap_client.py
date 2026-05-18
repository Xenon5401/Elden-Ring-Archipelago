import websockets  # type: ignore
import asyncio
import json
import yaml
import re
import unicodedata

with open('elden_ring.yaml', 'r') as f:
    config = yaml.safe_load(f)

server = config['server']
if not server.startswith(('ws://', 'wss://')):
    server = f'ws://{server}'

try:
    with open('datapackage_eldenring.json', 'r', encoding='utf-8') as f:
        DataPackage = json.load(f)
except FileNotFoundError:
    DataPackage = {}


def clean_name(name: str) -> str:
    name = re.sub(r'^\[.*?\]\s*', '', name)
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = name.strip()
    if name == 'Terra Magicus':
        return 'Terra Magica'
    return name


def build_flag_maps(dp: dict):
    location_to_flag = dp.get("data", {}).get("games", {}).get("EldenRing", {}).get("location_to_flag", {})
    FLAG_TO_LOC_IDS = {}
    
    for key, value in location_to_flag.items():
        try:
            # Try to convert key to int (should be location ID)
            loc_id = int(key)
            flag = str(value)
            FLAG_TO_LOC_IDS.setdefault(flag, []).append(loc_id)
        except (ValueError, TypeError) as e:
            print(f"Warning: Skipping invalid entry in location_to_flag - key: {key}, value: {value}, error: {e}")
            continue
    
    LOOT_FLAG_IDS = list(FLAG_TO_LOC_IDS.keys())
    return FLAG_TO_LOC_IDS, LOOT_FLAG_IDS


FLAG_TO_LOC_IDS, LOOT_FLAG_IDS = build_flag_maps(DataPackage) if DataPackage else ({}, [])


secret = {"uuid": "afc006ee-e0f7-47b0-838b-7d2c37ed417b"}

# Queue partagée entre les deux clients
queue_serv_to_dll = asyncio.Queue()
queue_dll_to_serv = asyncio.Queue()

# Client Archipelago (communication avec le serveur Archipelago)

async def server_archi():
    global DataPackage, FLAG_TO_LOC_IDS, LOOT_FLAG_IDS
    while True:
        try:
            async with websockets.connect(server) as websocket:
                # 1. RoomInfo
                raw = await websocket.recv()
                print(f"Received RoomInfo: {raw}")
                room_info = json.loads(raw)[0]
                server_version = room_info.get("version")

                # 2. GetDataPackage
                if DataPackage == {}:
                    await websocket.send(json.dumps([{"cmd": "GetDataPackage", "games": ["EldenRing"]}]))

                    # 3. DataPackage
                    raw = await websocket.recv()
                    print(f"Received DataPackage: {raw[:200]}...")
                    DataPackage = json.loads(raw)[0]
                    print(DataPackage["data"]["games"]["EldenRing"].keys())

                    with open('datapackage_eldenring.json', 'w', encoding='utf-8') as f:
                        json.dump(DataPackage, f, indent=4, ensure_ascii=False)
                    print("DataPackage saved to datapackage_eldenring.json")

                    FLAG_TO_LOC_IDS, LOOT_FLAG_IDS = build_flag_maps(DataPackage)

                # 4. Connect
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

                # 5. Connected ou ConnectionRefused
                raw = await websocket.recv()
                response = json.loads(raw)[0]

                if response["cmd"] == "ConnectionRefused":
                    print(f"Refused: {response.get('errors')}")
                    return

                missing = response.get("missing_locations", [])
                checked = response.get("checked_locations", [])

                print(f"Connected! Team={response['team']} Slot={response['slot']}")
                print(f"Missing locations: {len(missing)} | first: {missing[:3]} ... last: {missing[-3:]}")
                print(f"Checked locations: {len(checked)}")

               # Tâche séparée pour envoyer les messages de la DLL vers AP
                async def send_loop():
                    while True:
                        msg = await queue_dll_to_serv.get()
                        print(f"[Server] Envoi vers AP: {msg}")
                        await websocket.send(json.dumps(msg))

                # Tâche séparée pour recevoir les messages AP (pas forwardé à DLL)
                async def recv_loop():
                    async for message in websocket:
                        parsed = json.loads(message)
                        print(f"[Server] Event AP: {parsed}")

                await asyncio.gather(send_loop(), recv_loop())


        except Exception as e:
            print(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

# Client DLL 

async def dll():
    global LOOT_FLAG_IDS
    while True:
        try:


            async with websockets.connect("ws://127.0.0.1:12999/ws", ping_interval=20, ping_timeout=10) as websocket:
                print("[DLL] Connecté")

                # Envoyer la liste des flags à surveiller
                if LOOT_FLAG_IDS:
                    # Convertir les strings en entiers
                    loot_flags_int = [int(flag) for flag in LOOT_FLAG_IDS]
                    loot_msg = {"set_flag_loot": loot_flags_int}
                    print(f"[DLL] Envoi de {len(loot_flags_int)} flags à surveiller")
                    print(f"[DLL] Flags envoyés: {loot_flags_int[:10]}{'...' if len(loot_flags_int) > 10 else ''}")
                    print(f"[DLL] Message complet: {json.dumps(loot_msg)[:500]}...")
                    await websocket.send(json.dumps(loot_msg))
                    try:
                        resp = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        print(f"[DLL] Réponse set_flag_loot: {resp}")
                    except asyncio.TimeoutError:
                        print("[DLL] Timeout en attente de réponse set_flag_loot (continuant...)")
                        # Continue anyway - the server might not send an ack

                async def recv_loop():
                    pending_locs = set()

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
                                    fid = str(parsed["flag_id"])
                                    loc_ids = FLAG_TO_LOC_IDS.get(fid, [])
                                    print(f"[DLL] Flag {fid} set -> locations: {loc_ids}")
                                    if loc_ids:
                                        pending_locs.update(loc_ids)

                    async def flusher():
                        while True:
                            await asyncio.sleep(0.2)
                            await flush()

                    await asyncio.gather(reader(), flusher())

                await recv_loop()

        except Exception as e:
            print(f"[DLL_serveur] Error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

async def main():
    await asyncio.gather(
        server_archi(),
        dll()
    )

asyncio.run(main())