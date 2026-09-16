"""
Intended for develpoer use to download Bungie's SQLite world content manifest.

The SQLite database contains every definition table (inventory items,
plug sets, etc.), which the weapon roll generator needs. A version file
is kept alongside it so the download is skipped when already current.
"""
import io
import zipfile
from pathlib import Path

import requests

from api.bungie import get_manifest
from config import BUNGIE_ROOT

from paths import APPDATA_DIR

MANIFEST_DB_PATH = APPDATA_DIR / "manifest.db"


class ManifestManager:

    def __init__(self, db_path: Path = MANIFEST_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.version_path = self.db_path.with_name("version.txt")

    def is_update_needed(self, version: str) -> bool:
        if not self.db_path.exists():
            return True

        if not self.version_path.exists():
            return True

        return self.version_path.read_text(encoding="utf-8").strip() != version

    def download_manifest(self) -> Path:
        data = get_manifest()["Response"]
        version = data["version"]

        if not self.is_update_needed(version):
            return self.db_path

        path = data["mobileWorldContentPaths"]["en"]

        print("Downloading manifest database...")
        response = requests.get(f"{BUNGIE_ROOT}{path}", timeout=300)
        response.raise_for_status()

        print("Extracting database...")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            if not names:
                raise RuntimeError("Could not find database inside manifest archive")

            with archive.open(names[0]) as db_file:
                self.db_path.write_bytes(db_file.read())

        self.version_path.write_text(version, encoding="utf-8")

        print("Saved manifest database")
        return self.db_path
