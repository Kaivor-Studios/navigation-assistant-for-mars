"""REST + SSE routes for the NAM backend."""
from __future__ import annotations
import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from pydantic import BaseModel

from ..core.geo import (
    sample_elevation, sample_roughness, slope_at, pressure_estimate,
    hazard_at, elevation_profile, terrain_analyze,
)
from ..core.router import plan_route, PRESETS
from ..core.environment import (
    find_shelters, find_water, assess_radiation, assess_radiation_along_path,
)
from ..core.walk import walk_init, walk_terrain_patch, walk_pov_lookup, walk_list_povs, POV_LIBRARY
from ..core.assistant import list_tools, invoke_tool, chat_respond
from ..core.state import (
    create_node, get_node, list_nodes, update_node, delete_node,
    create_mission, get_mission, list_missions, update_mission_route,
    add_waypoint, add_stop_to_mission, delete_mission,
)
from ..core.sim import create_event, get_event, list_events, list_presence, presence_near
from ..data import load_json_data, normalize_lat, normalize_lon
from .models import NodeIn, RouteIn, MissionIn, WaypointIn, StopIn, ChatIn


router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health lives at /health (no prefix) — see main.py for the actual mount.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Layers + tiles
# ---------------------------------------------------------------------------

@router.get("/layers")
async def get_layers():
    d = load_json_data()
    return {
        "layers": d["LAYERS"],
        "registry": d["REGISTRY"],
        "provenance": "Curated from v1 NAM.DATA — OpenPlanetaryMap (verified CORS), NASA PDS, USGS.",
    }


@router.get("/layers/{layer_id}/tiles/{z}/{x}/{y}")
async def get_tile(layer_id: str, z: int, x: int, y: int, request: Request):
    """Proxy a map tile from the configured upstream URL.

    The proxy caches to disk and adds attribution headers. If the upstream
    is unreachable, returns 503 with a source link.
    """
    from ..core.tiles import fetch_tile
    result = await fetch_tile(layer_id, z, x, y)
    if result is None:
        raise HTTPException(503, detail={
            "error": "tile upstream unreachable",
            "layer_id": layer_id,
            "source_url": _layer_url(layer_id),
            "note": "See the layer registry for direct links.",
        })
    return Response(content=result["bytes"], media_type=result["media_type"],
                    headers={"Cache-Control": "public, max-age=86400",
                             "X-NAM-Source": _ascii_only(result["source_url"]),
                             "X-NAM-Credit": _ascii_only(result["credit"])})


def _ascii_only(s: str) -> str:
    """HTTP headers must be latin-1 encodable — strip non-ASCII chars."""
    return s.encode("ascii", "replace").decode("ascii")


def _layer_url(layer_id: str) -> str:
    for l in load_json_data()["LAYERS"]:
        if l["id"] == layer_id:
            return l.get("url", "")
    return ""


# ---------------------------------------------------------------------------
# Gazetteer / mission sites / instruments
# ---------------------------------------------------------------------------

@router.get("/gazetteer")
async def search_gazetteer(q: str = "", limit: int = Query(20, le=200)):
    d = load_json_data()
    feats = d["FEATURES"]
    if not q:
        return {"count": len(feats), "features": feats[:limit]}
    ql = q.lower()
    matches = [f for f in feats
               if ql in f["name"].lower()
               or ql in f["id"].lower()
               or ql in f.get("type", "").lower()
               or ql in " ".join(f.get("tags", [])).lower()]
    return {"count": len(matches), "features": matches[:limit]}


@router.get("/missions/sites")
async def list_mission_sites():
    d = load_json_data()
    return {"sites": d["SITES"], "orbiters": d["ORBITERS"]}


@router.get("/instruments")
async def list_instruments():
    return {"instruments": load_json_data()["INSTRUMENTS"]}


@router.get("/targets")
async def list_spectral_targets():
    return {"targets": load_json_data()["TARGETS"]}


# ---------------------------------------------------------------------------
# Geospatial
# ---------------------------------------------------------------------------

# Terrain tile cache (heightmaps for the Cesium terrain provider)
from functools import lru_cache


