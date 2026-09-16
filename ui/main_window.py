from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QFrame,
    QTabWidget,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from api.definitions import DestinyDefinitions
from progression import ProgressionManager
from services.icon_service import IconService
from paths import ARMOUR_EMOJI_IMAGE


class MainWindow(QWidget):

    ARMOUR_SLOTS = {"Helmet", "Arms", "Chest", "Legs", "Class Item"}
    ICON_SIZE = 160
    ARMOUR_PLACEHOLDER_PATH = ARMOUR_EMOJI_IMAGE

    def __init__(self, manifest_path):
        super().__init__()

        self.setWindowTitle("Destiny Zero to Hero")
        self.resize(980, 720)
        self.setStyleSheet(
            """
            QPushButton {
                background: #39424e;
                color: #f4f4f4;
                border: 1px solid #2a313b;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background: #4a5564;
            }
            QPushButton:pressed {
                background: #242b33;
            }
            QPushButton:disabled {
                background: #80868e;
                color: #d9d9d9;
            }
            """
        )

        self.defs = DestinyDefinitions(manifest_path)
        self.progression = ProgressionManager(manifest_path=manifest_path)

        self.icon_service = IconService()
        self.save_state = None
        self.encounter_rows = {}
        self.armoury_display_label = None
        self.reward_icon_label = None

        root = QVBoxLayout()

        header = QHBoxLayout()
        self.class_combo = QComboBox()
        self.class_combo.addItems(["Hunter", "Titan", "Warlock"])
        header.addWidget(QLabel("Class"))
        header.addWidget(self.class_combo)

        self.raid_combo = QComboBox()
        self.raid_combo.addItems(self.progression.list_raids())
        self.raid_combo.currentTextChanged.connect(self.on_raid_selected)
        header.addWidget(QLabel("Raid"))
        header.addWidget(self.raid_combo)

        root.addLayout(header)

        actions = QHBoxLayout()
        new_run_button = QPushButton("New Run")
        new_run_button.clicked.connect(self.start_new_run)
        actions.addWidget(new_run_button)

        save_button = QPushButton("Save Progress")
        save_button.clicked.connect(self.save_current_progress)
        actions.addWidget(save_button)

        load_button = QPushButton("Load Progress")
        load_button.clicked.connect(self.load_saved_progress)
        actions.addWidget(load_button)

        root.addLayout(actions)

        self.summary_label = QLabel("Start a new run to see your armoury and raid progress.")
        root.addWidget(self.summary_label)

        tabs = QTabWidget()

        raid_tab = QWidget()
        raid_layout = QVBoxLayout(raid_tab)
        raid_layout.setContentsMargins(0, 0, 0, 0)
        raid_layout.setSpacing(10)

        raid_layout.addWidget(QLabel("Raid Progress"))

        self.encounter_scroll = QScrollArea()
        self.encounter_scroll.setWidgetResizable(True)
        self.encounter_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.encounter_container = QWidget()
        self.encounter_list_layout = QVBoxLayout(self.encounter_container)
        self.encounter_list_layout.setContentsMargins(0, 0, 0, 0)
        self.encounter_list_layout.setSpacing(8)
        self.encounter_scroll.setWidget(self.encounter_container)
        raid_layout.addWidget(self.encounter_scroll)

        reward_panel = QFrame()
        reward_panel.setObjectName("rewardPanel")
        # Dark grey backdrop behind the reward + perk icons. Scoped by
        # objectName so it doesn't bleed onto other widgets.
        reward_panel.setStyleSheet(
            "QFrame#rewardPanel { background: #2b2b2b; border-radius: 8px; }"
        )
        reward_display_row = QHBoxLayout(reward_panel)
        reward_display_row.setContentsMargins(10, 10, 10, 10)
        self.reward_icon_label = QLabel()
        self.reward_icon_label.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self.reward_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reward_display_row.addWidget(self.reward_icon_label)

        self.reward_perks_layout = QHBoxLayout()
        self.reward_perks_layout.setSpacing(6)
        reward_display_row.addLayout(self.reward_perks_layout)
        reward_display_row.addStretch(1)
        raid_layout.addWidget(reward_panel)

        self.reward_label = QLabel("Latest reward will appear here.")
        self.reward_label.setWordWrap(True)
        raid_layout.addWidget(self.reward_label)

        armoury_tab = QWidget()
        armoury_layout = QVBoxLayout(armoury_tab)
        armoury_layout.setContentsMargins(0, 0, 0, 0)
        armoury_layout.setSpacing(10)

        weapons_group, weapons_body = self._build_collapsible_section("Weapons", True)
        self.weapon_list = QListWidget()
        self.weapon_list.itemClicked.connect(self.show_selected_weapon_icon)
        weapons_body.addWidget(self.weapon_list)

        armoury_buttons = QHBoxLayout()
        delete_button = QPushButton("Delete Selected Weapon")
        delete_button.clicked.connect(self.delete_selected_weapon)
        armoury_buttons.addWidget(delete_button)
        weapons_body.addLayout(armoury_buttons)

        armoury_layout.addWidget(weapons_group)

        abilities_group, abilities_body = self._build_collapsible_section("Abilities", True)
        self.ability_list = QListWidget()
        self.ability_list.itemClicked.connect(self.show_selected_ability_icon)
        abilities_body.addWidget(self.ability_list)
        armoury_layout.addWidget(abilities_group)

        armoury_panel = QFrame()
        armoury_panel.setObjectName("rewardPanel")
        # Same dark grey backdrop as the Raid tab's reward area, for
        # visual consistency.
        armoury_panel.setStyleSheet(
            "QFrame#rewardPanel { background: #2b2b2b; border-radius: 8px; }"
        )
        armoury_display_row = QHBoxLayout(armoury_panel)
        armoury_display_row.setContentsMargins(10, 10, 10, 10)
        self.armoury_display_label = QLabel()
        self.armoury_display_label.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self.armoury_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        armoury_display_row.addWidget(self.armoury_display_label)

        self.armoury_perks_layout = QHBoxLayout()
        self.armoury_perks_layout.setSpacing(6)
        armoury_display_row.addLayout(self.armoury_perks_layout)
        armoury_display_row.addStretch(1)
        armoury_layout.addWidget(armoury_panel)

        exotics_tab = QWidget()
        exotics_layout = QVBoxLayout(exotics_tab)
        exotics_layout.setContentsMargins(0, 0, 0, 0)
        exotics_layout.setSpacing(10)

        exotics_layout.addWidget(QLabel("Exotic Weapons"))

        roll_exotic_button = QPushButton("Roll Random Exotic")
        roll_exotic_button.clicked.connect(self.roll_random_exotic)
        exotics_layout.addWidget(roll_exotic_button)

        exotics_panel = QFrame()
        exotics_panel.setObjectName("rewardPanel")
        exotics_panel.setStyleSheet(
            "QFrame#rewardPanel { background: #2b2b2b; border-radius: 8px; }"
        )
        exotics_display_row = QHBoxLayout(exotics_panel)
        exotics_display_row.setContentsMargins(10, 10, 10, 10)
        self.exotics_display_label = QLabel()
        self.exotics_display_label.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self.exotics_display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        exotics_display_row.addWidget(self.exotics_display_label)

        self.exotics_perks_layout = QHBoxLayout()
        self.exotics_perks_layout.setSpacing(6)
        exotics_display_row.addLayout(self.exotics_perks_layout)
        exotics_display_row.addStretch(1)
        exotics_layout.addWidget(exotics_panel)

        self.exotics_result_label = QLabel("Roll to reveal an exotic weapon.")
        self.exotics_result_label.setWordWrap(True)
        exotics_layout.addWidget(self.exotics_result_label)
        exotics_layout.addStretch(1)

        options_tab = QWidget()
        options_layout = QVBoxLayout(options_tab)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(10)

        options_layout.addWidget(QLabel("Debug Tools"))

        grant_abilities_button = QPushButton("Grant All Class Abilities")
        grant_abilities_button.clicked.connect(self.grant_all_abilities)
        options_layout.addWidget(grant_abilities_button)

        options_hint = QLabel(
            "Unlocks every ability available to your current class. "
            "Start or load a run first."
        )
        options_hint.setWordWrap(True)
        options_layout.addWidget(options_hint)
        options_layout.addStretch(1)

        tabs.addTab(raid_tab, "Raid")
        tabs.addTab(armoury_tab, "Armoury")
        tabs.addTab(exotics_tab, "Exotics")
        tabs.addTab(options_tab, "Options")

        root.addWidget(tabs)

        self.setLayout(root)

        self.on_raid_selected(self.raid_combo.currentText())
        self.load_saved_progress(silent=True)

    # -- helpers ---------------------------------------------------------

    def _current_raid_name(self):
        return self.raid_combo.currentText().strip()

    def _current_class_name(self):
        return self.class_combo.currentText().strip()

    @staticmethod
    def _drop_name(drop):
        """Weapon drops are dicts ({name, itemHash, roll}); armour drops are
        plain slot-name strings. Always display/look up by name."""
        if isinstance(drop, dict):
            return drop.get("name", "Unknown")
        return str(drop)

    @staticmethod
    def _drop_roll_text(drop):
        """Formats a weapon drop's rolled perks, e.g.
        'Arrowhead Brake / Accurized Rounds / Rapid Hit / Kill Clip'."""
        if not isinstance(drop, dict):
            return ""

        perks = [entry.get("perk", "") for entry in drop.get("roll", []) or []]
        perks = [perk for perk in perks if perk]
        return " / ".join(perks)

    def _describe_drop(self, drop):
        name = self._drop_name(drop)
        roll_text = self._drop_roll_text(drop)
        if roll_text:
            return f"{name} ({roll_text})"
        return name

    def _reward_drop_text(self, drop):
        """Reward text for a drop. Armour pieces are never named - the player
        just applies the drop they received - so we avoid 'You got: <slot>'."""
        if self._drop_name(drop) in self.ARMOUR_SLOTS:
            return "armour (use the drop you received)"
        return self._describe_drop(drop)

    def _combine_reward_text(self, drop, ability_reward):
        """Builds the reward summary for an encounter/challenge completion.
        Some raids have no configured item drops (ability-only), so `drop`
        may be None - the ability, if any, is then the whole reward."""
        item_text = self._reward_drop_text(drop) if drop is not None else None
        ability_name = ability_reward.get("name", "Unknown") if ability_reward else None

        if item_text and ability_name:
            return f"{item_text} and {ability_name}"
        if item_text:
            return item_text
        if ability_name:
            return ability_name
        return "nothing new (already unlocked everything available)"

    def _display_encounter_reward(self, drop):
        if drop is not None:
            self._set_icon_for_drop_on_label(drop, self.reward_icon_label)
            self._set_perk_icons(drop, self.reward_perks_layout)
        else:
            self.reward_icon_label.clear()
            self._clear_perk_icons(self.reward_perks_layout)

    PERK_ICON_SIZE = 44

    def _clear_perk_icons(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _set_perk_icons(self, drop, layout):
        """Renders one small icon per rolled perk (traits, origin trait)
        beside the weapon icon. Armour and unknown perks render nothing."""
        self._clear_perk_icons(layout)

        if not isinstance(drop, dict):
            return

        for entry in drop.get("roll", []) or []:
            perk_hash = entry.get("perkHash")
            if not perk_hash:
                continue

            perk_def = self.defs.get_definition("DestinyInventoryItemDefinition", perk_hash)
            if not perk_def:
                continue

            icon_path = (perk_def.get("displayProperties", {}) or {}).get("icon")
            if not icon_path:
                continue

            local_icon = self.icon_service.get_icon(icon_path)
            if not local_icon:
                continue

            pixmap = QPixmap(local_icon)
            if pixmap.isNull():
                continue

            label = QLabel()
            label.setFixedSize(self.PERK_ICON_SIZE, self.PERK_ICON_SIZE)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setPixmap(
                pixmap.scaled(
                    self.PERK_ICON_SIZE,
                    self.PERK_ICON_SIZE,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            label.setToolTip(f"{entry.get('slot', 'Perk')}: {entry.get('perk', '')}")
            layout.addWidget(label)

    def _set_icon_for_name(self, name):
        self._set_icon_for_name_on_label(name, self.reward_icon_label)

    def _set_icon_for_name_on_label(self, name, target_label):
        if name in self.ARMOUR_SLOTS:
            self._set_placeholder_icon(target_label)
            return

        item = self.defs.search_item(name)
        self._set_icon_from_item(item, target_label)

    def _set_icon_for_drop_on_label(self, drop, target_label):
        """Weapon drops carry an itemHash from the manifest roll (see
        DestinyDefinitions.build_weapon_roll). Looking it up directly avoids
        the ambiguity of name search, which can match the wrong manifest
        entry when several items share a display name (e.g. a weapon's
        quest/catalyst/ornament variants)."""
        if isinstance(drop, dict) and drop.get("itemHash"):
            item = self.defs.get_definition("DestinyInventoryItemDefinition", drop["itemHash"])
            if item:
                self._set_icon_from_item(item, target_label)
                return

        self._set_icon_for_name_on_label(self._drop_name(drop), target_label)

    def _set_icon_from_item(self, item, target_label):
        if not item:
            target_label.clear()
            return

        display = item.get("displayProperties", {})
        icon_path = display.get("icon")
        if not icon_path:
            target_label.clear()
            return

        local_icon = self.icon_service.get_icon(icon_path)
        if not local_icon:
            target_label.clear()
            return

        pixmap = QPixmap(local_icon)
        if pixmap.isNull():
            target_label.clear()
            return

        target_label.setPixmap(
            pixmap.scaled(
                self.ICON_SIZE,
                self.ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_placeholder_icon(self, target_label):
        if not self.ARMOUR_PLACEHOLDER_PATH.exists():
            target_label.clear()
            return

        pixmap = QPixmap(str(self.ARMOUR_PLACEHOLDER_PATH))
        target_label.setPixmap(
            pixmap.scaled(
                self.ICON_SIZE,
                self.ICON_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _ability_name(self, ability):
        if isinstance(ability, dict):
            return ability.get("name", "Unknown")
        return str(ability)

    def _ability_payload(self, ability):
        if isinstance(ability, dict):
            return ability
        return {"name": str(ability)}

    def _build_collapsible_section(self, title, expanded=True):
        container = QFrame()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)

        header_button = QPushButton(f"{'▼' if expanded else '▶'} {title}")
        header_button.setCheckable(True)
        header_button.setChecked(expanded)
        header_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header_button.setStyleSheet(
            """
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #2a313b;
                border-radius: 6px;
                background: #2f3842;
                color: #f4f4f4;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #3b4551;
            }
            QPushButton:checked {
                background: #242b33;
            }
            """
        )

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(8)

        def toggle_body(checked):
            body.setVisible(checked)
            header_button.setText(f"{'▼' if checked else '▶'} {title}")

        header_button.toggled.connect(toggle_body)
        toggle_body(expanded)

        container_layout.addWidget(header_button)
        container_layout.addWidget(body)

        return container, body_layout

    # -- list population --------------------------------------------------

    def _populate_weapon_list(self, weapons):
        self.weapon_list.clear()

        for weapon in weapons:
            name = self._drop_name(weapon)
            roll_text = self._drop_roll_text(weapon)

            label = f"{name}  —  {roll_text}" if roll_text else name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, weapon)

            if roll_text:
                item.setToolTip(roll_text)

            self.weapon_list.addItem(item)

    def _populate_ability_list(self, abilities):
        self.ability_list.clear()

        for ability in abilities:
            name = self._ability_name(ability)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, self._ability_payload(ability))
            self.ability_list.addItem(item)

    def _populate_armoury_lists(self):
        if not self.save_state:
            self.weapon_list.clear()
            self.ability_list.clear()
            return

        inventory = self.progression.ensure_inventory_structure(self.save_state)
        self._populate_weapon_list(inventory.get("unlockedWeapons", []))
        self._populate_ability_list(inventory.get("unlockedAbilities", []))

    def _set_armoury_display(self, name):
        self._set_icon_for_name_on_label(name, self.armoury_display_label)

    def grant_all_abilities(self):
        """Debug tool: unlocks every ability for the current run's class."""
        if not self.save_state:
            QMessageBox.information(self, "Options", "Start or load a run first.")
            return

        added = self.progression.grant_all_class_abilities(self.save_state)
        self._populate_armoury_lists()

        class_name = self.save_state.get("profile", {}).get("class", "your class")
        if added:
            QMessageBox.information(
                self, "Options", f"Granted {added} new {class_name} ability(s)."
            )
        else:
            QMessageBox.information(
                self, "Options", f"All {class_name} abilities are already unlocked."
            )

    def roll_random_exotic(self):
        if not self.save_state:
            QMessageBox.information(self, "Exotics", "Start or load a run first.")
            return

        try:
            reward = self.progression.award_random_exotic_weapon(self.save_state)
        except ValueError as exc:
            QMessageBox.warning(self, "Exotics", str(exc))
            return

        self.exotics_result_label.setText(f"You rolled: {self._describe_drop(reward)}")
        self._set_icon_for_drop_on_label(reward, self.exotics_display_label)
        self._set_perk_icons(reward, self.exotics_perks_layout)

        self._refresh_unlock_list_from_save()

    def _ensure_active_raid_state(self, raid_name):
        if not self.save_state:
            self.save_state = self.progression.init_save_state(self._current_class_name(), raid_name)
            self.summary_label.setText(f"New {self._current_class_name()} run started on {raid_name}.")
            self._populate_armoury_lists()
            return self.save_state["raids"][raid_name]

        return self.progression.ensure_raid_state(self.save_state, raid_name)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self._clear_layout(child_layout)

    # -- encounter rows ----------------------------------------------------

    def _build_encounter_row(self, encounter_name, encounter_state):
        row_widget = QFrame()
        row_widget.setFrameShape(QFrame.Shape.StyledPanel)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(10)

        completed = encounter_state.get("completed", False)
        challenged = encounter_state.get("challenged", False)
        status_text = "".join([
            "✓" if completed else "",
            "★" if challenged else "",
        ])
        tick_label = QLabel(status_text)
        tick_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tick_label.setFixedWidth(28)
        tick_label.setStyleSheet("font-weight: 700; color: #2e7d32;")
        row_layout.addWidget(tick_label)

        name_label = QLabel(encounter_name)
        row_layout.addWidget(name_label)
        row_layout.addStretch(1)

        button = QPushButton("Complete" if not completed else "Completed")
        button.setEnabled(not completed)
        button.clicked.connect(lambda checked=False, name=encounter_name: self.complete_selected_encounter(name))
        row_layout.addWidget(button)

        challenge_button = QPushButton("Challenge" if not challenged else "Completed")
        challenge_button.setEnabled(not challenged)
        challenge_button.clicked.connect(lambda checked=False, name=encounter_name: self.challenge_selected_encounter(name))
        row_layout.addWidget(challenge_button)

        self.encounter_list_layout.addWidget(row_widget)
        self.encounter_rows[encounter_name] = {
            "row": row_widget,
            "tick": tick_label,
            "button": button,
            "challenge_button": challenge_button,
            "label": name_label,
        }

    def _build_secret_chest_row(self):
        row_widget = QFrame()
        row_widget.setFrameShape(QFrame.Shape.StyledPanel)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(10)

        label = QLabel("Secret Chest")
        row_layout.addWidget(label)
        row_layout.addStretch(1)

        button = QPushButton("Open Secret Chest")
        button.clicked.connect(self.open_secret_chest)
        row_layout.addWidget(button)

        self.encounter_list_layout.addWidget(row_widget)
        self.encounter_rows["Secret Chest"] = {
            "row": row_widget,
            "button": button,
            "label": label,
        }

    def refresh_encounters(self, raid_name):
        self._clear_layout(self.encounter_list_layout)
        self.encounter_rows = {}

        if not raid_name:
            placeholder = QLabel("Pick a raid to begin.")
            placeholder.setStyleSheet("color: #666;")
            self.encounter_list_layout.addWidget(placeholder)
            return

        raid_state = self._ensure_active_raid_state(raid_name)

        encounters = raid_state.get("encounters", {}) or {}
        for encounter_name, encounter_state in encounters.items():
            self._build_encounter_row(encounter_name, encounter_state)

        if self.progression.has_secret_chest_loot(raid_name):
            self._build_secret_chest_row()

    def on_raid_selected(self, raid_name):
        if not raid_name:
            self.refresh_encounters(raid_name)
            return

        self._ensure_active_raid_state(raid_name)
        self.refresh_encounters(raid_name)

    # -- top-level actions ---------------------------------------------------

    def start_new_run(self):
        player_class = self._current_class_name()
        raid_name = self._current_raid_name()

        self.save_state = self.progression.init_save_state(player_class, raid_name)
        self.summary_label.setText(f"New {player_class} run started on {raid_name}.")

        self._populate_armoury_lists()

        self.refresh_encounters(self._current_raid_name())
        first_ability = self.ability_list.item(0).text() if self.ability_list.count() else ""
        self._set_armoury_display(first_ability)

    def load_saved_progress(self, silent=False):
        self.save_state = self.progression.load_progress()
        if not self.save_state:
            if not silent:
                QMessageBox.information(self, "Load Progress", "No saved progress found yet.")
            return

        player_class = self.save_state.get("profile", {}).get("class", self._current_class_name())
        index = self.class_combo.findText(player_class)
        if index >= 0:
            self.class_combo.setCurrentIndex(index)

        self._populate_armoury_lists()

        current_raid = next(iter(self.save_state.get("raids", {}).keys()), self._current_raid_name())
        raid_index = self.raid_combo.findText(current_raid)
        if raid_index >= 0:
            self.raid_combo.setCurrentIndex(raid_index)

        self.refresh_encounters(self._current_raid_name())
        self.summary_label.setText("Loaded saved progress.")

    def save_current_progress(self):
        if not self.save_state:
            QMessageBox.information(self, "Save Progress", "Start or load a run first.")
            return

        self.progression.save_progress(self.save_state)
        QMessageBox.information(self, "Save Progress", "Progress saved to data/save.json.")

    def complete_selected_encounter(self, encounter_name=None):
        if not self.save_state:
            QMessageBox.information(self, "Encounter", "Start or load a run first.")
            return

        raid_name = self._current_raid_name()
        if not encounter_name:
            QMessageBox.information(self, "Encounter", "Pick an encounter first.")
            return

        try:
            _, drop = self.progression.complete_encounter(self.save_state, raid_name, encounter_name)
        except ValueError as exc:
            QMessageBox.warning(self, "Encounter", str(exc))
            return

        ability_reward = self.progression.award_random_ability_reward(self.save_state)
        reward_text = self._combine_reward_text(drop, ability_reward)

        self.reward_label.setText(f"Encounter reward: {reward_text}")
        self._display_encounter_reward(drop)

        self._refresh_unlock_list_from_save()
        self.refresh_encounters(raid_name)

    def challenge_selected_encounter(self, encounter_name=None):
        if not self.save_state:
            QMessageBox.information(self, "Encounter", "Start or load a run first.")
            return

        raid_name = self._current_raid_name()
        if not encounter_name:
            QMessageBox.information(self, "Encounter", "Pick an encounter first.")
            return

        try:
            _, drop = self.progression.challenge_encounter(self.save_state, raid_name, encounter_name)
        except ValueError as exc:
            QMessageBox.information(self, "Challenge", str(exc))
            return

        ability_reward = self.progression.award_random_ability_reward(self.save_state)
        reward_text = self._combine_reward_text(drop, ability_reward)

        self.reward_label.setText(f"Challenge reward: {reward_text}")
        self._display_encounter_reward(drop)

        self._refresh_unlock_list_from_save()
        self.refresh_encounters(raid_name)

    def open_secret_chest(self):
        if not self.save_state:
            QMessageBox.information(self, "Secret Chest", "Start or load a run first.")
            return

        raid_name = self._current_raid_name()

        try:
            reward = self.progression.open_secret_chest(self.save_state, raid_name)
        except ValueError as exc:
            QMessageBox.information(self, "Secret Chest", str(exc))
            return

        reward_text = self._reward_drop_text(reward)

        self.reward_label.setText(f"Secret chest reward: {reward_text}")
        self._set_icon_for_drop_on_label(reward, self.reward_icon_label)
        self._set_perk_icons(reward, self.reward_perks_layout)
        self._refresh_unlock_list_from_save()
        self._populate_armoury_lists()

    def _refresh_unlock_list_from_save(self):
        if not self.save_state:
            return

        self._populate_armoury_lists()

    def delete_selected_weapon(self):
        if not self.save_state:
            QMessageBox.information(self, "Armoury", "Start or load a run first.")
            return

        current_row = self.weapon_list.currentRow()
        current_item = self.weapon_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "Armoury", "Select a weapon to delete first.")
            return

        inventory = self.progression.ensure_inventory_structure(self.save_state)
        unlocked_weapons = inventory.setdefault("unlockedWeapons", [])
        if current_row < 0 or current_row >= len(unlocked_weapons):
            QMessageBox.information(self, "Armoury", "Could not delete the selected weapon.")
            return

        unlocked_weapons.pop(current_row)
        self.progression.sync_inventory_lists(self.save_state)
        self._refresh_unlock_list_from_save()
        self.armoury_display_label.clear()
        self._clear_perk_icons(self.armoury_perks_layout)

    def show_selected_weapon_icon(self, item):
        weapon = item.data(Qt.ItemDataRole.UserRole)
        self._set_icon_for_drop_on_label(weapon, self.armoury_display_label)
        self._set_perk_icons(weapon, self.armoury_perks_layout)

    def show_selected_ability_icon(self, item):
        self._clear_perk_icons(self.armoury_perks_layout)
        ability = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(ability, dict):
            self._set_armoury_display(item.text())
            return

        self._set_armoury_display(ability.get("name", item.text()))