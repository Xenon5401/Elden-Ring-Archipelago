import json
import re
import unicodedata

TYPE_MAP = {
    "Weapon": 0,
    "Protector": 1,
    "Accessory": 2,
    "Goods": 4,
    "AshOfWar": 8,
}


def clean_name(name: str) -> str:
    name = re.sub(r"^\[.*?\]\s*", "", name)
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.strip()
    if name == "Terra Magicus":
        return "Terra Magica"
    return name


with open("flag_items_with_regions.json", "r", encoding="utf-8") as f:
    flag_items = json.load(f)

with open("datapackage_eldenring.json", "r", encoding="utf-8") as f:
    datapackage = json.load(f)

item_name_to_id = datapackage["data"]["games"]["EldenRing"]["item_name_to_id"]

name_to_game = {}
for flag_key, entry in flag_items.items():
    for item in entry["items"]:
        name = item["name"]
        if name in name_to_game:
            continue
        game_id = item["id"]
        game_type = TYPE_MAP.get(item["type"], 4)
        name_to_game[name] = {"id": game_id, "type": game_type}

# Also try matching via clean_name for items not directly matched
cleaned_to_original = {}
for name in name_to_game:
    c = clean_name(name)
    cleaned_to_original[c] = name

extra = 0
for ap_name in item_name_to_id:
    ap_clean = clean_name(ap_name)
    if ap_name not in name_to_game and ap_clean in cleaned_to_original:
        orig = cleaned_to_original[ap_clean]
        name_to_game[ap_name] = name_to_game[orig]
        extra += 1

output = {}
for name, data in name_to_game.items():
    output[name] = {"id": data["id"], "type": data["type"]}

with open("item_id_to_game_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Generated item_id_to_game_data.json with {len(output)} entries")
print(f"  - Direct matches: {len(output) - extra}")
print(f"  - Clean-name matches: {extra}")