@lru_cache(maxsize=1024)
def _terrain_tile_cached(z: int, x: int, y: int, grid_size: int):
    """Compute a heightmap for a geographic quadtree tile. Cached."""
    n_x = 2 << z   # level 0: 2 columns
    n_y = 1 << z   # level 0: 1 row
    lon_min = -180.0 + 360.0 * x / n_x
    lon_max = -180.0 + 360.0 * (x + 1) / n_x
    lat_max = 90.0 - 180.0 * y / n_y
    lat_min = 90.0 - 180.0 * (y + 1) / n_y
    g = max(2, min(65, grid_size))
    heights = []
    hmin, hmax = float("inf"), float("-inf")
    for i in range(g):
        lat = lat_max - (lat_max - lat_min) * i / (g - 1)
        row = []
        for j in range(g):
            lon = lon_min + (lon_max - lon_min) * j / (g - 1)
            e = round(sample_elevation(lat, lon), 1)
            row.append(e)
            if e < hmin:
                hmin = e
            if e > hmax:
                hmax = e
        heights.append(row)
    return {
        "width": g,
        "height": g,
        "heights": heights,
        "extent": {
            "lon_min": lon_min, "lon_max": lon_max,
            "lat_min": lat_min, "lat_max": lat_max,
        },
        "min_m": hmin, "max_m": hmax,
        "provenance": {
            "elevation": "MOLA MEGDR 4 px/deg (NASA PDS urn-nasa-pds-mgs_mola_topography_derived)",
            "note": "Heights relative to the MOLA areoid, rendered above the Mars ellipsoid (areoid-ellipsoid difference not modelled).",
            "url": "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
        },
    }


@router.get("/terrain/tile/{z}/{x}/{y}")
async def get_terrain_tile(z: int, x: int, y: int, grid_size: int = 33):
    """Heightmap tile for a geographic quadtree (level 0 = 2x1 tiles).

    Used by the frontend's custom Cesium terrain provider to render real
    MOLA terrain on the globe.
    """
    if z < 0 or z > 10:
        raise HTTPException(400, "zoom level must be 0..10")
    n_x = 2 << z
    n_y = 1 << z
    if x < 0 or x >= n_x or y < 0 or y >= n_y:
        raise HTTPException(400, f"tile coordinates out of range for level {z}")
    return _terrain_tile_cached(z, x, y, grid_size)


@router.get("/elevation")
async def get_elevation(lat: float, lon: float):
    e = sample_elevation(lat, lon)
    s = slope_at(lat, lon)
    r = sample_roughness(lat, lon)
    p = pressure_estimate(e)
    return {
        "lat": round(normalize_lat(lat), 5), "lon": round(normalize_lon(lon), 5),
        "elev_m": round(e, 1),
        "slope_deg": (None if s is None else round(s, 2)),
        "roughness_m": (None if r is None else round(r, 2)),
        "pressure_mbar": p,
        "provenance": {
            "elevation": "MOLA MEGDR 4 px/deg (NASA PDS urn-nasa-pds-mgs_mola_topography_derived)",
            "roughness": "MOLA roughness 1 px/deg (NASA PDS)",
            "slope": "Derived from MOLA MEGDR 4 ppd, ±0.25 deg neighbourhood (~30 km)",
            "pressure": "Derived from MOLA areoid + simple scale-height model; advisory only",
            "url": "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
        },
    }


@router.get("/elevation/profile")
async def get_elevation_profile(points: str):
    """?points=lat1,lon1,lat2,lon2,..."""
    try:
        nums = [float(x) for x in points.split(",")]
    except ValueError:
        raise HTTPException(400, "points must be comma-separated numbers")
    if len(nums) % 2 != 0:
        raise HTTPException(400, "points must be even-length (lat,lon pairs)")
    pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    return {"profile": elevation_profile(pts), "count": len(pts)}


@router.get("/terrain/analyze")
async def get_terrain_analyze(lat: float, lon: float,
                              radius_km: float = 50.0,
                              resolution_deg: float | None = None):
    return terrain_analyze(lat, lon, radius_km, resolution_deg)


@router.get("/hazard")
async def get_hazard(lat: float, lon: float):
    h = hazard_at(lat, lon)
    return {
        "lat": h.lat, "lon": h.lon, "elev_m": h.elev_m,
        "slope_deg": h.slope_deg, "roughness_m": h.roughness_m,
        "pressure_mbar": h.pressure_mbar,
        "hazard_class": h.hazard_class, "hazard_score": h.hazard_score,
        "notes": h.notes, "provenance": h.provenance,
    }


