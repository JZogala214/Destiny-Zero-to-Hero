import os

API_KEY = os.environ.get("BUNGIE_API_KEY", "")

BUNGIE_API = "https://www.bungie.net/Platform"
BUNGIE_ROOT = "https://www.bungie.net"


def require_api_key() -> str:
    if not API_KEY:
        raise RuntimeError(
            "Missing Bungie API key. Set the BUNGIE_API_KEY environment variable."
        )
    return API_KEY
