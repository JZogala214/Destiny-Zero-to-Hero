from pathlib import Path
import requests

from paths import CACHE_DIR

# Magic bytes for the image formats Bungie's manifest serves. Used to detect
# and discard corrupt cache entries (e.g. an HTML error page saved from a
# failed download in an older version of this code, before response
# validation was added) so they get re-downloaded instead of being served
# forever as a broken/blank icon.
_IMAGE_SIGNATURES = (
    b"\xff\xd8\xff",  # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"GIF8",  # GIF
)


class IconService:

    BASE_URL = "https://www.bungie.net"

    def __init__(self):
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)

    @staticmethod
    def _looks_like_image(data: bytes) -> bool:
        return bool(data) and any(data.startswith(sig) for sig in _IMAGE_SIGNATURES)

    def get_icon(self, icon_path):
        filename = Path(icon_path).name
        local_file = self.cache_dir / filename

        if local_file.exists():
            if self._looks_like_image(local_file.read_bytes()):
                return str(local_file)
            # Cached file is corrupt (e.g. from a failed download) - discard
            # it and fall through to re-download.
            local_file.unlink()

        response = requests.get(self.BASE_URL + icon_path, timeout=30)
        if response.status_code != 200 or not self._looks_like_image(response.content):
            return None

        local_file.write_bytes(response.content)
        return str(local_file)