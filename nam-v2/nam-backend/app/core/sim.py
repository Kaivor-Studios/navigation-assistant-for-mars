"""Environment simulation: dust storms, solar particle events, presence.

All simulated values are labelled [SIM]. Anchors:
  - MARCI daily global map climatology for dust seasonal patterns
  - 2018 Mars Year 34 PEDE for planet-encircling dust events
  - RAD on Curiosity Sept 2017 SEP event for solar particle events
"""
from __future__ import annotations
import uuid
import time
import random
from typing import Any

_EVENTS: dict[str, dict] = {}


def create_event(kind: str = "dust", lat: float = 0.0, lon: float = 0.0,
                 severity: str = "regional") -> dict:
    """Create a synthetic storm/SEP event."""
    eid = f"event-{uuid.uuid4().hex[:10]}"
    if kind == "dust":
        if severity == "planet_encircling":
            tau = 8.5  # MY34 PEDE peak
            duration_sols = 90
            polygon_radius_deg = 90.0  # half the planet
            intensity = {"tau": tau, "category": "PEDE (Mars Year 34 class)"}
            notes = ("Synthetic planet-encircling dust event modelled on the 2018 "
                     "Mars Year 34 PEDE that ended the Opportunity mission. [SIM]")
        elif severity == "regional":
            tau = 4.5
            duration_sols = 20
            polygon_radius_deg = 15.0
            intensity = {"tau": tau, "category": "regional dust event"}
            notes = "Synthetic regional dust event. [SIM]"
        else:  # local
            tau = 2.0
            duration_sols = 5
            polygon_radius_deg = 3.0
            intensity = {"tau": tau, "category": "local dust event"}
            notes = "Synthetic local dust event. [SIM]"
        event = {
            "id": eid,
            "kind": "dust",
            "severity": severity,
            "center": {"lat": lat, "lon": lon},
            "polygon": _circle_polygon(lat, lon, polygon_radius_deg),
            "start_sol": 1245,
            "duration_sols": duration_sols,
            "intensity": intensity,
            "operational_impact": {
                "solar_power_penalty_pct": round(min(80, tau * 8), 1),
                "eva_visibility_m": max(10, int(5000 / tau)),
                "rover_energy_inflation_pct": round(min(150, tau * 12), 1),
            },
            "notes": notes,
            "provenance": {
                "model": "[SIM] Synthetic event anchored on MARCI climatology (Malin Space Science Systems / PDS)",
                "reference": ("Montabone et al. (2015), Icarus 251, 65–95 (Mars dust climatology reanalysis); "
                               "Mars Year 34 PEDE (2018)."),
                "url": "https://pds-geosciences.wustl.edu/missions/mgs/marci.html",
            },
        }
    elif kind == "sep":
        if severity == "X-flare-class":
            peak_flux_pf = 50.0  # pfu > 10 MeV protons
            duration_sols = 3
            dose_msv = 50.0  # surface dose estimate behind nominal shielding
            intensity = {"peak_flux_pfu": peak_flux_pf, "dose_equiv_msv": dose_msv,
                         "class": "X-class SEP"}
            notes = ("Synthetic X-class solar particle event scaled from the "
                     "September 2017 event observed by RAD on Curiosity. [SIM]")
        else:
            peak_flux_pf = 10.0
            duration_sols = 1
            dose_msv = 5.0
            intensity = {"peak_flux_pfu": peak_flux_pf, "dose_equiv_msv": dose_msv,
                         "class": "M-class SEP"}
            notes = "Synthetic M-class solar particle event. [SIM]"
        event = {
            "id": eid,
            "kind": "sep",
            "severity": severity,
            "center": {"lat": lat, "lon": lon},
            "polygon": _circle_polygon(lat, lon, 45.0),  # SEPs are planet-wide
            "start_sol": 1245,
            "duration_sols": duration_sols,
            "intensity": intensity,
            "operational_impact": {
                "eva_halt": True,
                "shelter_required": True,
                "estimated_surface_dose_msv": dose_msv,
            },
            "notes": notes,
            "provenance": {
                "model": "[SIM] Synthetic SEP event anchored on RAD/Curiosity Sept 2017 observation",
                "reference": "Guo, J. et al. (2018), Space Weather 16, 977–988",
                "url": "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2018SW001981",
            },
        }
    else:
        raise ValueError(f"unknown event kind: {kind}")
    event["created_at"] = time.time()
    _EVENTS[eid] = event
    return event


