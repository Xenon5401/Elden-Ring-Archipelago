"""
Build flag_to_locations.json: maps each flag_id in flag_items_with_regions.json
to AP location IDs from datapackage_eldenring.json.

Matching logic:
1. If flag has regions → match region names to AP locations via area codes + item names
2. If flag has unique items → match item names directly to AP locations
3. If flag has no region AND only generic items → not mappable (empty array)

Usage: python build_flag_to_locations.py
Output: flag_to_locations.json
"""
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
FLAG_FILE = HERE / "flag_items_with_regions.json"
DP_FILE = HERE / "datapackage_eldenring.json"
AREA_CODES_FILE = HERE / "area_codes.json"
OUTPUT_FILE = HERE / "flag_to_locations.json"

GENERIC_PATTERNS = [
    r"^golden rune", r"^smithing stone", r"^somber smithing",
    r"^rune arc", r"^arteria leaf", r"^thin beast bone",
    r"^human bone shard", r"^glass shard", r"^hefty beast bone",
    r"^shadow realm rune", r"^broken rune", r"^lump of flesh",
    r"^beast blood", r"^beast liver", r"^old fang",
    r"^sliver of meat", r"^rainbow stone", r"^kukri",
    r"^throwing dagger", r"^ruin fragment",
    r"^furlcalling finger remedy", r"^gold-pickled fowl foot",
    r"^silver-pickled fowl foot", r"^pickled turtle neck",
    r"^preserving boluses", r"^immunizing", r"^neutralizing",
    r"^boluses", r"^shabriri grape", r"^larval tear",
    r"^starlight shards", r"^nascent butterfly",
    r"^budding horn", r"^crab eggs", r"^string", r"^soap",
    r"^dewgem", r"^exalted flesh", r"^smoldering butterfly",
    r"^drawstring", r"^fire grease", r"^magic grease",
    r"^lightning grease", r"^holy grease", r"^poisonbone dart",
    r"^poisoned stone", r"^warming stone", r"^boiled crab",
    r"^dappled cured meat", r"^ghost glovewort",
    r"^grave glovewort", r"^rold medallion",
    r"^cerulean", r"^crimson", r"^opaline",
    r"^stamina", r"^neutralizing", r"^immunizing",
    r"^preserving", r"^boluses",
    r"^livejar shard", r"^living jar shard",
    r"^festering bloody finger", r"^recusant finger",
    r"^root resin", r"^mushroom", r"^slumbering egg",
    r"^radiant", r"^rainbow stone arrow", r"^dwelling arrow",
    r"^stormhawk feather", r"^glintstone scrap",
    r"^crystal dart", r"^fan daggers", r"^ballista bolt",
    r"^great arrow", r"^lightning greatbolt",
    r"^explosive greatbolt", r"^explosive stone clump",
    r"^gravity stone", r"^stanching", r"^thawfrost",
    r"^scarab", r"^knot resin", r"^flight pinion",
    r"^silver horn tender", r"^golden horn tender",
    r"^spiritgrave stone", r"^spirit calculus",
    r"^radiant", r"^beast horn", r"^golden centipede",
    r"^scorpion liver", r"^whiteflesh mushroom",
    r"^sacramental bud", r"^rimed crystal bud",
]


def is_generic(name):
    return any(re.search(p, name.lower()) for p in GENERIC_PATTERNS)


def clean_item_name(name):
    # Strip leading [Category] prefixes like [Sorcery], [Incantation] but keep [quantity] suffixes
    name = re.sub(r'^\[.*?\]\s*', '', name)
    return name.strip()


def extract_area_code(loc_name):
    m = re.match(r'^([A-Za-z0-9]+)/', loc_name)
    return m.group(1) if m else None


def load_json(path):
    with open(path) as f:
        return json.load(f)


