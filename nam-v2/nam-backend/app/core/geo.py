"""Geospatial engine: elevation, slope, roughness, hazard scoring.

Pure-Python port of NAM.ELEV and NAM.INTEL from the v1 single-file app.
The math is intentionally identical so the v1 behaviour is preserved:
  - bilinear sampling on the 4 ppd MOLA grid
  - regional slope from ±0.25 deg neighbours (~30 km at equator)
  - roughness lookup on the 1 ppd MOLA roughness grid
  - composite hazard score from slope + roughness + elevation
All values are advisory planning indicators, never certified safety products.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from ..data import (
    ELEV_H, ELEV_W, ROUGH_H, ROUGH_W,
    load_elevation, load_roughness,
    mars_radius_m, mars_datum_pressure_mbar, mars_scale_height_m,
    normalize_lat, normalize_lon,
)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------
def _bilinear(grid: np.ndarray, lat: float, lon: float, deg_per_px: float) -> float:
    """Bilinear sample of a global grid; lon wraps 0..360."""
    fr = (90.0 - lat) / deg_per_px
    fc = normalize_lon(lon) / deg_per_px
    h, w = grid.shape
    r0 = int(math.floor(fr))
    c0 = int(math.floor(fc))
    tr = fr - r0
    tc = fc - c0
    # clamp lat rows, wrap lon cols
    r0 = max(0, min(h - 2, r0))
    r1 = r0 + 1
    c0 = c0 % w
    c1 = (c0 + 1) % w
    v00 = float(grid[r0, c0])
    v01 = float(grid[r0, c1])
    v10 = float(grid[r1, c0])
    v11 = float(grid[r1, c1])
    return (v00 * (1 - tc) + v01 * tc) * (1 - tr) + (v10 * (1 - tc) + v11 * tc) * tr


def sample_elevation(lat: float, lon: float) -> float:
    """Bilinear elevation (meters above MOLA areoid)."""
    return _bilinear(load_elevation(), normalize_lat(lat), normalize_lon(lon), 0.25)


def sample_roughness(lat: float, lon: float) -> float | None:
    """Nearest-pixel roughness (meters), or None for no-data cells."""
    grid = load_roughness()
    lat = normalize_lat(lat)
    lon = normalize_lon(lon)
    r = int(round((90.0 - lat)))
    c = int(round(lon))
    r = max(0, min(ROUGH_H - 1, r))
    c = c % ROUGH_W
    v = float(grid[r, c])
    if math.isnan(v):
        return None
    return v


def slope_at(lat: float, lon: float) -> float | None:
    """Regional slope (degrees) over ±0.25 deg (~30 km E-W at equator)."""
    lat = normalize_lat(lat)
    lon = normalize_lon(lon)
    dpx = 0.25
    try:
        e0 = sample_elevation(lat, lon)
        en = sample_elevation(lat + dpx, lon)
        es = sample_elevation(lat - dpx, lon)
        ee = sample_elevation(lat, lon + dpx)
        ew = sample_elevation(lat, lon - dpx)
    except Exception:
        return None
    km_per_deg_lat = mars_radius_m() * math.pi / 180.0 / 1000.0  # ~59.17
    km_per_deg_lon = km_per_deg_lat * max(0.05, math.cos(lat * math.pi / 180.0))
    dz_n = (en - es) / (2 * dpx)  # meters per degree
    dz_e = (ee - ew) / (2 * dpx)
    s_n = dz_n / (km_per_deg_lat * 1000.0)
    s_e = dz_e / (km_per_deg_lon * 1000.0)
    return math.degrees(math.atan(math.sqrt(s_n * s_n + s_e * s_e)))


def pressure_estimate(elev_m: float | None) -> float | None:
    """Surface pressure (mbar) using Mars datum pressure + scale height."""
    if elev_m is None:
        return None
    H = mars_scale_height_m()
    p0 = mars_datum_pressure_mbar()
    return round(min(12.5, p0 * math.exp(-elev_m / H)), 4)


# ---------------------------------------------------------------------------
# Hazard scoring (composite)
# ---------------------------------------------------------------------------
HAZARD_THRESHOLDS = {
    # slope (deg) thresholds per v1 INTEL
    "slope_low": 5.0,
    "slope_med": 10.0,
    "slope_high": 20.0,
    # roughness (m) thresholds
    "rough_low": 5.0,
    "rough_med": 15.0,
    "rough_high": 30.0,
}


@dataclass
class HazardReadout:
    lat: float
    lon: float
    elev_m: float
    slope_deg: float | None
    roughness_m: float | None
    pressure_mbar: float | None
    hazard_class: str  # "low" | "moderate" | "high" | "extreme"
    hazard_score: float  # 0..100 composite
    notes: list[str]
    provenance: dict


def hazard_at(lat: float, lon: float) -> HazardReadout:
    lat_n = normalize_lat(lat)
    lon_n = normalize_lon(lon)
    elev = sample_elevation(lat_n, lon_n)
    slope = slope_at(lat_n, lon_n)
    rough = sample_roughness(lat_n, lon_n)
    press = pressure_estimate(elev)

    notes: list[str] = []
    score = 0.0

    # slope contribution (0-45 pts)
    if slope is not None:
        if slope > HAZARD_THRESHOLDS["slope_high"]:
            score += 45.0
            notes.append(f"Slope {slope:.1f}° exceeds {HAZARD_THRESHOLDS['slope_high']}° — major traverse risk.")
        elif slope > HAZARD_THRESHOLDS["slope_med"]:
            score += 30.0
            notes.append(f"Slope {slope:.1f}° — sustained grade, rover/EVA caution.")
        elif slope > HAZARD_THRESHOLDS["slope_low"]:
            score += 15.0
            notes.append(f"Slope {slope:.1f}° — moderate grade.")
        else:
            score += 0.0
    else:
        notes.append("Slope unavailable (grid edge).")

    # roughness contribution (0-30 pts)
    if rough is not None:
        if rough > HAZARD_THRESHOLDS["rough_high"]:
            score += 30.0
            notes.append(f"Roughness {rough:.1f} m — boulder field, mobility risk.")
        elif rough > HAZARD_THRESHOLDS["rough_med"]:
            score += 20.0
            notes.append(f"Roughness {rough:.1f} m — uneven terrain.")
        elif rough > HAZARD_THRESHOLDS["rough_low"]:
            score += 10.0
            notes.append(f"Roughness {rough:.1f} m — minor irregularities.")
    else:
        notes.append("Roughness unavailable at this point (no-data cell).")

    # elevation contribution (0-25 pts) — extreme low (Hellas) and extreme high (Tharsis) both penalize
    if elev < -6000:
        score += 25.0
        notes.append(f"Elevation {elev:.0f} m — deep basin; pressure {press:.2f} mbar (densest atmosphere).")
    elif elev < -3000:
        score += 10.0
        notes.append(f"Elevation {elev:.0f} m — below datum.")
    elif elev > 15_000:
        score += 20.0
        notes.append(f"Elevation {elev:.0f} m — extremely high; pressure {press:.2f} mbar (very thin atmosphere).")
    elif elev > 8_000:
        score += 10.0
        notes.append(f"Elevation {elev:.0f} m — above datum; pressure {press:.2f} mbar.")

    score = min(100.0, score)
    if score >= 65:
        cls = "extreme"
    elif score >= 40:
        cls = "high"
    elif score >= 20:
        cls = "moderate"
    else:
        cls = "low"

    return HazardReadout(
        lat=lat_n, lon=lon_n, elev_m=float(elev),
        slope_deg=(None if slope is None else round(slope, 2)),
        roughness_m=(None if rough is None else round(rough, 2)),
        pressure_mbar=press,
        hazard_class=cls,
        hazard_score=round(score, 1),
        notes=notes,
        provenance={
            "elevation": "MOLA MEGDR 4 px/deg (NASA PDS urn-nasa-pds-mgs_mola_topography_derived)",
            "roughness": "MOLA roughness 1 px/deg (NASA PDS)",
            "slope": "Derived from MOLA MEGDR 4 ppd, ±0.25 deg neighbourhood (~30 km)",
            "pressure": "Derived from MOLA areoid + simple scale-height model; advisory only",
            "url": "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
            "advisory": "Regional MOLA slopes (~15 km cells) cannot resolve meter-scale obstacles — advisory only.",
        },
    )


# ---------------------------------------------------------------------------
# Elevation profile (along a path of points)
# ---------------------------------------------------------------------------
def elevation_profile(points: Iterable[tuple[float, float]]) -> list[dict]:
    """For each (lat, lon) return {lat, lon, elev_m, slope_deg, rough_m, pressure_mbar}."""
    out = []
    for (lat, lon) in points:
        e = sample_elevation(lat, lon)
        s = slope_at(lat, lon)
        r = sample_roughness(lat, lon)
        out.append({
            "lat": round(lat, 5),
            "lon": round(normalize_lon(lon), 5),
            "elev_m": round(e, 1),
            "slope_deg": (None if s is None else round(s, 2)),
            "rough_m": (None if r is None else round(r, 2)),
            "pressure_mbar": pressure_estimate(e),
        })
    return out


# ---------------------------------------------------------------------------
# Terrain analyse — local grid of slope/elevation/roughness around a point
# ---------------------------------------------------------------------------
def terrain_analyze(lat: float, lon: float, radius_km: float, resolution_deg: float | None = None) -> dict:
    """Compute a small local grid of elevation + slope + roughness + hazard.

    radius_km : half-width of the analysed box (km)
    resolution_deg : grid step in degrees; defaults to ~1 km at the equator
                     (i.e. 1/60 deg) but clamped to no less than 0.25 deg (the
                     MOLA grid resolution — finer steps just bilinear-interp)
    """
    R = mars_radius_m()
    if resolution_deg is None:
        resolution_deg = max(0.25, (1.0 / 60.0))  # ~1.85 km at equator
    half_deg_lat = (radius_km * 1000.0) / R * (180.0 / math.pi)
    cos_lat = max(0.05, math.cos(math.radians(lat)))
    half_deg_lon = half_deg_lat / cos_lat

    n_lat = max(3, int(2 * half_deg_lat / resolution_deg) + 1)
    n_lon = max(3, int(2 * half_deg_lon / resolution_deg) + 1)
    n_lat = min(n_lat, 80)
    n_lon = min(n_lon, 80)

    cells = []
    elev_grid = []
    slope_grid = []
    hazard_grid = []
    for i in range(n_lat):
        row_elev = []
        row_slope = []
        row_haz = []
        for j in range(n_lon):
            la = lat - half_deg_lat + (i / max(1, n_lat - 1)) * 2 * half_deg_lat
            lo = lon - half_deg_lon + (j / max(1, n_lon - 1)) * 2 * half_deg_lon
            e = sample_elevation(la, lo)
            s = slope_at(la, lo)
            r = sample_roughness(la, lo)
            row_elev.append(round(e, 1))
            row_slope.append(None if s is None else round(s, 2))
            # crude hazard cell — slope dominated
            if s is None:
                row_haz.append("unknown")
            elif s > HAZARD_THRESHOLDS["slope_high"]:
                row_haz.append("extreme")
            elif s > HAZARD_THRESHOLDS["slope_med"]:
                row_haz.append("high")
            elif s > HAZARD_THRESHOLDS["slope_low"]:
                row_haz.append("moderate")
            else:
                row_haz.append("low")
            cells.append({
                "lat": round(la, 5), "lon": round(normalize_lon(lo), 5),
                "elev_m": round(e, 1),
                "slope_deg": (None if s is None else round(s, 2)),
                "rough_m": (None if r is None else round(r, 2)),
            })
        elev_grid.append(row_elev)
        slope_grid.append(row_slope)
        hazard_grid.append(row_haz)

    return {
        "center": {"lat": normalize_lat(lat), "lon": normalize_lon(lon)},
        "radius_km": radius_km,
        "resolution_deg": resolution_deg,
        "grid_shape": [n_lat, n_lon],
        "extent": {
            "lat_min": round(lat - half_deg_lat, 5),
            "lat_max": round(lat + half_deg_lat, 5),
            "lon_min": round(normalize_lon(lon - half_deg_lon), 5),
            "lon_max": round(normalize_lon(lon + half_deg_lon), 5),
        },
        "elev_grid": elev_grid,
        "slope_grid": slope_grid,
        "hazard_grid": hazard_grid,
        "cells": cells,
        "provenance": {
            "elevation": "MOLA MEGDR 4 px/deg",
            "slope": "±0.25 deg neighbourhood (~30 km at equator)",
            "roughness": "MOLA 1 px/deg",
            "advisory": "Regional MOLA slopes; advisory planning only.",
            "url": "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
        },
    }
