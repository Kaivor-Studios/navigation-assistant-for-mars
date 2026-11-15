"""In-memory state store for nodes, plans (missions), and events.

For the hackathon we use an in-memory dict keyed by id. This is replaced with
SQLite/PostGIS in the production v2 plan.
"""
from __future__ import annotations
import uuid
import time
from typing import Any

# In-memory stores
_NODES: dict[str, dict] = {}
_MISSIONS: dict[str, dict] = {}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def create_node(name: str, type: str, lat: float, lon: float,
                radius_m: float = 0.0, properties: dict | None = None) -> dict:
    nid = _new_id("node")
    node = {
        "id": nid,
        "name": name,
        "type": type,  # waypoint|cache|shelter|water|hazard|poi|person|area
        "lat": lat,
        "lon": lon,
        "radius_m": radius_m,
        "properties": properties or {},
        "created_at": time.time(),
        "provenance": {
            "elevation": "MOLA MEGDR 4 px/deg (NASA PDS)",
            "note": "User-created node; advisory only.",
        },
    }
    _NODES[nid] = node
    return node


def get_node(node_id: str) -> dict | None:
    return _NODES.get(node_id)


def list_nodes(node_type: str | None = None, bbox: tuple[float, float, float, float] | None = None) -> list[dict]:
    """List nodes, optionally filtered by type and/or bbox (lat_min, lon_min, lat_max, lon_max)."""
    out = []
    for n in _NODES.values():
        if node_type and n["type"] != node_type:
            continue
        if bbox:
            lat_min, lon_min, lat_max, lon_max = bbox
            if not (lat_min <= n["lat"] <= lat_max and lon_min <= n["lon"] <= lon_max):
                continue
        out.append(n)
    return out


def update_node(node_id: str, updates: dict) -> dict | None:
    if node_id not in _NODES:
        return None
    for k, v in updates.items():
        if k == "id":
            continue
        _NODES[node_id][k] = v
    return _NODES[node_id]


def delete_node(node_id: str) -> bool:
    return _NODES.pop(node_id, None) is not None


# ---------------------------------------------------------------------------
# Missions / plans
# ---------------------------------------------------------------------------

def create_mission(name: str, objective: str, kind: str = "route") -> dict:
    mid = _new_id("mission")
    m = {
        "id": mid,
        "name": name,
        "objective": objective,
        "kind": kind,  # route|area|evacuation|survey
        "start": None,
        "end": None,
        "waypoints": [],
        "stops": [],
        "route": None,
        "hazards": [],
        "assumptions": [],
        "status": "draft",
        "created_at": time.time(),
    }
    _MISSIONS[mid] = m
    return m


def get_mission(mission_id: str) -> dict | None:
    return _MISSIONS.get(mission_id)


def list_missions() -> list[dict]:
    return list(_MISSIONS.values())


def update_mission_route(mission_id: str, route_result) -> dict | None:
    if mission_id not in _MISSIONS:
        return None
    _MISSIONS[mission_id]["route"] = {
        "ok": route_result.ok,
        "preset": route_result.preset,
        "start": route_result.start,
        "end": route_result.end,
        "waypoints": route_result.waypoints,
        "stats": route_result.stats.__dict__ if route_result.stats else None,
        "path_cells": route_result.path_cells,
        "notes": route_result.notes,
        "provenance": route_result.provenance,
    }
    return _MISSIONS[mission_id]


def add_waypoint(mission_id: str, waypoint: dict) -> dict | None:
    if mission_id not in _MISSIONS:
        return None
    wp = {
        "id": _new_id("wp"),
        "lat": waypoint["lat"],
        "lon": waypoint["lon"],
        "name": waypoint.get("name", f"WP{len(_MISSIONS[mission_id]['waypoints']) + 1}"),
    }
    _MISSIONS[mission_id]["waypoints"].append(wp)
    # If start/end empty, fill them
    m = _MISSIONS[mission_id]
    if m["start"] is None:
        m["start"] = {"lat": wp["lat"], "lon": wp["lon"]}
    elif m["end"] is None:
        m["end"] = {"lat": wp["lat"], "lon": wp["lon"]}
    else:
        # update end to the latest
        m["end"] = {"lat": wp["lat"], "lon": wp["lon"]}
    return wp


def add_stop_to_mission(mission_id: str, stop: dict) -> dict | None:
    if mission_id not in _MISSIONS:
        return None
    s = {
        "id": _new_id("stop"),
        "lat": stop["lat"],
        "lon": stop["lon"],
        "reason": stop.get("reason", ""),
        "activity": stop.get("activity", ""),
    }
    _MISSIONS[mission_id]["stops"].append(s)
    return s


def delete_mission(mission_id: str) -> bool:
    return _MISSIONS.pop(mission_id, None) is not None
