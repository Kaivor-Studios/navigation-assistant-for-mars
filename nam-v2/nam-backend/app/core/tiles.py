"""Tile proxy: fetches map tiles from upstream providers with disk cache.

Implements the v1 integrity rule: if an upstream is unreachable or returns
non-200, returns None (so the route handler can 503 with a source link),
rather than fabricating a tile.
"""
from __future__ import annotations
import asyncio
import hashlib
from pathlib import Path
from typing import Any

import httpx

from ..data import load_json_data


CACHE_DIR = Path("/tmp/nam_tile_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(layer_id: str, z: int, x: int, y: int) -> Path:
    h = hashlib.md5(f"{layer_id}/{z}/{x}/{y}".encode()).hexdigest()[:12]
    return CACHE_DIR / f"{layer_id}_{z}_{x}_{y}_{h}.bin"


async def fetch_tile(layer_id: str, z: int, x: int, y: int) -> dict | None:
    """Return {bytes, media_type, source_url, credit} or None on failure."""
    # Look up layer URL template
    layers = load_json_data()["LAYERS"]
    layer = next((l for l in layers if l["id"] == layer_id), None)
    if not layer:
        return None
    url = layer.get("url")
    if not url or not layer.get("live"):
        return None
    try:
        url_filled = url.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
    except Exception:
        return None

    # Check cache
    cache_path = _cache_key(layer_id, z, x, y)
    if cache_path.exists():
        return {
            "bytes": cache_path.read_bytes(),
            "media_type": _media_type_for(layer),
            "source_url": url_filled,
            "credit": layer.get("credit", ""),
        }

    # Fetch upstream (with short timeout — Mars tile services are sometimes slow)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url_filled, headers={"User-Agent": "NAM-backend/2.0"})
            if resp.status_code != 200:
                return None
            data = resp.content
            # Cache to disk (limit to 5 MB to avoid runaway)
            if len(data) < 5_000_000:
                cache_path.write_bytes(data)
            return {
                "bytes": data,
                "media_type": _media_type_for(layer),
                "source_url": url_filled,
                "credit": layer.get("credit", ""),
            }
    except Exception:
        return None


def _media_type_for(layer: dict) -> str:
    url = layer.get("url", "")
    if url.endswith(".png"):
        return "image/png"
    if url.endswith(".jpg") or url.endswith(".jpeg"):
        return "image/jpeg"
    if "image/png" in url.lower():
        return "image/png"
    return "image/png"