def main():
    print("Loading data...")
    flag_data = load_json(FLAG_FILE)
    dp_data = load_json(DP_FILE)
    area_codes = load_json(AREA_CODES_FILE)
    loc_map = dp_data["data"]["games"]["EldenRing"]["location_name_to_id"]

    # Build reverse: area name (lower) → area codes
    area_name_to_codes = defaultdict(list)
    for code, name in area_codes.items():
        clean = name.lower().split(" (")[0].split(" - ")[0]
        area_name_to_codes[clean].append(code)

    print(f"Flags: {len(flag_data)}, AP locations: {len(loc_map)}")

    # Index locations by item name for fast lookup
    # For each location name, extract the item name (after colon, before ' - ')
    item_to_locations = defaultdict(list)
    for loc_name, lid in loc_map.items():
        if not isinstance(lid, int):
            continue
        if ":" in loc_name:
            item_part = loc_name.split(":", 1)[1].strip()
            item_name = item_part.split(" - ")[0].strip().lower()
            item_to_locations[item_name].append((lid, loc_name))

    mapping = {}
    stats = {"mapped": 0, "empty_region_generic": 0, "empty_no_match": 0, "has_region": 0}

    for flag_id, entry in flag_data.items():
        regions = entry.get("regions", [])
        items = entry.get("items", [])
        item_names = set()
        has_unique = False
        for item in items:
            name = item["name"]
            item_names.add(name)
            if not is_generic(name):
                has_unique = True

        # item_name → {location_id} to track which item matched which location
        item_to_lids = defaultdict(set)

        # Strategy 1: Match via regions
        if regions:
            stats["has_region"] += 1
            for region in regions:
                region_lower = region.lower()
                parts = [p.strip() for p in region.split(" - ")]
                area_name = parts[0].lower()

                # Find matching area codes
                matched_codes = set()
                for code, name in area_codes.items():
                    nl = name.lower()
                    if area_name in nl or nl.startswith(area_name):
                        matched_codes.add(code)

                # Handle LD prefix
                if parts[0].upper() == "LD" and len(parts) >= 2:
                    for code, name in area_codes.items():
                        if parts[1].lower() in name.lower().split(" - ")[0].lower():
                            matched_codes.add(code)
                            break

                # Search locations matching area code + item name
                for loc_name, lid in loc_map.items():
                    if not isinstance(lid, int):
                        continue
                    loc_lower = loc_name.lower()
                    code = extract_area_code(loc_name)

                    if code not in matched_codes:
                        continue

                    # Check if any item from this flag matches
                    for item_name in item_names:
                        cname = clean_item_name(item_name).lower()
                        if cname and cname in loc_lower:
                            item_to_lids[item_name].add(lid)

                    # Boss drop matching (doesn't track which item, use a sentinel)
                    if is_boss_region(region_lower):
                        sub = parts[-1].lower()
                        if "boss drop" in loc_lower or "mainboss" in loc_lower:
                            frags = [w for w in re.findall(r"[a-z']+", sub) if len(w) > 2]
                            if any(f in loc_lower for f in frags):
                                item_to_lids["__bossdrop__"].add(lid)

        # Strategy 2: Match via unique item names directly (no region)
        if has_unique and not regions:
            for item_name in item_names:
                cname = clean_item_name(item_name).lower()
                if not cname or is_generic(item_name):
                    continue
                for loc_item_name, locs in item_to_locations.items():
                    if cname in loc_item_name:
                        for lid, _ in locs:
                            item_to_lids[item_name].add(lid)

        # Deduplicate: for each item_name, keep at most 1 location
        deduped = set()
        for item_name, lids in item_to_lids.items():
            if lids:
                deduped.add(next(iter(lids)))  # Take just 1 per item_name

        if deduped:
            mapping[flag_id] = sorted(x for x in deduped if isinstance(x, int))
            stats["mapped"] += 1
        elif regions:
            mapping[flag_id] = []
            stats["empty_no_match"] += 1
        else:
            mapping[flag_id] = []
            stats["empty_region_generic"] += 1

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"Saved: {OUTPUT_FILE}")

    mapped_count = sum(1 for v in mapping.values() if v)
    print(f"\nStats: {len(mapping)} total flags")
    print(f"  Mapped (has locations):   {mapped_count}")
    print(f"  Empty (no match found):   {len(mapping) - mapped_count}")
    print(f"  - had region but no match: {stats['empty_no_match']}")
    print(f"  - no region, generic items: {stats['empty_region_generic']}")

    # Show examples
    print(f"\nExamples:")
    with open(OUTPUT_FILE) as f:
        data = json.load(f)
    shown = 0
    for fid, locs in data.items():
        if locs and shown < 10:
            loc_names = [next((n for n, i in loc_map.items() if i == l), f"UNKNOWN({l})") for l in locs[:3]]
            print(f"  Flag {fid} → {locs[:3]}")
            for n in loc_names:
                print(f"      {n}")
            shown += 1
            print()


def is_boss_region(region_lower):
    bosses = {"godrick", "margit", "morgott", "rennala", "radahn", "rykard",
              "maliketh", "malenia", "mohg", "gideon", "hoarah loux", "godfrey",
              "fire giant", "placidusax", "fortissax", "astel", "loretta",
              "niall", "elemer", "godskin", "misbegotten", "erdtree",
              "tree sentinel", "leonine", "dragonkin soldier",
              "valiant gargoyle", "mimic tear", "ancient dragon",
              "death rite bird", "magma wyrm", "fallingstar beast",
              "tibia mariner", "ulcerated tree spirit",
              "black knife assassin", "crucible knight",
              "grafted scion", "abductor virgin"}
    return any(b in region_lower for b in bosses)


if __name__ == "__main__":
    main()