# ---------------------------------------------------------------------------
# Environment: shelters, water, radiation
# ---------------------------------------------------------------------------

@router.get("/shelters")
async def get_shelters(lat: float, lon: float,
                       max_radius_km: float = 500.0, limit: int = 10):
    return find_shelters(lat, lon, max_radius_km, limit)


@router.get("/water")
async def get_water(lat: float, lon: float,
                    max_radius_km: float = 500.0, limit: int = 10):
    return find_water(lat, lon, max_radius_km, limit)


@router.get("/radiation")
async def get_radiation(lat: float | None = None, lon: float | None = None,
                        path: str | None = None):
    if path:
        try:
            nums = [float(x) for x in path.split(",")]
        except ValueError:
            raise HTTPException(400, "path must be comma-separated numbers")
        if len(nums) % 2 != 0:
            raise HTTPException(400, "path must be even-length")
        pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
        return assess_radiation_along_path(pts)
    if lat is None or lon is None:
        raise HTTPException(400, "either lat+lon or path is required")
    return assess_radiation(lat, lon)


# ---------------------------------------------------------------------------
# Environment: storms + presence (sim)
# ---------------------------------------------------------------------------

@router.get("/env/storms")
async def list_storms(kind: str | None = None):
    return {"events": list_events(kind=kind), "simulated": True}


@router.post("/env/storms/simulate")
async def simulate_storm(kind: str = "dust", lat: float = 0, lon: float = 0,
                          severity: str = "regional"):
    e = create_event(kind=kind, lat=lat, lon=lon, severity=severity)
    # Broadcast the alert to all WebSocket subscribers
    from ..ws.handlers import publish_storm_alert
    await publish_storm_alert({"type": "storm.alert", "event": e})
    return {"event": e}


@router.get("/env/storms/{event_id}")
async def get_storm(event_id: str):
    e = get_event(event_id)
    if not e:
        raise HTTPException(404, "event not found")
    return e


@router.get("/presence")
async def get_presence(lat: float | None = None, lon: float | None = None,
                      radius_km: float = 100.0):
    if lat is not None and lon is not None:
        return {"agents": presence_near(lat, lon, radius_km), "simulated": True}
    return {"agents": list_presence(), "simulated": True}


# ---------------------------------------------------------------------------
# Routes / planning
# ---------------------------------------------------------------------------

@router.post("/route")
async def plan_route_endpoint(req: RouteIn):
    r = plan_route(req.start_lat, req.start_lon,
                   req.end_lat, req.end_lon,
                   preset=req.preset)
    return {
        "ok": r.ok, "preset": r.preset,
        "start": r.start, "end": r.end,
        "waypoints": r.waypoints,
        "stats": (r.stats.__dict__ if r.stats else None),
        "path_cells": r.path_cells,
        "notes": r.notes, "provenance": r.provenance,
    }


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@router.get("/nodes")
async def list_nodes_endpoint(type: str | None = None,
                              bbox: str | None = None):
    bbox_tuple = None
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            bbox_tuple = (parts[0], parts[1], parts[2], parts[3])
        except (ValueError, IndexError):
            raise HTTPException(400, "bbox must be lat_min,lon_min,lat_max,lon_max")
    return {"nodes": list_nodes(type, bbox_tuple)}


@router.post("/nodes")
async def create_node_endpoint(req: NodeIn):
    n = create_node(req.name, req.type, req.lat, req.lon, req.radius_m, req.properties)
    return {"node": n}


@router.get("/nodes/{node_id}")
async def get_node_endpoint(node_id: str):
    n = get_node(node_id)
    if not n:
        raise HTTPException(404, "node not found")
    return n


@router.patch("/nodes/{node_id}")
async def update_node_endpoint(node_id: str, req: dict):
    n = update_node(node_id, req)
    if not n:
        raise HTTPException(404, "node not found")
    return {"node": n}


@router.delete("/nodes/{node_id}")
async def delete_node_endpoint(node_id: str):
    if not delete_node(node_id):
        raise HTTPException(404, "node not found")
    return {"deleted": True, "id": node_id}


# ---------------------------------------------------------------------------
# Missions / plans
# ---------------------------------------------------------------------------

@router.get("/plans")
async def list_plans_endpoint():
    return {"missions": list_missions()}


