"""Match a manual abilities list against the Destiny manifest.

Reads `data/abilities.json`, looks up each entry in the SQLite manifest
(`data/manifest.db`), and writes `data/abilities_resolved.json` with hash
and icon fields added.

Usage:
    python tools/match_abilities_to_manifest.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.definitions import DestinyDefinitions
from api.manifest import ManifestManager

DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.db"
ABILITIES_PATH = DATA_DIR / "abilities.json"
OUTPUT_PATH = DATA_DIR / "abilities_resolved.json"

TYPE_HINTS = {
    "movement": ["jump", "lift", "glide", "blink"],
    "class": ["class ability", "dodge", "barricade", "rift", "thruster", "dive"],
    "melee": ["melee"],
    "super": ["super"],
    "grenade": ["grenade"],
    "fragment": ["fragment"],
    "aspect": ["aspect"],
}


def ensure_manifest():
    if MANIFEST_PATH.exists() and MANIFEST_PATH.stat().st_size > 0:
        return
    ManifestManager(MANIFEST_PATH).download_manifest()


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_manual_entries(path: Path):
    data = load_json(path)

    if isinstance(data, dict):
        data = list(data.values())

    if not isinstance(data, list):
        raise ValueError(f"Expected a list or object map in {path}")

    normalized = []
    for entry in data:
        if not isinstance(entry, dict):
            continue

        normalized.append({
            "name": entry.get("name", ""),
            "type": entry.get("type", ""),
            "element": entry.get("element", ""),
            "classes": normalize_classes(entry.get("classes", [])),
            "prismatic": bool(entry.get("prismatic", False)),
            "raw": entry,
        })

    return normalized


def normalize_text(value):
    return " ".join(str(value or "").strip().lower().split())


def normalize_classes(value):
    if value is None:
        return []

    raw_values = [value] if isinstance(value, str) else list(value)

    classes = []
    for entry in raw_values:
        for part in str(entry).split(","):
            cleaned = part.strip()
            if cleaned:
                classes.append(cleaned)

    deduped = []
    seen = set()
    for class_name in classes:
        normalized = class_name.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)

    return deduped


def index_manifest(definitions: DestinyDefinitions):
    indexed = []
    for item in definitions.iter_item_definitions():
        display = item.get("displayProperties", {})
        name = display.get("name", "")
        if not name:
            continue

        indexed.append({
            "hash": item.get("hash"),
            "name": name,
            "name_norm": normalize_text(name),
            "itemTypeDisplayName": item.get("itemTypeDisplayName", "") or "",
            "icon": display.get("icon"),
            "classType": item.get("classType"),
            "categoryHashes": item.get("itemCategoryHashes", []) or [],
            "description": display.get("description", ""),
        })

    return indexed


def type_score(manual_type, manifest_item):
    manual_type = normalize_text(manual_type)
    if not manual_type:
        return 0

    item_type = normalize_text(manifest_item.get("itemTypeDisplayName", ""))
    score = 0

    for hint in TYPE_HINTS.get(manual_type, []):
        if hint in item_type:
            score += 10

    if manual_type in TYPE_HINTS and any(hint in item_type for hint in TYPE_HINTS[manual_type]):
        score += 20

    return score


def resolve_entry(entry, manifest_index):
    name = entry.get("name", "")
    name_norm = normalize_text(name)
    manual_type = normalize_text(entry.get("type", ""))
    manual_classes = normalize_classes(entry.get("classes", []))

    candidates = [item for item in manifest_index if item["name_norm"] == name_norm]

    if not candidates:
        candidates = [item for item in manifest_index if name_norm and name_norm in item["name_norm"]]

    if not candidates:
        return {"entry": entry, "status": "unmatched", "matches": []}

    scored = []
    for candidate in candidates:
        score = 100
        score += type_score(manual_type, candidate)

        candidate_name = candidate["name"].lower()
        if any(cls.lower() in candidate_name for cls in manual_classes):
            score += 5

        if "| light ability" in normalize_text(candidate.get("itemTypeDisplayName", "")):
            score -= 1

        scored.append((score, candidate))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["hash"]))
    best_score, best = scored[0]

    output = {
        "entry": entry,
        "status": "resolved",
        "hash": best["hash"],
        "icon": best["icon"],
        "resolvedName": best["name"],
        "itemTypeDisplayName": best["itemTypeDisplayName"],
        "classType": best["classType"],
        "score": best_score,
    }

    if len(scored) > 1:
        output["alternatives"] = [
            {
                "hash": candidate["hash"],
                "name": candidate["name"],
                "itemTypeDisplayName": candidate["itemTypeDisplayName"],
                "icon": candidate["icon"],
                "score": score,
            }
            for score, candidate in scored[1:5]
        ]

    return output


def main():
    ensure_manifest()

    if not ABILITIES_PATH.exists():
        raise FileNotFoundError(f"Missing {ABILITIES_PATH}")

    manual_entries = load_manual_entries(ABILITIES_PATH)
    definitions = DestinyDefinitions(MANIFEST_PATH)
    manifest_index = index_manifest(definitions)

    resolved = []
    unmatched = []

    for entry in manual_entries:
        result = resolve_entry(entry, manifest_index)
        if result["status"] == "resolved":
            resolved.append(result)
        else:
            unmatched.append(result)

    output = {
        "resolved": resolved,
        "unmatched": unmatched,
        "summary": {
            "inputCount": len(manual_entries),
            "resolvedCount": len(resolved),
            "unmatchedCount": len(unmatched),
        },
    }

    resolved_entries = [
        {
            **result["entry"],
            "hash": result["hash"],
            "icon": result["icon"],
            "resolvedName": result["resolvedName"],
            "itemTypeDisplayName": result["itemTypeDisplayName"],
            "classType": result["classType"],
        }
        for result in resolved
    ]

    resolved_output_path = OUTPUT_PATH.with_name("abilities_resolved_flat.json")
    with resolved_output_path.open("w", encoding="utf-8") as f:
        json.dump(resolved_entries, f, indent=2, ensure_ascii=False)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(json.dumps(output["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Wrote {resolved_output_path}")


if __name__ == "__main__":
    main()
