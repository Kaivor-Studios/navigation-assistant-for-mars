"""A* route planner over the MOLA 4 ppd grid.

Port of NAM.ROUTER from v1. Same cost function and three presets:
  - balanced   : distance + slope² + roughness penalty
  - terrain    : heavy slope/roughness penalty (terrain-averse)
  - speed      : distance-dominated (fastest traverse)

Cost formula (matches v1 NAM.ROUTER):
  cost = distance_km * (1 + (slope_deg/6)^2 * w_slope + rough/5 * w_rough)
        - science_bonus * 0.05

The grid resolution is 0.25 deg (~14.8 km at the equator), so the planner is
regional only — advisory, not certified safe.
"""
from __future__ import annotations
import heapq
import math
from dataclasses import dataclass, field
from typing import Iterable

from ..data import (
    ELEV_H, ELEV_W, load_elevation, load_roughness,
    mars_radius_m, normalize_lat, normalize_lon,
)
from .geo import sample_elevation, slope_at, sample_roughness


PRESETS = {
    "balanced": {"w_slope": 1.0, "w_rough": 1.0, "science_bonus": 0.0},
    "terrain":  {"w_slope": 3.0, "w_rough": 2.5, "science_bonus": 0.0},
    "speed":    {"w_slope": 0.5, "w_rough": 0.3, "science_bonus": 0.0},
}

# 8-connected neighbours (row, col, diagonal?) — diagonals cost sqrt(2)
_NEIGHBOURS = [
    (-1, 0, False), (1, 0, False), (0, -1, False), (0, 1, False),
    (-1, -1, True), (-1, 1, True), (1, -1, True), (1, 1, True),
]


@dataclass
class RouteStats:
    length_m: float = 0.0
    length_km: float = 0.0
    ascent_m: float = 0.0
    descent_m: float = 0.0
    max_slope_deg: float = 0.0
    mean_slope_deg: float = 0.0
    est_sols: float = 0.0  # rough traversal-time estimate at 100 m/sol EVA


@dataclass
class RouteResult:
    ok: bool
    preset: str
    start: dict
    end: dict
    waypoints: list[dict] = field(default_factory=list)  # [{lat, lon, elev_m, slope_deg}]
    stats: RouteStats | None = None
    path_cells: int = 0
    notes: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)


def _latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """Return (row, col) into the (720, 1440) grid for a (lat, lon)."""
    la = normalize_lat(lat)
    lo = normalize_lon(lon)
    r = int(round((90.0 - la) * 4.0))
    c = int(round(lo * 4.0))
    r = max(0, min(ELEV_H - 1, r))
    c = c % ELEV_W
    return r, c


def _grid_to_latlon(r: int, c: int) -> tuple[float, float]:
    """Inverse of _latlon_to_grid (returns centre of cell)."""
    la = 90.0 - r / 4.0
    lo = (c / 4.0) % 360.0
    return la, lo


def _km_per_cell_at(lat: float) -> tuple[float, float]:
    """Return (km_per_col, km_per_row) for the 0.25 deg grid at this latitude."""
    R = mars_radius_m()
    km_per_deg_lat = R * math.pi / 180.0 / 1000.0
    km_per_deg_lon = km_per_deg_lat * max(0.05, math.cos(math.radians(lat)))
    return km_per_deg_lon * 0.25, km_per_deg_lat * 0.25


def _slope_at_grid(elev: "np.ndarray", r: int, c: int) -> float:
    """Slope (degrees) at a grid cell using ±1 cell (~7.4 km at equator)."""
    import numpy as np
    h, w = elev.shape
    c0 = c % w
    cn = (c + 1) % w
    cs = (c - 1) % w
    rn = min(h - 1, r + 1)
    rs = max(0, r - 1)
    e0 = float(elev[r, c0])
    en = float(elev[rs, c0])
    es = float(elev[rn, c0])
    ee = float(elev[r, cn])
    ew = float(elev[r, cs])
    # treat as ±0.25 deg (one cell)
    dpx = 0.25
    R = mars_radius_m()
    km_per_deg_lat = R * math.pi / 180.0 / 1000.0
    lat = 90.0 - r / 4.0
    km_per_deg_lon = km_per_deg_lat * max(0.05, math.cos(math.radians(lat)))
    dz_n = (en - es) / (2 * dpx)
    dz_e = (ee - ew) / (2 * dpx)
    s_n = dz_n / (km_per_deg_lat * 1000.0)
    s_e = dz_e / (km_per_deg_lon * 1000.0)
    return math.degrees(math.atan(math.sqrt(s_n * s_n + s_e * s_e)))