@router.post("/plans")
async def create_plan_endpoint(req: MissionIn):
    m = create_mission(req.name, req.objective, req.kind)
    return {"mission": m}


@router.get("/plans/{mission_id}")
async def get_plan_endpoint(mission_id: str):
    m = get_mission(mission_id)
    if not m:
        raise HTTPException(404, "mission not found")
    return m


@router.delete("/plans/{mission_id}")
async def delete_plan_endpoint(mission_id: str):
    if not delete_mission(mission_id):
        raise HTTPException(404, "mission not found")
    return {"deleted": True, "id": mission_id}


@router.post("/plans/{mission_id}/waypoints")
async def add_waypoint_endpoint(mission_id: str, req: WaypointIn):
    wp = add_waypoint(mission_id, {"lat": req.lat, "lon": req.lon, "name": req.name})
    if wp is None:
        raise HTTPException(404, "mission not found")
    return {"waypoint": wp}


@router.post("/plans/{mission_id}/stops")
async def add_stop_endpoint(mission_id: str, req: StopIn):
    s = add_stop_to_mission(mission_id, {"lat": req.lat, "lon": req.lon,
                                          "reason": req.reason, "activity": req.activity})
    if s is None:
        raise HTTPException(404, "mission not found")
    return {"stop": s}


# ---------------------------------------------------------------------------
# Walk View
# ---------------------------------------------------------------------------

@router.get("/walk/init")
async def walk_init_endpoint(lat: float, lon: float, heading_deg: float = 0.0):
    return walk_init(lat, lon, heading_deg=heading_deg)


@router.get("/walk/terrain")
async def walk_terrain_endpoint(lat: float, lon: float,
                                radius_m: float = 500.0,
                                resolution_m: float = 25.0):
    return walk_terrain_patch(lat, lon, radius_m, resolution_m)


@router.get("/walk/pov")
async def walk_pov_endpoint(lat: float, lon: float, max_radius_km: float = 100.0):
    return walk_pov_lookup(lat, lon, max_radius_km)


@router.get("/walk/povs")
async def walk_list_povs_endpoint():
    return {"count": len(POV_LIBRARY), "povs": walk_list_povs()}


# ---------------------------------------------------------------------------
# Assistant (deterministic, OpenAI-compatible chat shape)
# ---------------------------------------------------------------------------

@router.get("/assistant/tools")
async def list_tools_endpoint():
    return {"tools": list_tools()}


@router.post("/assistant/tool/{tool_name}")
async def invoke_tool_endpoint(tool_name: str, args: dict):
    return {"tool": tool_name, "result": invoke_tool(tool_name, args)}


@router.post("/assistant/chat")
async def chat_endpoint(req: ChatIn):
    """Deterministic chat. Streams as SSE with tool-activity events.

    The response shape is OpenAI-compatible so a real LLM can replace this
    endpoint without breaking the UI. Each event is a JSON object on its
    own line, prefixed with "data: ".

    Event types:
      - {type:"role", role:"assistant"}
      - {type:"token", text:"..."}            (natural-language text, chunked)
      - {type:"tool_call", tool, args}         (when the assistant invokes a tool)
      - {type:"tool_result", tool, result_summary}
      - {type:"sources", sources:[...]}
      - {type:"fly_to", lat, lon}              (UI hint to fly the camera)
      - {type:"done"}
    """
    async def event_stream():
        turn = chat_respond(req.message, mission_id=req.mission_id)
        yield _sse({"type": "role", "role": "assistant"})
        # Chunk the text into ~10-word pieces to mimic token streaming
        text = turn.get("text", "")
        words = text.split()
        for i in range(0, len(words), 5):
            chunk = " ".join(words[i:i + 5]) + " "
            yield _sse({"type": "token", "text": chunk})
            await asyncio.sleep(0.02)
        if turn.get("fly_to"):
            yield _sse({"type": "fly_to", **turn["fly_to"]})
        for tc in turn.get("tool_calls", []):
            yield _sse({"type": "tool_call", "tool": tc["tool"], "args": tc["args"]})
            yield _sse({"type": "tool_result", "tool": tc["tool"],
                        "result_summary": tc["result_summary"]})
        if turn.get("result"):
            yield _sse({"type": "result", "result": turn["result"]})
        if turn.get("sources"):
            yield _sse({"type": "sources", "sources": turn["sources"]})
        yield _sse({"type": "done"})
    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
