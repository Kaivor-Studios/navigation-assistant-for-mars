"""Static data loaders.

Loads the bundled datasets extracted from NAM v1:
  - MOLA MEGDR elevation grid (1440 x 720 int32, 0.25 deg/px)
  - MOLA roughness grid (360 x 180 float32, 1 deg/px, NaN for no-data)
  - nam_data.json: PLANET, FEATURES (102), SITES (13), ORBITERS (8),
    TARGETS (16), INSTRUMENTS (13), LAYERS (6), REGISTRY (7)
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"

# Grid geometry — fixed by v1's encoding. DO NOT change without re-extracting.
ELEV_W = 1440
ELEV_H = 720
ROUGH_W = 360
ROUGH_H = 180

# MOLA areoid offsets (per v1): elevation meters = uint16 - 16384
ELEV_OFFSET = 16384
# Roughness meters = uint16 / 64, with 65535 = no-data
ROUGH_NODATA = 65535
ROUGH_SCALE = 64.0


@lru_cache(maxsize=1)
def load_elevation() -> np.ndarray:
    """Return a (720, 1440) int32 array of elevation meters.

    Grid orientation: row 0 = lat +90, last row = lat -90.
    Column 0 = lon 0 E, wraps through 360 E (== 0).
    """
    arr = np.fromfile(RAW_DIR / "elev.bin", dtype=np.int32)
    if arr.size != ELEV_W * ELEV_H:
        raise RuntimeError(
            f"elev.bin size mismatch: got {arr.size}, expected {ELEV_W * ELEV_H}"
        )
    return arr.reshape(ELEV_H, ELEV_W)


@lru_cache(maxsize=1)
def load_roughness() -> np.ndarray:
    """Return a (180, 360) float32 array of roughness meters (NaN for no-data)."""
    arr = np.fromfile(RAW_DIR / "rough.bin", dtype=np.float32)
    if arr.size != ROUGH_W * ROUGH_H:
        raise RuntimeError(
            f"rough.bin size mismatch: got {arr.size}, expected {ROUGH_W * ROUGH_H}"
        )
    return arr.reshape(ROUGH_H, ROUGH_W)


@lru_cache(maxsize=1)
def load_json_data() -> dict[str, Any]:
    """Return the parsed nam_data.json contents (PLANET, FEATURES, SITES, etc.)."""
    with (RAW_DIR / "nam_data.json").open() as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Mars physical constants (convenience access)
# ---------------------------------------------------------------------------
def mars_radius_m() -> float:
    return float(load_json_data()["PLANET"]["meanRadius_m"])


def mars_gravity() -> float:
    return float(load_json_data()["PLANET"]["gravity"])


def mars_datum_pressure_mbar() -> float:
    return float(load_json_data()["PLANET"]["datumPressure_mbar"])


def mars_scale_height_m() -> float:
    """Scale height H0 used in the pressure estimate (per v1)."""
    return 11_000.0


# ---------------------------------------------------------------------------
# Coordinates convention reminder
# ---------------------------------------------------------------------------
# Throughout the API: latitude is degrees (south negative, range -90..+90),
# longitude is degrees EAST in 0..360 convention (matches v1 and IAU Mars
# gazetteer). Negative longitudes are accepted and normalized to 0..360.
# ---------------------------------------------------------------------------


def normalize_lon(lon: float) -> float:
    """Bring any longitude into 0..360."""
    return ((lon % 360.0) + 360.0) % 360.0


def normalize_lat(lat: float) -> float:
    """Clamp latitude to -90..+90 (we don't accept poles-wrap)."""
    if lat > 90.0:
        return 90.0
    if lat < -90.0:
        return -90.0
    return lat
