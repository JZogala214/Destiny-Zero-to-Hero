"""Validate raid loot table names against the Destiny manifest.

Checks weapon and armor drop names in `data/loot_tables/raids.json`
against the SQLite manifest (`data/manifest.db`) and writes a validation
report to `data/loot_table_validation.json`.

Usage:
    python tools/validate_raid_tables.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.definitions import DestinyDefinitions

DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.db"
RAIDS_PATH = DATA_DIR / "loot_tables" / "raids.json"
OUTPUT_PATH = DATA_DIR / "loot_table_validation.json"

ARMOR_SLOTS = {"helmet", "arms", "chest", "legs", "class item"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_raid_tables(raw_tables):
    if isinstance(raw_tables, dict):
        return raw_tables

    normalized = {}
    if isinstance(raw_tables, list):
        for entry in raw_tables:
            if not isinstance(entry, dict):
                continue
            for raid_name, raid_data in entry.items():
                if isinstance(raid_data, dict):
                    normalized[raid_name] = raid_data

    return normalized


def normalize_name(value):
    return " ".join(str(value or "").strip().lower().split())


def build_manifest_index(definitions: DestinyDefinitions):
    index = {}
    for item in definitions.iter_item_definitions():
        display = item.get("displayProperties", {})
        name = display.get("name", "")
        if not name:
            continue
        index.setdefault(normalize_name(name), []).append({
            "hash": item.get("hash"),
            "name": name,
            "itemTypeDisplayName": item.get("itemTypeDisplayName", "") or "",
            "icon": display.get("icon"),
        })
    return index


def classify_drop(name):
    if normalize_name(name) in ARMOR_SLOTS:
        return "armor"
    return "weapon"


def check_drop(drop_name, manifest_index, report, target, raid_name, encounter_name=None):
    report["summary"]["dropsChecked"] += 1

    if classify_drop(drop_name) == "armor":
        report["summary"]["armorChecked"] += 1
        target["matched"].append({"name": drop_name, "type": "armor"})
        report["summary"]["matched"] += 1
        return

    report["summary"]["weaponsChecked"] += 1
    matches = manifest_index.get(normalize_name(drop_name), [])
    if matches:
        best = matches[0]
        target["matched"].append({
            "name": drop_name,
            "hash": best["hash"],
            "icon": best["icon"],
            "itemTypeDisplayName": best["itemTypeDisplayName"],
        })
        report["summary"]["matched"] += 1
    else:
        target["missing"].append(drop_name)
        report["summary"]["missing"] += 1
        missing_entry = {"raid": raid_name, "name": drop_name, "type": "weapon"}
        if encounter_name:
            missing_entry["encounter"] = encounter_name
        report["missingDrops"].append(missing_entry)


def validate_tables(raids, manifest_index):
    report = {
        "summary": {
            "raidsChecked": 0,
            "dropsChecked": 0,
            "weaponsChecked": 0,
            "armorChecked": 0,
            "matched": 0,
            "missing": 0,
        },
        "raids": {},
        "missingDrops": [],
    }

    for raid_name, raid_data in raids.items():
        report["summary"]["raidsChecked"] += 1

        raid_report = {
            "encounters": {},
            "lootTable": {"matched": [], "missing": []},
        }

        for drop_name in raid_data.get("loot_table", []) or []:
            check_drop(drop_name, manifest_index, report, raid_report["lootTable"], raid_name)

        for encounter_name, encounter_data in (raid_data.get("encounters", {}) or {}).items():
            encounter_report = {"matched": [], "missing": []}

            for drop_name in encounter_data.get("drops", []) or []:
                check_drop(
                    drop_name, manifest_index, report, encounter_report,
                    raid_name, encounter_name,
                )

            raid_report["encounters"][encounter_name] = encounter_report

        report["raids"][raid_name] = raid_report

    return report


def main():
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Missing manifest database: {MANIFEST_PATH}. "
            "Provide the bundled manifest before running this validator."
        )
    if not RAIDS_PATH.exists():
        raise FileNotFoundError(f"Missing raid tables file: {RAIDS_PATH}")

    definitions = DestinyDefinitions(MANIFEST_PATH)
    raids = normalize_raid_tables(load_json(RAIDS_PATH))
    manifest_index = build_manifest_index(definitions)

    report = validate_tables(raids, manifest_index)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