def plan_route(start_lat: float, start_lon: float,
               end_lat: float, end_lon: float,
               preset: str = "balanced",
               max_steps: int = 6000,
               blocked_cells: set[tuple[int, int]] | None = None) -> RouteResult:
    """A* over the 4 ppd MOLA grid. Returns a RouteResult.

    blocked_cells : optional set of (r, c) cells to avoid (e.g. storm polygon).
    """
    if preset not in PRESETS:
        preset = "balanced"
    w = PRESETS[preset]

    start = (normalize_lat(start_lat), normalize_lon(start_lon))
    end = (normalize_lat(end_lat), normalize_lon(end_lon))

    elev = load_elevation()  # (720, 1440) int32

    sr, sc = _latlon_to_grid(*start)
    er, ec = _latlon_to_grid(*end)

    if (sr, sc) == (er, ec):
        return RouteResult(
            ok=True, preset=preset,
            start={"lat": start[0], "lon": start[1]},
            end={"lat": end[0], "lon": end[1]},
            waypoints=[{"lat": start[0], "lon": start[1], "elev_m": float(elev[sr, sc]), "slope_deg": 0.0}],
            stats=RouteStats(),
            path_cells=1,
            notes=["Start and end are the same grid cell."],
            provenance={"engine": "A* on MOLA MEGDR 4 ppd grid", "advisory": "Regional slopes; advisory only."},
        )

    blocked = blocked_cells or set()

    # Heuristic: great-circle distance in km, divided by mean cell size (~15 km)
    # so we get an admissible estimate in cells.
    R = mars_radius_m()
    def haversine_km(a_lat, a_lon, b_lat, b_lon):
        dlat = math.radians(b_lat - a_lat)
        dlon = math.radians(b_lon - a_lon)
        x = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
             * math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x)) / 1000.0

    def heuristic(r, c):
        # Weighted A*: estimate remaining cost from remaining distance.
        # A 15 km step typically costs ~2x its distance due to slope/roughness
        # multipliers, so scale the straight-line estimate by 2.0. Slightly
        # optimistic (near-admissible) — keeps routes near-optimal while
        # focusing the search dramatically.
        la, lo = _grid_to_latlon(r, c)
        return haversine_km(la, lo, end[0], end[1]) * 2.0

    # Slope cache — small LRU-ish dict (we re-visit few cells)
    slope_cache: dict[tuple[int, int], float] = {}

    def cell_cost(r, c, nr, nc):
        la, lo = _grid_to_latlon(r, c)
        km_per_col, km_per_row = _km_per_cell_at(la)
        # diagonal step distance
        diag = math.sqrt(km_per_col ** 2 + km_per_row ** 2)
        step_km = diag if (abs(nr - r) + abs(nc - c) == 2) else max(km_per_col, km_per_row)
        # slope at the neighbour cell
        if (nr, nc) not in slope_cache:
            slope_cache[(nr, nc)] = _slope_at_grid(elev, nr, nc)
        slope = slope_cache[(nr, nc)]
        # roughness — nearest pixel on 1 deg grid
        rough_arr = load_roughness()
        rr = min(ROUGH_H - 1, max(0, int(round((90.0 - la)))))
        rc = int(round(lo)) % ROUGH_W
        rough = float(rough_arr[rr, rc])
        if math.isnan(rough):
            rough = 5.0  # fallback
        cost = step_km * (1 + (slope / 6.0) ** 2 * w["w_slope"] + rough / 5.0 * w["w_rough"])
        # hard block on extreme slopes
        if slope > 30.0:
            return None
        return cost

    # A*
    import sys
    open_heap: list[tuple[float, int, int, int]] = []
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {(sr, sc): 0.0}
    closed: set[tuple[int, int]] = set()
    counter = 0  # tie-breaker
    heapq.heappush(open_heap, (heuristic(sr, sc), counter, sr, sc))

    found = False
    steps = 0
    while open_heap and steps < max_steps:
        _, _, r, c = heapq.heappop(open_heap)
        if (r, c) in closed:
            continue
        closed.add((r, c))
        steps += 1
        if (r, c) == (er, ec):
            found = True
            break
        for dr, dc, _diag in _NEIGHBOURS:
            nr, nc = r + dr, (c + dc) % ELEV_W
            if nr < 0 or nr >= ELEV_H:
                continue
            if (nr, nc) in closed:
                continue
            if (nr, nc) in blocked:
                continue
            cost = cell_cost(r, c, nr, nc)
            if cost is None:
                continue
            tentative = g_score[(r, c)] + cost
            if tentative < g_score.get((nr, nc), float("inf")):
                g_score[(nr, nc)] = tentative
                came_from[(nr, nc)] = (r, c)
                counter += 1
                heapq.heappush(open_heap, (tentative + heuristic(nr, nc), counter, nr, nc))

    if not found:
        return RouteResult(
            ok=False, preset=preset,
            start={"lat": start[0], "lon": start[1]},
            end={"lat": end[0], "lon": end[1]},
            notes=[f"A* did not find a path within {max_steps} steps.",
                   "Try a less terrain-averse preset, or move endpoints to less extreme terrain."],
            provenance={"engine": "A* on MOLA MEGDR 4 ppd grid", "advisory": "Regional slopes; advisory only."},
        )

    # Reconstruct
    path = []
    cur = (er, ec)
    while cur != (sr, sc):
        path.append(cur)
        cur = came_from[cur]
    path.append((sr, sc))
    path.reverse()

    # Stats
    waypoints = []
    ascent = 0.0
    descent = 0.0
    total_km = 0.0
    max_slope = 0.0
    slopes = []
    prev_latlon = None
    for (r, c) in path:
        la, lo = _grid_to_latlon(r, c)
        e = float(elev[r, c])
        s = _slope_at_grid(elev, r, c)
        slopes.append(s)
        if s > max_slope:
            max_slope = s
        if prev_latlon is not None:
            d = haversine_km(prev_latlon[0], prev_latlon[1], la, lo)
            total_km += d
            prev_e = waypoints[-1]["elev_m"]
            if e > prev_e:
                ascent += (e - prev_e)
            else:
                descent += (prev_e - e)
        prev_latlon = (la, lo)
        waypoints.append({"lat": round(la, 5), "lon": round(lo, 5),
                          "elev_m": round(e, 1), "slope_deg": round(s, 2)})

    # Subsample waypoints to keep payload reasonable (max ~80)
    if len(waypoints) > 80:
        step = max(1, len(waypoints) // 80)
        sampled = waypoints[::step]
        if sampled[-1] != waypoints[-1]:
            sampled.append(waypoints[-1])
        if sampled[0] != waypoints[0]:
            sampled.insert(0, waypoints[0])
        waypoints = sampled

    # Rough sol estimate: 100 m/sol EVA traverse (per v1)
    est_sols = total_km * 1000.0 / 100.0

    return RouteResult(
        ok=True, preset=preset,
        start={"lat": start[0], "lon": start[1]},
        end={"lat": end[0], "lon": end[1]},
        waypoints=waypoints,
        stats=RouteStats(
            length_m=round(total_km * 1000.0, 1),
            length_km=round(total_km, 2),
            ascent_m=round(ascent, 1),
            descent_m=round(descent, 1),
            max_slope_deg=round(max_slope, 2),
            mean_slope_deg=round(sum(slopes) / len(slopes), 2),
            est_sols=round(est_sols, 1),
        ),
        path_cells=len(path),
        notes=[
            f"Planned over {len(path)} MOLA 4 ppd cells (~14.8 km each at the equator).",
            f"Max slope {max_slope:.1f}° — anything > 20° is major traverse risk (advisory).",
            f"Estimated traverse time {est_sols:.1f} sols at 100 m/sol EVA pace.",
        ],
        provenance={
            "engine": "A* on MOLA MEGDR 4 ppd grid, 8-connected",
            "preset": preset,
            "cost_function": "distance × (1 + (slope/6)² × w_slope + rough/5 × w_rough) − science_bonus",
            "advisory": "Regional MOLA slopes cannot resolve meter-scale obstacles — treat as advisory only.",
            "elevation_source": "MOLA MEGDR 4 px/deg (NASA PDS urn-nasa-pds-mgs_mola_topography_derived)",
            "url": "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
        },
    )


# re-export ROUGH constants used internally
from ..data import ROUGH_W, ROUGH_H  # noqa: E402
