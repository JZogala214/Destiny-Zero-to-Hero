import json
import random
from datetime import datetime, timezone
from pathlib import Path

from api.definitions import DestinyDefinitions

from paths import ABILITIES_JSON, LOOT_TABLES_JSON, SAVE_JSON, MANIFEST_DB, EXOTIC_WEAPONS_JSON

class ProgressionManager:

    ARMOUR_SLOTS = {"Helmet", "Arms", "Chest", "Legs", "Class Item"}

    def __init__(self,
                 abilities_path=ABILITIES_JSON,
                 loot_tables_path=LOOT_TABLES_JSON,
                 save_path=SAVE_JSON,
                 manifest_path=MANIFEST_DB,
                 exotic_weapons_path=EXOTIC_WEAPONS_JSON):

        self.abilities_path = Path(abilities_path)
        self.loot_tables_path = Path(loot_tables_path)
        self.save_path = Path(save_path)
        self.manifest_path = Path(manifest_path)
        self.exotic_weapons_path = Path(exotic_weapons_path)

        self.abilities = self._normalize_ability_classes(self._load_json(self.abilities_path))
        self.raids = self._normalize_raid_tables(self._load_json(self.loot_tables_path))
        self.exotic_weapons = self._load_json(self.exotic_weapons_path) or []
        self.definitions = DestinyDefinitions(self.manifest_path)


    @staticmethod
    def _normalize_ability_classes(abilities):
        """Splits comma-joined class strings (e.g. ["Hunter, Warlock, Titan"])
        into proper lists so class-pool membership checks work."""
        if not isinstance(abilities, list):
            return abilities

        for ability in abilities:
            if not isinstance(ability, dict):
                continue
            classes = ability.get("classes", []) or []
            normalized = []
            for entry in classes:
                for part in str(entry).split(","):
                    cleaned = part.strip()
                    if cleaned and cleaned not in normalized:
                        normalized.append(cleaned)
            ability["classes"] = normalized

        return abilities

    def _load_json(self, path: Path):
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _normalize_raid_tables(self, raw_tables):
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

    def list_raids(self):
        return list(self.raids.keys())

    def get_raid(self, raid_name: str):
        return self.raids.get(raid_name)

    def list_raid_encounters(self, raid_name: str):
        raid = self.get_raid(raid_name) or {}
        encounters = raid.get("encounters", {}) or {}
        return list(encounters.keys())

    def roll_encounter_drop(self, raid_name: str, encounter_name: str):
        raid = self.get_raid(raid_name)
        if not raid:
            raise ValueError(f"Unknown raid: {raid_name}")

        encounter = (raid.get("encounters", {}) or {}).get(encounter_name)
        if not encounter:
            raise ValueError(f"Unknown encounter '{encounter_name}' for raid '{raid_name}'")

        drops = encounter.get("drops", []) or []
        if not drops:
            raise ValueError(f"Encounter '{encounter_name}' has no drops configured")

        return random.choice(drops)

    def has_secret_chest_loot(self, raid_name: str):
        raid = self.get_raid(raid_name)
        if not raid:
            return False
        return bool(raid.get("loot_table"))

    def _encounter_has_configured_drops(self, raid_name: str, encounter_name: str):
        raid = self.get_raid(raid_name)
        if not raid:
            raise ValueError(f"Unknown raid: {raid_name}")

        encounter = (raid.get("encounters", {}) or {}).get(encounter_name)
        if not encounter:
            raise ValueError(f"Unknown encounter '{encounter_name}' for raid '{raid_name}'")

        return bool(encounter.get("drops"))

    def roll_secret_chest_drop(self, raid_name: str):
        raid = self.get_raid(raid_name)
        if not raid:
            raise ValueError(f"Unknown raid: {raid_name}")

        loot_table = raid.get("loot_table", []) or []
        if not loot_table:
            raise ValueError(f"Raid '{raid_name}' has no loot table configured")

        return random.choice(loot_table)

    def _item_name(self, item):
        if isinstance(item, dict):
            return item.get("name", "")
        return str(item)

    def is_ability_name(self, name: str):
        lowered = name.lower().strip()
        return any(self._item_name(ability).lower() == lowered for ability in self.abilities)

    def find_ability_entry(self, name: str, class_name: str | None = None):
        lowered = name.lower().strip()
        for ability in self.abilities:
            if self._item_name(ability).lower() != lowered:
                continue
            if class_name and class_name not in ability.get("classes", []):
                continue
            return ability
        return None

    def get_class_ability_pool(self, class_name: str):
        return [ability for ability in self.abilities if class_name in ability.get("classes", [])]

    def ensure_inventory_structure(self, save_state: dict):
        inventory = save_state.setdefault("inventory", {})
        inventory.setdefault("starterPack", [])

        if "unlockedWeapons" not in inventory or "unlockedAbilities" not in inventory:
            legacy_unlocked = inventory.get("unlocked", []) or []
            unlocked_weapons = []
            unlocked_abilities = []

            for item in legacy_unlocked:
                item_name = self._item_name(item)
                if self.is_ability_name(item_name):
                    ability_entry = item if isinstance(item, dict) else self.find_ability_entry(item_name)
                    if ability_entry and self._item_name(ability_entry).lower() not in {
                        self._item_name(existing).lower() for existing in unlocked_abilities
                    }:
                        unlocked_abilities.append(ability_entry)
                else:
                    unlocked_weapons.append(item if isinstance(item, dict) else item_name)

            if not unlocked_abilities:
                unlocked_abilities = list(inventory.get("starterPack", []))

            inventory["unlockedWeapons"] = unlocked_weapons
            inventory["unlockedAbilities"] = unlocked_abilities

        inventory["unlockedWeapons"] = [
            self.normalize_weapon_reward(weapon)
            for weapon in inventory.get("unlockedWeapons", []) or []
        ]

        inventory["unlocked"] = list(inventory.get("unlockedWeapons", [])) + list(inventory.get("unlockedAbilities", []))
        return inventory

    def sync_inventory_lists(self, save_state: dict):
        inventory = self.ensure_inventory_structure(save_state)
        inventory["unlocked"] = list(inventory.get("unlockedWeapons", [])) + list(inventory.get("unlockedAbilities", []))
        return inventory

    def award_random_ability_reward(self, save_state: dict):
        class_name = save_state.get("profile", {}).get("class")
        if not class_name:
            return None

        inventory = self.ensure_inventory_structure(save_state)
        starter_names = {self._item_name(item).lower() for item in inventory.get("starterPack", [])}
        unlocked_names = {self._item_name(item).lower() for item in inventory.get("unlockedAbilities", [])}

        pool = [
            ability for ability in self.get_class_ability_pool(class_name)
            if self._item_name(ability).lower() not in starter_names | unlocked_names
        ]

        if not pool:
            return None

        reward = random.choice(pool)
        inventory.setdefault("unlockedAbilities", []).append(reward)
        self.sync_inventory_lists(save_state)
        save_state.setdefault("meta", {})["updatedAt"] = datetime.now(timezone.utc).isoformat()
        return reward

    def award_random_exotic_weapon(self, save_state: dict):
        """Rolls a random exotic weapon from the exotic weapons pool (excluding
        exotics already in the armoury) and adds it to the save's armoury.
        Raises ValueError if the manifest can't produce a roll for the chosen
        weapon (e.g. legacy-only versions), or if every exotic is already owned."""
        if not self.exotic_weapons:
            raise ValueError("No exotic weapons are configured.")

        inventory = self.ensure_inventory_structure(save_state)
        owned_names = {
            self._item_name(weapon).lower() for weapon in inventory.get("unlockedWeapons", [])
        }

        pool = [name for name in self.exotic_weapons if name.lower() not in owned_names]
        if not pool:
            raise ValueError("Every exotic weapon is already in the armoury.")

        weapon_name = random.choice(pool)
        reward = self.build_weapon_reward(weapon_name, require_origin_trait=False)

        inventory.setdefault("unlockedWeapons", []).append(reward)
        self.sync_inventory_lists(save_state)
        save_state.setdefault("meta", {})["updatedAt"] = datetime.now(timezone.utc).isoformat()

        return reward

    def grant_all_class_abilities(self, save_state: dict):
        """Debug helper: unlocks every ability in the player's class pool.

        Returns the number of newly-added abilities (0 if none were missing
        or no class is set).
        """
        class_name = save_state.get("profile", {}).get("class")
        if not class_name:
            return 0

        inventory = self.ensure_inventory_structure(save_state)
        unlocked_names = {
            self._item_name(item).lower() for item in inventory.get("unlockedAbilities", [])
        }

        added = 0
        for ability in self.get_class_ability_pool(class_name):
            if self._item_name(ability).lower() in unlocked_names:
                continue
            inventory.setdefault("unlockedAbilities", []).append(ability)
            unlocked_names.add(self._item_name(ability).lower())
            added += 1

        if added:
            self.sync_inventory_lists(save_state)
            save_state.setdefault("meta", {})["updatedAt"] = datetime.now(timezone.utc).isoformat()

        return added

    def build_weapon_reward(self, weapon_name: str, require_origin_trait: bool = True):
        return self.definitions.build_weapon_roll(weapon_name, require_origin_trait=require_origin_trait)

    def normalize_weapon_reward(self, weapon):
        if isinstance(weapon, dict):
            if weapon.get("roll"):
                weapon["roll"] = [self._normalize_weapon_roll_entry(entry) for entry in weapon.get("roll", []) or []]
                return weapon

            legacy_traits = weapon.get("traits", []) or []
            if legacy_traits:
                weapon_name = weapon.get("name", "")
                return {
                    "name": weapon_name,
                    "itemHash": weapon.get("itemHash"),
                    "roll": [self._normalize_weapon_roll_entry({
                        "slot": self.definitions.WEAPON_ROLL_SLOTS[index] if index < len(self.definitions.WEAPON_ROLL_SLOTS) else f"Trait {index + 1}",
                        "perk": trait,
                    }) for index, trait in enumerate(legacy_traits)],
                }

            return weapon

        weapon_name = self._item_name(weapon).strip()
        if not weapon_name:
            return weapon

        if weapon_name in self.ARMOUR_SLOTS:
            return weapon_name

        return self.build_weapon_reward(weapon_name)

    def _normalize_weapon_roll_entry(self, entry: dict):
        if not isinstance(entry, dict):
            return entry

        perk_hash = entry.get("perkHash")
        perk_name = entry.get("perk")
        if perk_hash or not perk_name:
            return entry

        perk_def = self.definitions.find_item_by_name(perk_name) or self.definitions.search_item(perk_name)
        if perk_def:
            entry["perkHash"] = perk_def.get("hash")

        return entry

    def init_save_state(self, player_class: str, raid_name: str | None = None):
        player_class = player_class.capitalize()
        starter_pack = self.generate_starter_pack(player_class)

        
        state = {
            "meta": {
                "version": 1,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
            "profile": {
                "class": player_class,
            },
            "inventory": {
                "starterPack": starter_pack,
                "unlockedWeapons": [],
                "unlockedAbilities": starter_pack.copy(),
                "unlocked": starter_pack.copy(),
                "currentSubclass": None,
            },
            "raids": {},
        }

        if raid_name:
            state["raids"][raid_name] = self._build_raid_state(raid_name)

        return state

    def _build_raid_state(self, raid_name: str):
        raid = self.get_raid(raid_name)
        if not raid:
            raise ValueError(f"Unknown raid: {raid_name}")

        encounters = {}
        for encounter_name in self.list_raid_encounters(raid_name):
            encounters[encounter_name] = {
                "completed": False,
                "challenged": False,
                "clearedAt": None,
                "challengedAt": None,
                "drops": [],
            }

        return {
            "completed": False,
            "completedAt": None,
            "encounters": encounters,
        }

    def ensure_raid_state(self, save_state: dict, raid_name: str):
        save_state.setdefault("raids", {})
        if raid_name not in save_state["raids"]:
            save_state["raids"][raid_name] = self._build_raid_state(raid_name)
        return save_state["raids"][raid_name]

    def complete_encounter(self, save_state: dict, raid_name: str, encounter_name: str):
        drop = (
            self.roll_encounter_drop(raid_name, encounter_name)
            if self._encounter_has_configured_drops(raid_name, encounter_name)
            else None
        )
        encounter_state, reward = self._complete_encounter_with_drop(
            save_state,
            raid_name,
            encounter_name,
            drop,
            action_key="completed",
            timestamp_key="clearedAt",
        )
        self.sync_inventory_lists(save_state)
        return encounter_state, reward

    def challenge_encounter(self, save_state: dict, raid_name: str, encounter_name: str):
        drop = (
            self.roll_encounter_drop(raid_name, encounter_name)
            if self._encounter_has_configured_drops(raid_name, encounter_name)
            else None
        )
        encounter_state, reward = self._complete_encounter_with_drop(
            save_state,
            raid_name,
            encounter_name,
            drop,
            action_key="challenged",
            timestamp_key="challengedAt",
        )
        self.sync_inventory_lists(save_state)
        return encounter_state, reward

    def open_secret_chest(self, save_state: dict, raid_name: str):
        drop = self.roll_secret_chest_drop(raid_name)
        timestamp = datetime.now(timezone.utc).isoformat()

        raid_state = self.ensure_raid_state(save_state, raid_name)
        self.ensure_inventory_structure(save_state)
        chest_history = raid_state.setdefault("secretChestOpens", [])
        chest_history.append({
            "openedAt": timestamp,
            "drop": drop,
        })

        reward = drop

        if drop not in self.ARMOUR_SLOTS:
            inventory = save_state.setdefault("inventory", {})
            unlocked_weapons = inventory.setdefault("unlockedWeapons", [])
            reward = self.build_weapon_reward(drop)
            unlocked_weapons.append(reward)

        self.sync_inventory_lists(save_state)

        save_state.setdefault("meta", {})["updatedAt"] = timestamp

        return reward

    def _complete_encounter_with_drop(self, save_state: dict, raid_name: str, encounter_name: str, drop: str | None, action_key: str, timestamp_key: str):
        raid_state = self.ensure_raid_state(save_state, raid_name)
        encounter_state = raid_state["encounters"].get(encounter_name)
        if not encounter_state:
            raise ValueError(f"Unknown encounter '{encounter_name}' for raid '{raid_name}'")

        if encounter_state.get(action_key):
            return encounter_state, None

        timestamp = datetime.now(timezone.utc).isoformat()

        # Build the reward first: if roll generation fails (e.g. the
        # origin-trait guard rejects a legacy-only weapon), the encounter
        # must not be marked complete. A None drop means this encounter has
        # no configured loot (ability-only raid) - nothing to roll.
        reward = None
        if drop is not None:
            reward = self.build_weapon_reward(drop) if drop not in self.ARMOUR_SLOTS else drop

        self.ensure_inventory_structure(save_state)
        encounter_state[action_key] = True
        encounter_state[timestamp_key] = timestamp

        if reward is not None:
            encounter_state["drops"].append(reward)

            if drop not in self.ARMOUR_SLOTS:
                inventory = save_state.setdefault("inventory", {})
                unlocked_weapons = inventory.setdefault("unlockedWeapons", [])
                unlocked_weapons.append(reward)

        raid_state["completed"] = all(
            encounter.get("completed", False)
            for encounter in raid_state["encounters"].values()
        )
        if raid_state["completed"] and not raid_state["completedAt"]:
            raid_state["completedAt"] = timestamp

        save_state.setdefault("meta", {})["updatedAt"] = timestamp

        return encounter_state, reward

    def serialize_save_state(self, save_state: dict):
        return json.dumps(save_state, indent=2)

    def generate_starter_pack(self, class_name: str):
        """Generate a starter pack of 10 abilities for the given class.

        Rules:
        - 1 random Super ability for the class
        - 1 random ability matching the Super's element (and for the class)
        - 8 other random abilities (class-matching), no duplicates
        """

        class_name = class_name.capitalize()

        pool = [a for a in self.abilities if class_name in a.get("classes", [])]

        if not pool:
            raise ValueError(f"No abilities found for class {class_name}")

        supers = [a for a in pool if a.get("type") == "super"]

        if not supers:
            raise ValueError(f"No supers defined for class {class_name}")

        chosen = []

        super_choice = random.choice(supers)
        chosen.append(super_choice)

        super_element = super_choice.get("element")

        # pick one ability that matches the super element (and is not the super)
        element_matches = [a for a in pool if a.get("element") == super_element and a.get("type") != "super"]

        if element_matches:
            element_choice = random.choice(element_matches)
            chosen.append(element_choice)

        # pick remaining abilities
        remaining_pool = [a for a in pool if a not in chosen]

        needed = 10 - len(chosen)

        if needed > len(remaining_pool):
            # allow repeats only if pool is too small
            additional = random.choices(remaining_pool, k=needed)
        else:
            additional = random.sample(remaining_pool, k=needed)

        chosen.extend(additional)

        return chosen

    def save_progress(self, data: dict):
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_progress(self):
        if not self.save_path.exists():
            default_save = self.create_default_save()
            self.save_progress(default_save)
            return default_save

        with open(self.save_path, "r", encoding="utf-8") as f:
            return json.load(f)
        
    def create_default_save(self):
        return {
            "meta": {
                "version": 1,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            },
            "profile": {
                "class": None,
            },
            "inventory": {
                "starterPack": [],
                "unlockedWeapons": [],
                "unlockedAbilities": [],
                "unlocked": [],
                "currentSubclass": None,
            },
            "raids": {},
        }


if __name__ == "__main__":
    print("ProgressionManager loaded successfully.")
    