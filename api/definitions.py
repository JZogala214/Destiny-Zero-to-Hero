import json
import random
import re
import sqlite3
from pathlib import Path

from paths import DATA_DIR

_EMPTY_SOCKET_RE = re.compile(r"^empty .* socket$", re.IGNORECASE)


def _to_signed_int32(value: int) -> int:
    # Bungie hashes are unsigned 32-bit, but the manifest DB stores the `id`
    # column as a signed 32-bit integer. Any hash >= 2^31 needs to be
    # converted or it won't match any row.
    value &= 0xFFFFFFFF
    if value >= 0x80000000:
        value -= 0x100000000
    return value


class DestinyDefinitions:
    """Reads item/perk definitions from the local Bungie manifest (SQLite)
    and generates randomized weapon rolls.

    Replaces the old JSON-backed (items.json) implementation. The public
    interface is a superset of the old one: search_item keeps its scoring
    behaviour for the UI's icon lookups.
    """

    WEAPON_ROLL_SLOTS = ["Barrel", "Magazine", "Trait 1", "Trait 2", "Origin Trait", "Masterwork"]

    def __init__(self, manifest_path="data/manifest.db"):
        self.manifest_path = Path(manifest_path)
        self.origin_trait_names = self._load_origin_trait_names(DATA_DIR / "raid_traits.json")

        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"Manifest not found at {self.manifest_path}. "
                f"Run ManifestManager.download_manifest() first."
            )

        self._conn = sqlite3.connect(f"file:{self.manifest_path}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row

    def _load_origin_trait_names(self, traits_path: Path):
        if not traits_path.exists():
            return set()

        with traits_path.open("r", encoding="utf-8") as f:
            traits = json.load(f)

        if not isinstance(traits, list):
            return set()

        return {str(trait).strip().lower() for trait in traits if str(trait).strip()}

    # -- raw lookups --------------------------------------------------

    def get_definition(self, table: str, hash_: int):
        row = self._conn.execute(
            f"SELECT json FROM {table} WHERE id = ?",
            (_to_signed_int32(hash_),),
        ).fetchone()

        if row is None:
            return None

        return json.loads(row["json"])

    @staticmethod
    def _has_random_sockets(item) -> bool:
        sockets = (item.get("sockets", {}) or {}).get("socketEntries", []) or []
        return any(socket.get("randomizedPlugSetHash") for socket in sockets)

    def _plug_item_hashes_for_socket(self, socket) -> list:
        """Collects every plug item hash a socket can hold, across
        singleInitialItemHash, direct reusablePlugItems, and both plug sets."""
        hashes = []

        single = socket.get("singleInitialItemHash")
        if single:
            hashes.append(single)

        for plug in socket.get("reusablePlugItems", []) or []:
            plug_hash = plug.get("plugItemHash")
            if plug_hash:
                hashes.append(plug_hash)

        for key in ("reusablePlugSetHash", "randomizedPlugSetHash"):
            plug_set_hash = socket.get(key)
            if not plug_set_hash:
                continue
            plug_set = self.get_definition("DestinyPlugSetDefinition", plug_set_hash)
            if not plug_set:
                continue
            for plug in plug_set.get("reusablePlugItems", []) or []:
                plug_hash = plug.get("plugItemHash")
                if plug_hash:
                    hashes.append(plug_hash)

        return hashes

    def _is_origin_trait_plug(self, plug_def) -> bool:
        if not plug_def:
            return False

        display_name = str((plug_def.get("displayProperties", {}) or {}).get("name", "")).strip().lower()
        if self.origin_trait_names:
            return display_name in self.origin_trait_names

        plug_category = ((plug_def.get("plug", {}) or {}).get("plugCategoryIdentifier") or "")
        if plug_category == "origins":
            return True

        return str(plug_def.get("itemTypeDisplayName", "")).strip().lower() == "origin trait"

    def get_origin_traits(self, weapon_item) -> list:
        """Returns the origin trait perks on a weapon definition, e.g.
        [{"hash": ..., "name": "Runneth Over", "description": ...}]."""
        traits = []
        seen_names = set()

        sockets = (weapon_item.get("sockets", {}) or {}).get("socketEntries", []) or []
        for socket in sockets:
            for plug_hash in self._plug_item_hashes_for_socket(socket):
                plug = self.get_definition("DestinyInventoryItemDefinition", plug_hash)
                if not self._is_origin_trait_plug(plug):
                    continue

                display = plug.get("displayProperties", {}) or {}
                name = display.get("name")
                if self._is_placeholder_plug(name):
                    continue

                normalized_name = str(name).strip().lower()
                if self.origin_trait_names and normalized_name not in self.origin_trait_names:
                    continue

                if normalized_name in seen_names:
                    continue
                seen_names.add(normalized_name)

                traits.append({
                    "hash": plug.get("hash"),
                    "name": name,
                    "description": display.get("description"),
                })

        return traits

    def has_origin_trait(self, item) -> bool:
        return bool(self.get_origin_traits(item))

    def find_item_by_name(self, name: str):
        """Finds the best manifest item with this exact display name.

        The manifest often contains several items sharing one name:
        collections dummies, fixed-roll copies, and legacy (sunset)
        versions whose random pools contain outdated perks. Origin traits
        only exist on current reissues, so a randomizable copy WITH an
        origin trait outranks everything else:
        randomizable+origin > randomizable > origin > weapon > sockets > rest.
        """
        cursor = self._conn.execute(
            "SELECT json FROM DestinyInventoryItemDefinition WHERE json LIKE ?",
            (f'%"name":"{name}"%',),
        )

        candidates = []
        for row in cursor:
            item = json.loads(row["json"])
            display_name = (item.get("displayProperties", {}) or {}).get("name", "")
            if display_name == name:
                candidates.append(item)

        if not candidates:
            return None

        def score(item):
            has_random = self._has_random_sockets(item)
            has_origin = self.has_origin_trait(item) if item.get("itemType") == 3 else False
            is_weapon = item.get("itemType") == 3
            has_sockets = bool((item.get("sockets", {}) or {}).get("socketEntries"))
            return (has_random and has_origin, has_random, has_origin, is_weapon, has_sockets)

        return max(candidates, key=score)

    def search_item(self, query):
        """Fuzzy name search, preserving the old JSON implementation's
        scoring: prefers exact matches, ability-like items, and non-emotes.
        Used by the UI for icon lookups.
        """
        query = str(query).lower().strip()
        if not query:
            return None

        def score(item):
            display = item.get("displayProperties", {})
            name = display.get("name", "")
            item_type = str(item.get("itemTypeDisplayName", "")).lower()
            trait_ids = item.get("traitIds", []) or []

            exact_match = name.lower() == query

            # Weapons (and their catalysts/ornaments) are looked up by hash
            # elsewhere (see MainWindow._set_icon_for_drop_on_label), so this
            # search is only ever used for abilities/placeholders now.
            # Several exotic weapons share a name with an ability (e.g. the
            # "Bastion" Void Titan aspect vs. the "Bastion" exotic fusion
            # rifle) - deprioritizing weapons here resolves that collision
            # in favor of the ability.
            not_weapon = item.get("itemType") != 3

            ability_like = any(
                keyword in item_type
                for keyword in (
                    "ability", "melee", "grenade", "class ability", "super",
                    "aspect", "fragment",
                )
            )
            not_emote = "item.emote" not in trait_ids and item_type != "emote"

            return (
                2 if exact_match else 1,
                1 if not_weapon else 0,
                1 if ability_like else 0,
                1 if not_emote else 0,
            )

        # LIKE is case-insensitive for ASCII by default in SQLite, which
        # narrows candidates cheaply before scoring in Python.
        cursor = self._conn.execute(
            "SELECT json FROM DestinyInventoryItemDefinition WHERE json LIKE ?",
            (f"%{query}%",),
        )

        matches = []
        for row in cursor:
            item = json.loads(row["json"])
            name = item.get("displayProperties", {}).get("name", "")
            if query in name.lower():
                matches.append(item)

        if not matches:
            return None

        return max(matches, key=score)

    def iter_item_definitions(self):
        """Yields every DestinyInventoryItemDefinition row, parsed.

        Used by the maintenance tools (validate_raid_tables,
        match_abilities_to_manifest) instead of loading items.json.
        """
        cursor = self._conn.execute("SELECT json FROM DestinyInventoryItemDefinition")
        for row in cursor:
            yield json.loads(row["json"])

    # -- perk / socket resolution --------------------------------------

    def _is_placeholder_plug(self, name):
        if not name:
            return True
        # Bungie's manifest includes placeholder plugs like "Empty Trait
        # Socket", "Empty Catalyst Socket" etc. These aren't real perk options.
        return bool(_EMPTY_SOCKET_RE.match(name.strip()))

    def get_perks_from_plug_set(self, plug_set_hash: int):
        plug_set = self.get_definition("DestinyPlugSetDefinition", plug_set_hash)
        if not plug_set:
            return []

        perks = []
        seen_names = set()

        for plug in plug_set.get("reusablePlugItems", []) or []:
            perk = self.get_definition("DestinyInventoryItemDefinition", plug.get("plugItemHash"))
            if not perk:
                continue

            display = perk.get("displayProperties", {}) or {}
            name = display.get("name")

            if self._is_placeholder_plug(name):
                continue

            if name in seen_names:
                continue
            seen_names.add(name)

            perks.append({
                "hash": perk.get("hash"),
                "name": name,
                "description": display.get("description"),
            })

        return perks

    def _is_origin_trait_plug_set(self, plug_set_hash: int) -> bool:
        """True if any plug in this plug set is an origin trait.

        Some current weapons expose their origin trait socket through a
        randomizedPlugSetHash (when the weapon can roll one of several
        origin traits), which would otherwise make it look like an
        ordinary perk pool and get double-counted alongside the explicit
        origin trait handling in build_weapon_roll.
        """
        plug_set = self.get_definition("DestinyPlugSetDefinition", plug_set_hash)
        if not plug_set:
            return False

        for plug in plug_set.get("reusablePlugItems", []) or []:
            plug_def = self.get_definition("DestinyInventoryItemDefinition", plug.get("plugItemHash"))
            if self._is_origin_trait_plug(plug_def):
                return True

        return False

    def get_weapon_perk_pools(self, weapon_hash: int):
        weapon = self.get_definition("DestinyInventoryItemDefinition", weapon_hash)
        if not weapon:
            raise ValueError("Weapon not found")

        pools = []
        for socket in (weapon.get("sockets", {}) or {}).get("socketEntries", []) or []:
            plug_set_hash = socket.get("randomizedPlugSetHash")
            if not plug_set_hash:
                continue

            if self._is_origin_trait_plug_set(plug_set_hash):
                continue

            perks = self.get_perks_from_plug_set(plug_set_hash)
            pools.append({"plugSetHash": plug_set_hash, "perks": perks})

        return pools

    # -- roll generation ------------------------------------------------

    def build_weapon_roll(self, weapon_name: str, require_origin_trait: bool = True):
        item = self.find_item_by_name(weapon_name)
        if not item:
            raise ValueError(f"Weapon not found in manifest: '{weapon_name}'")

        origin_traits = self.get_origin_traits(item)
        if not origin_traits and require_origin_trait:
            # Origin traits only exist on current weapon versions. Their
            # absence means every manifest copy of this name is a legacy /
            # sunset version whose random pools contain outdated perks, so
            # rolling it would produce perks the weapon can no longer have.
            raise ValueError(
                f"'{weapon_name}' has no origin trait in the manifest - only "
                f"legacy versions were found, so it cannot be rolled. Check "
                f"the loot table entry or re-download the manifest."
            )

        weapon_hash = item.get("hash")
        pools = self.get_weapon_perk_pools(weapon_hash)

        if require_origin_trait and not any(pool["perks"] for pool in pools):
            # Exotics (require_origin_trait=False) commonly have fixed,
            # non-randomized perks, so an empty pool there is expected, not
            # a data problem worth flagging.
            print(
                f"Warning: '{weapon_name}' (hash {weapon_hash}) has no "
                f"randomized perk pools in the manifest; roll will be empty."
            )

        roll = []
        for index, pool in enumerate(pools):
            if not pool["perks"]:
                continue

            perk = random.choice(pool["perks"])
            slot = (
                self.WEAPON_ROLL_SLOTS[index]
                if index < len(self.WEAPON_ROLL_SLOTS)
                else f"Trait {index + 1}"
            )
            roll.append({"slot": slot, "perk": perk["name"], "perkHash": perk["hash"]})

        for trait in origin_traits:
            roll.append({
                "slot": "Origin Trait",
                "perk": trait["name"],
                "perkHash": trait["hash"],
            })

        display = item.get("displayProperties", {}) or {}
        return {
            "name": display.get("name", weapon_name),
            "itemHash": weapon_hash,
            "roll": roll,
        }