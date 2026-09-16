from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent

app_data_root = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
if app_data_root:
    APPDATA_DIR = Path(app_data_root) / "Destiny Zero to Hero"
else:
    APPDATA_DIR = Path.home() / ".destiny-zero-to-hero"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

SAVE_JSON = APPDATA_DIR / "save.json"

DATA_DIR = BASE_DIR / "data"
CACHE_DIR = APPDATA_DIR / "cache"
IMAGES_DIR = BASE_DIR / "assets"

ABILITIES_JSON = DATA_DIR / "abilities.json"
LOOT_TABLES_JSON = DATA_DIR / "loot_tables" / "raids.json"
RAID_TRAITS_JSON = DATA_DIR / "raid_traits.json"
EXOTIC_WEAPONS_JSON = DATA_DIR / "exotic_weapons.json"
MANIFEST_DB = DATA_DIR / "manifest.db"
ARMOUR_EMOJI_IMAGE = IMAGES_DIR / "armour_emoji.jpg"

# For debugging save
# SAVE_JSON = DATA_DIR / "save.json"