def get_event(event_id: str) -> dict | None:
    return _EVENTS.get(event_id)


def list_events(kind: str | None = None, active_only: bool = False) -> list[dict]:
    out = []
    for e in _EVENTS.values():
        if kind and e["kind"] != kind:
            continue
        out.append(e)
    return out


def _circle_polygon(center_lat: float, center_lon: float, radius_deg: float,
                    steps: int = 16) -> list[dict]:
    """Return a list of {lat, lon} points approximating a circle around (lat, lon)."""
    pts = []
    for i in range(steps):
        theta = 2 * 3.14159265 * i / steps
        # Approximate in degrees — fine for event visualization
        lat = center_lat + radius_deg * 0.7 * math.cos(theta)  # 0.7 accounts for cos(lat) scaling
        lon = center_lon + radius_deg * math.sin(theta)
        # wrap lon
        lon = ((lon % 360) + 360) % 360
        pts.append({"lat": round(lat, 4), "lon": round(lon, 4)})
    pts.append(pts[0])  # close polygon
    return pts


# ---------------------------------------------------------------------------
# Presence (simulated agents)
# ---------------------------------------------------------------------------

_PRESENCE_AGENTS: list[dict] = [
    {"id": "agent-1", "name": "Crew Alpha (Commander)", "kind": "crew",
     "lat": 18.44, "lon": 77.45, "sol": 1245, "status": "eva"},
    {"id": "agent-2", "name": "Crew Bravo (Geologist)", "kind": "crew",
     "lat": 18.45, "lon": 77.50, "sol": 1245, "status": "eva"},
    {"id": "agent-3", "name": "Habitat Base Camp", "kind": "habitat",
     "lat": 18.42, "lon": 77.43, "sol": 1245, "status": "online"},
    {"id": "agent-4", "name": "Rover Perseverance (sim)", "kind": "rover",
     "lat": 18.448, "lon": 77.471, "sol": 1245, "status": "driving"},
    {"id": "agent-5", "name": "Cargo Cache #1", "kind": "cache",
     "lat": 18.50, "lon": 77.60, "sol": 1245, "status": "deployed"},
]


def list_presence() -> list[dict]:
    return list(_PRESENCE_AGENTS)


def presence_near(lat: float, lon: float, radius_km: float = 100.0) -> list[dict]:
    import math
    R = 3389500.0
    out = []
    for a in _PRESENCE_AGENTS:
        dlat = math.radians(a["lat"] - lat)
        dlon = math.radians(a["lon"] - lon)
        x = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat)) * math.cos(math.radians(a["lat"]))
             * math.sin(dlon / 2) ** 2)
        d = R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x)) / 1000.0
        if d <= radius_km:
            out.append({**a, "distance_km": round(d, 1)})
    out.sort(key=lambda x: x["distance_km"])
    return out


def tick_presence():
    """Advance the simulated agents by one tick (small jitter)."""
    for a in _PRESENCE_AGENTS:
        if a["kind"] in ("crew", "rover") and a["status"] == "driving" or a["status"] == "eva":
            a["lat"] += random.uniform(-0.005, 0.005)
            a["lon"] += random.uniform(-0.005, 0.005)
            a["sol"] = a.get("sol", 1245)


# Need math import (kept at bottom to keep file readable)
import math  # noqa: E402
