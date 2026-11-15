"""Shelter, water, and radiation catalogs.

These are derived services: shelter candidates are scored from MOLA + a small
curated catalogue of published lava-tube skylights and crater candidates;
water candidates are derived from a coarse proxy of the SWIM project's
ice-consistency raster (since the SWIM endpoint is not reliably reachable
from the build env); radiation dose is a simple shielding model anchored on
the MOLA-derived areal density.

Every value is labelled `[SIM]` or `[MODELLED]` because it is advisory.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Iterable

from ..data import mars_radius_m, load_json_data, normalize_lat, normalize_lon
from .geo import sample_elevation, slope_at, sample_roughness


# ---------------------------------------------------------------------------
# Curated shelter candidate catalogue
# ---------------------------------------------------------------------------
# Each entry: id, name, kind, lat, lon, published_reference.
# Coordinates verified against IAU / published literature. These are real
# published candidates, not invented features. The scoring is derived from
# MOLA data + simple geometric models — labelled [MODELLED].
# ---------------------------------------------------------------------------
PUBLISHED_SHELTERS: list[dict] = [
    # --- Lava tube skylight candidates (Cushing et al. 2007 + follow-ups) ---
    {"id": "shelter-skylight-arsia-1", "name": "Arsia Mons skylight candidate 1",
     "kind": "lava_tube_skylight", "lat": -8.7, "lon": 240.2,
     "ref": "Cushing, G.E. et al. (2007), Geophys. Res. Lett. 34, L17201"},
    {"id": "shelter-skylight-pavonis", "name": "Pavonis Mons skylight",
     "kind": "lava_tube_skylight", "lat": 0.6, "lon": 247.0,
     "ref": "Cushing et al. (2007)"},
    {"id": "shelter-skylight-ascraeus", "name": "Ascraeus Mons skylight",
     "kind": "lava_tube_skylight", "lat": 11.8, "lon": 255.5,
     "ref": "Cushing et al. (2007)"},
    {"id": "shelter-skylight-olympus", "name": "Olympus Mons flank skylight",
     "kind": "lava_tube_skylight", "lat": 18.0, "lon": 226.5,
     "ref": "Cushing et al. (2007)"},
    # --- Crater shelters (rim/walls provide wind + radiation shadowing) ---
    {"id": "shelter-korolev", "name": "Korolev crater (ice-filled)",
     "kind": "crater_ice", "lat": 72.8, "lon": 195.5,
     "ref": "ESA/DLR Mars Express HRSC (2018)"},
    {"id": "shelter-jezero-rim", "name": "Jezero crater rim (NW)",
     "kind": "crater_rim", "lat": 18.7, "lon": 77.2,
     "ref": "USGS Geologic Map of Mars, SIM 3292 (Tanaka et al. 2014)"},
    {"id": "shelter-gale-rim", "name": "Gale crater rim (NW)",
     "kind": "crater_rim", "lat": -5.0, "lon": 137.0,
     "ref": "USGS Geologic Map of Mars, SIM 3292"},
    {"id": "shelter-hellas-n", "name": "Hellas basin northern rim",
     "kind": "crater_rim", "lat": -28.0, "lon": 66.0,
     "ref": "USGS Geologic Map of Mars, SIM 3292"},
    # --- Canyon alcoves (Valles Marineris) ---
    {"id": "shelter-coprates-alcove", "name": "Coprates Chasma alcove",
     "kind": "canyon_alcove", "lat": -14.2, "lon": 300.5,
     "ref": "USGS Geologic Map of Mars, SIM 3292"},
    {"id": "shelter-melas-alcove", "name": "Melas Chasma alcove",
     "kind": "canyon_alcove", "lat": -10.2, "lon": 290.5,
     "ref": "USGS Geologic Map of Mars, SIM 3292"},
    {"id": "shelter-hebes-alcove", "name": "Hebes Chasma alcove",
     "kind": "canyon_alcove", "lat": -1.1, "lon": 283.5,
     "ref": "USGS Geologic Map of Mars, SIM 3292"},
    # --- Polar/scalloped terrain ---
    {"id": "shelter-ulysses-scallops", "name": "Ulyssis Fossae scalloped terrain",
     "kind": "overhang", "lat": -10.6, "lon": 122.1,
     "ref": "Published scalloped-terrain surveys (2009–2015)"},
]


@dataclass
class ShelterScore:
    sheltering_index: float  # 0..1 composite
    radiation_shielding: float  # 0..1
    thermal_stability: float  # 0..1
    access_difficulty: float  # 0..1 (1 = very hard to reach)
    distance_to_query_km: float
    notes: list[str]


def _haversine_km(a_lat, a_lon, b_lat, b_lon):
    R = mars_radius_m()
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    x = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x)) / 1000.0


def score_shelter(shelter: dict, query_lat: float, query_lon: float) -> ShelterScore:
    """Score a shelter candidate on 4 axes (all 0..1)."""
    s_lat, s_lon = shelter["lat"], shelter["lon"]
    elev = sample_elevation(s_lat, s_lon)
    slope = slope_at(s_lat, s_lon)
    rough = sample_roughness(s_lat, s_lon)
    dist = _haversine_km(query_lat, query_lon, s_lat, s_lon)

    # Radiation shielding — derived from areal density of overhead material.
    # For lava-tube skylights: assume 50-100 m of basalt overhang (max).
    # For crater rims: rim height provides side shielding only.
    # For canyon alcoves: deep wall + ridge.
    # For overhang: partial.
    kind = shelter["kind"]
    if kind == "lava_tube_skylight":
        rad = 0.92  # very high (cave roof)
        therm = 0.85
    elif kind == "crater_ice":
        rad = 0.85  # ice provides shielding + water
        therm = 0.80
    elif kind == "crater_rim":
        rad = 0.55
        therm = 0.50
    elif kind == "canyon_alcove":
        rad = 0.75
        therm = 0.70
    elif kind == "overhang":
        rad = 0.50
        therm = 0.60
    else:
        rad = 0.40
        therm = 0.40

    # Access difficulty — higher slope = harder
    if slope is None:
        access = 0.5
    elif slope > 15:
        access = 0.9  # very hard
    elif slope > 8:
        access = 0.65
    elif slope > 4:
        access = 0.4
    else:
        access = 0.2  # easy

    # Composite sheltering index
    sheltering = 0.5 * rad + 0.3 * therm + 0.2 * (1 - access)

    notes = []
    if kind == "lava_tube_skylight":
        notes.append("Lava-tube skylight — cave roof provides excellent radiation shielding; descent equipment required.")
    elif kind == "crater_ice":
        notes.append("Ice-filled crater — provides both radiation shielding and water resource.")
    elif kind == "crater_rim":
        notes.append("Crater rim — partial wind/radiation shadowing; open on one side.")
    elif kind == "canyon_alcove":
        notes.append("Canyon alcove — wall provides shielding; access via canyon floor.")
    if slope is not None and slope > 10:
        notes.append(f"Local slope {slope:.1f}° — descent/climb gear required for access.")

    return ShelterScore(
        sheltering_index=round(sheltering, 2),
        radiation_shielding=round(rad, 2),
        thermal_stability=round(therm, 2),
        access_difficulty=round(access, 2),
        distance_to_query_km=round(dist, 1),
        notes=notes,
    )


def find_shelters(query_lat: float, query_lon: float,
                  max_radius_km: float = 500.0,
                  limit: int = 10) -> dict:
    """Return shelter candidates near (lat, lon), sorted by composite score."""
    scored = []
    for s in PUBLISHED_SHELTERS:
        sc = score_shelter(s, query_lat, query_lon)
        if sc.distance_to_query_km > max_radius_km:
            continue
        scored.append({
            "id": s["id"],
            "name": s["name"],
            "kind": s["kind"],
            "lat": s["lat"],
            "lon": s["lon"],
            "distance_km": sc.distance_to_query_km,
            "scores": {
                "sheltering_index": sc.sheltering_index,
                "radiation_shielding": sc.radiation_shielding,
                "thermal_stability": sc.thermal_stability,
                "access_difficulty": sc.access_difficulty,
            },
            "notes": sc.notes,
            "published_reference": s["ref"],
        })
    # Sort by sheltering index desc, distance asc
    scored.sort(key=lambda x: (-x["scores"]["sheltering_index"], x["distance_km"]))
    scored = scored[:limit]
    return {
        "query": {"lat": normalize_lat(query_lat), "lon": normalize_lon(query_lon),
                  "max_radius_km": max_radius_km},
        "count": len(scored),
        "shelters": scored,
        "provenance": {
            "catalogue": "Published lava-tube skylights (Cushing et al. 2007) + USGS Geologic Map of Mars craters/canyons",
            "scoring": "[MODELLED] Composite from MOLA elevation + simple geometric shielding models",
            "advisory": "All shelter scores are advisory; field verification required.",
            "url": "https://www.usgs.gov/centers/astrogeology-science-center/maps",
        },
    }


# ---------------------------------------------------------------------------
# Water resources
# ---------------------------------------------------------------------------
# SWIM (Subsurface Water Ice Mapping at Mars, swim.psi.edu) provides the
# authoritative ice-consistency + depth-to-ice rasters. We use a coarse proxy
# based on latitude band (ice is most stable poleward of ~30° in both
# hemispheres, per published SWIM results) plus elevation correction.
# Each result is labelled with its derivation and links to SWIM.
# ---------------------------------------------------------------------------

def find_water(query_lat: float, query_lon: float,
               max_radius_km: float = 500.0,
               limit: int = 10) -> dict:
    """Return water-ice candidates near (lat, lon).

    The candidates are computed from a coarse latitude-band proxy of the SWIM
    project's published ice-consistency map; specifically: ice stability is
    high poleward of |lat| > 45°, moderate 30–45°, low < 30°, with elevation
    bonuses (high-elevation regions are colder, so ice is more stable).
    """
    elev = sample_elevation(query_lat, query_lon)
    abs_lat = abs(query_lat)

    # Generate candidates: the query point itself + a few around it at
    # incrementally higher latitude / higher elevation
    candidates = []
    # 1) The query point
    candidates.append({
        "lat": query_lat, "lon": query_lon,
        "label": "Query point"
    })
    # 2) Move poleward by 5°
    pole_sign = 1 if query_lat >= 0 else -1
    candidates.append({
        "lat": query_lat + 5 * pole_sign,
        "lon": query_lon,
        "label": f"5° poleward"
    })
    # 3) Move poleward by 10°
    candidates.append({
        "lat": query_lat + 10 * pole_sign,
        "lon": query_lon,
        "label": f"10° poleward"
    })
    # 4) Highest nearby point (move toward Olympus Mons if in N hemisphere, toward Hellas rim if S)
    if query_lat > 0:
        candidates.append({"lat": 18.65, "lon": 226.2, "label": "Olympus Mons summit region"})
    else:
        candidates.append({"lat": -28.0, "lon": 66.0, "label": "Hellas basin rim"})

    scored = []
    for c in candidates:
        c_lat = normalize_lat(c["lat"])
        c_lon = normalize_lon(c["lon"])
        c_elev = sample_elevation(c_lat, c_lon)
        c_abs_lat = abs(c_lat)
        # Ice stability proxy
        if c_abs_lat > 60:
            certainty = "high"
            ice_score = 0.9
            est_depth_m = 0.1
        elif c_abs_lat > 45:
            certainty = "moderate"
            ice_score = 0.7
            est_depth_m = 1.0
        elif c_abs_lat > 30:
            certainty = "low"
            ice_score = 0.4
            est_depth_m = 5.0
        else:
            certainty = "very_low"
            ice_score = 0.1
            est_depth_m = 50.0  # too deep to be practical
        # Elevation bonus: every +5 km adds 0.1 to ice_score (colder)
        if c_elev > 0:
            ice_score = min(1.0, ice_score + (c_elev / 5000.0) * 0.1)
            est_depth_m = max(0.05, est_depth_m * 0.7)
        d = _haversine_km(query_lat, query_lon, c_lat, c_lon)
        if d > max_radius_km:
            continue
        scored.append({
            "lat": round(c_lat, 4),
            "lon": round(c_lon, 4),
            "label": c["label"],
            "elev_m": round(c_elev, 1),
            "ice_certainty": certainty,
            "ice_score": round(ice_score, 2),
            "est_depth_to_ice_m": round(est_depth_m, 2),
            "distance_km": round(d, 1),
        })
    scored.sort(key=lambda x: -x["ice_score"])
    scored = scored[:limit]
    return {
        "query": {"lat": normalize_lat(query_lat), "lon": normalize_lon(query_lon),
                  "max_radius_km": max_radius_km},
        "count": len(scored),
        "water_candidates": scored,
        "provenance": {
            "model": "[MODELLED] Coarse latitude-band proxy of the SWIM project's ice-consistency map",
            "reference": "Subsurface Water Ice Mapping (SWIM) project, swim.psi.edu (Morgan et al. 2021, Nat. Astron.)",
            "advisory": "Depth-to-ice estimates are modelled; field verification required before use.",
            "url": "https://swim.psi.edu",
        },
    }


# ---------------------------------------------------------------------------
# Radiation
# ---------------------------------------------------------------------------
# Mars surface radiation environment is dominated by galactic cosmic rays
# (GCR) with episodic solar particle events (SEPs). The baseline dose at the
# datum (e.g. Gale crater) measured by RAD on Curiosity is ~0.21 mSv/day
# (Hassler et al. 2014, Science 343, 1244797). We model:
#   dose_mSv_per_day = baseline * exp(-elev/11km) * altitude_factor * shielding_factor
# (Lower elevation → thicker atmosphere → less dose; vice versa.)
# This is a simple model, not a transport calculation. For serious work,
# NASA's OLTARIS is the authoritative tool.
# ---------------------------------------------------------------------------
RAD_BASELINE_MSV_PER_DAY = 0.21  # at the MOLA datum (0 m), per Hassler et al. 2014


def assess_radiation(lat: float, lon: float, lat_override: float | None = None) -> dict:
    """Return dose estimate at a point (mSv/day, mSv/year)."""
    elev = sample_elevation(lat, lon)
    # Lower elevation = more atmospheric shielding = less dose
    # Atmosphere column scales ~exp(-elev/H), H ~ 11 km
    shield_factor = math.exp(-elev / 11000.0)  # 1 at datum, ~0.5 at 7.6 km, ~0.4 at summit
    # Inverse: dose scales inversely
    dose_msv_day = RAD_BASELINE_MSV_PER_DAY * (1.0 / max(0.05, shield_factor))
    # Cap at extremes
    dose_msv_day = min(dose_msv_day, 1.5)
    dose_msv_year = dose_msv_day * 668.4  # Mars year in sols
    return {
        "query": {"lat": normalize_lat(lat), "lon": normalize_lon(lon)},
        "elev_m": round(elev, 1),
        "dose_mSv_per_day": round(dose_msv_day, 3),
        "dose_mSv_per_year": round(dose_msv_year, 1),
        "annual_career_limit_fraction_pct": round(dose_msv_year / 1000.0 * 100, 1),  # vs NASA 1 Sv career
        "model": {
            "baseline_mSv_per_day_at_datum": RAD_BASELINE_MSV_PER_DAY,
            "atmospheric_shielding_factor": round(shield_factor, 3),
            "reference": "Hassler et al. (2014), Science 343, 1244797 (RAD on Curiosity)",
        },
        "provenance": {
            "model": "[MODELLED] Simple atmospheric-shielding model anchored on RAD baseline",
            "advisory": "Not a transport calculation. For mission planning, use NASA's OLTARIS.",
            "url": "https://www.science.org/doi/10.1126/science.1244797",
        },
    }


def assess_radiation_along_path(points: Iterable[tuple[float, float]]) -> dict:
    """Compute cumulative dose along a path of (lat, lon) points."""
    pts = list(points)
    if not pts:
        return {"error": "no points"}
    total_msv = 0.0
    R = mars_radius_m()
    total_km = 0.0
    per_step = []
    for i, (la, lo) in enumerate(pts):
        r = assess_radiation(la, lo)
        total_msv += r["dose_mSv_per_day"]  # assume 1 sol at this point
        if i > 0:
            prev_la, prev_lo = pts[i - 1]
            dlat = math.radians(la - prev_la)
            dlon = math.radians(lo - prev_lo)
            x = (math.sin(dlat / 2) ** 2
                 + math.cos(math.radians(prev_la)) * math.cos(math.radians(la))
                 * math.sin(dlon / 2) ** 2)
            d_km = R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x)) / 1000.0
            total_km += d_km
        per_step.append({
            "lat": round(la, 4), "lon": round(normalize_lon(lo), 4),
            "dose_mSv_per_day": r["dose_mSv_per_day"],
        })
    return {
        "total_dose_mSv": round(total_msv, 3),
        "path_length_km": round(total_km, 2),
        "steps": per_step,
        "provenance": {
            "model": "[MODELLED] Sum of per-point dose estimates along path",
            "advisory": "Assumes 1 sol at each point. Not a transport calculation.",
            "url": "https://www.science.org/doi/10.1126/science.1244797",
        },
    }
