import websockets
import asyncio
import json
import yaml

with open('elden_ring.yaml', 'r') as f:
    config = yaml.safe_load(f)

server = config['server']
if not server.startswith(('ws://', 'wss://')):
    server = f'ws://{server}'

DataPackage = {}
secret = {"uuid": "afc006ee-e0f7-47b0-838b-7d2c37ed417b"}

async def connect():
    global DataPackage
    while True:
        try:
            async with websockets.connect(server) as websocket:
                # 1. RoomInfo
                raw = await websocket.recv()
                print(f"Received RoomInfo: {raw}")
                room_info = json.loads(raw)[0]
                server_version = room_info.get("version")

                # 2. GetDataPackage
                await websocket.send(json.dumps([{"cmd": "GetDataPackage", "games": ["EldenRing"]}]))

                # 3. DataPackage
                raw = await websocket.recv()
                print(f"Received DataPackage: {raw[:200]}...")
                DataPackage = json.loads(raw)[0]

                with open('datapackage_eldenring.json', 'w', encoding='utf-8') as f:
                    json.dump(DataPackage, f, indent=4, ensure_ascii=False)
                print("DataPackage saved to datapackage_eldenring.json")

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

                # 6. Boucle d'écoute
                async for message in websocket:
                    parsed = json.loads(message)
                    print(f"Event: {parsed}")

        except Exception as e:
            print(f"Connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

asyncio.run(connect())