"""Thin helpers for talking to the Bungie Platform API."""
import requests

from config import BUNGIE_API, require_api_key


def bungie_get(endpoint: str) -> dict:
    """GET a Bungie Platform endpoint (e.g. "/Destiny2/Manifest/")."""
    response = requests.get(
        f"{BUNGIE_API}{endpoint}",
        headers={"X-API-Key": require_api_key()},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_manifest() -> dict:
    return bungie_get("/Destiny2/Manifest/")
