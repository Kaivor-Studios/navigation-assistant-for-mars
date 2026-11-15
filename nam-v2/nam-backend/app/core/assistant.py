"""Deterministic assistant — 16 v1 tools + 8 new tools.

This is the deterministic intent router + tool dispatcher ported from
NAM.ASSISTANT in v1. It does NOT call an LLM — the response is rule-based.
The chat endpoint (/api/v1/assistant/chat) wraps this with an OpenAI-compatible
SSE shape so a real LLM can be dropped in later without breaking the UI.

Tool list (matches v1 verbatim, plus 8 new):
  v1 (16): search_planetary_location, get_current_map_context,
    search_nasa_datasets, get_location_observations, activate_map_layer,
    compare_geological_layers, get_elevation_profile, analyze_terrain,
    identify_hazards, find_scientific_targets, create_mission,
    generate_route, optimize_route, add_waypoint, explain_route, export_mission
  new (8): add_node, add_stop, plan_area, plan_storm_response,
    find_water, find_shelter, assess_radiation, simulate_storm
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from ..data import load_json_data, normalize_lat, normalize_lon
from .geo import (
    sample_elevation, slope_at, sample_roughness, hazard_at,
    elevation_profile, terrain_analyze,
)
from .router import plan_route, PRESETS
from .environment import find_shelters, find_water, assess_radiation, assess_radiation_along_path
from .walk import walk_init, walk_pov_lookup


# ---------------------------------------------------------------------------
# Tool registry — name -> (description, schema, handler)
# ---------------------------------------------------------------------------

@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    output_schema: dict
    handler: Callable[[dict], dict]


_REGISTRY: dict[str, ToolDef] = {}


def register_tool(name: str, description: str, input_schema: dict, output_schema: dict):
    def deco(fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
        _REGISTRY[name] = ToolDef(name, description, input_schema, output_schema, fn)
        return fn
    return deco


def list_tools() -> list[dict]:
    return [
        {"name": t.name, "description": t.description,
         "input_schema": t.input_schema, "output_schema": t.output_schema}
        for t in _REGISTRY.values()
    ]


def invoke_tool(name: str, args: dict) -> dict:
    if name not in _REGISTRY:
        return {"error": f"unknown tool: {name}", "available": list(_REGISTRY.keys())}
    try:
        return _REGISTRY[name].handler(args or {})
    except Exception as e:
        return {"error": str(e), "tool": name, "args": args}


# ---------------------------------------------------------------------------
# v1 tools (16)
# ---------------------------------------------------------------------------

@register_tool(
    "search_planetary_location",
    "Search the IAU Mars gazetteer (102 features) by name or type.",
    {"query": "str", "limit": "int, default 10"},
    {"results": "list of {id,name,type,lat,lon,desc,tags}"},
)
def t_search_planetary_location(args):
    q = (args.get("query") or "").strip().lower()
    limit = int(args.get("limit", 10))
    feats = load_json_data()["FEATURES"]
    if not q:
        return {"results": feats[:limit]}
    matches = [f for f in feats
               if q in f.get("name", "").lower()
               or q in f.get("id", "").lower()
               or q in " ".join(f.get("tags", [])).lower()
               or q in f.get("type", "").lower()]
    return {"results": matches[:limit], "count": len(matches)}


@register_tool(
    "get_current_map_context",
    "Summarize what's near a (lat, lon) on Mars: gazetteer features, mission sites, terrain.",
    {"lat": "float", "lon": "float", "radius_km": "float, default 500"},
    {"lat": "float", "lon": "float", "features": "list", "sites": "list", "terrain": "dict"},
)
def t_get_current_map_context(args):
    import math
    lat = float(args["lat"]); lon = float(args["lon"])
    radius = float(args.get("radius_km", 500))
    R = 3389500.0
    feats = load_json_data()["FEATURES"]
    sites = load_json_data()["SITES"]
    def haversine(a_lat, a_lon, b_lat, b_lon):
        dlat = math.radians(b_lat - a_lat)
        dlon = math.radians(b_lon - a_lon)
        x = math.sin(dlat/2)**2 + math.cos(math.radians(a_lat))*math.cos(math.radians(b_lat))*math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1-x)) / 1000.0
    nearby_feats = sorted(
        [{"id": f["id"], "name": f["name"], "type": f["type"],
          "lat": f["lat"], "lon": f["lon"],
          "distance_km": round(haversine(lat, lon, f["lat"], f["lon"]), 1)}
         for f in feats],
        key=lambda x: x["distance_km"]
    )[:5]
    nearby_sites = sorted(
        [{"id": s["id"], "name": s["name"], "agency": s["agency"], "kind": s["kind"],
          "lat": s["lat"], "lon": s["lon"], "date": s["date"],
          "distance_km": round(haversine(lat, lon, s["lat"], s["lon"]), 1)}
         for s in sites],
        key=lambda x: x["distance_km"]
    )[:3]
    elev = sample_elevation(lat, lon)
    slope = slope_at(lat, lon)
    return {
        "lat": round(lat, 5), "lon": round(lon, 5),
        "radius_km": radius,
        "elev_m": round(elev, 1),
        "slope_deg": (None if slope is None else round(slope, 2)),
        "features_nearby": nearby_feats,
        "mission_sites_nearby": nearby_sites,
    }


@register_tool(
    "search_nasa_datasets",
    "Search the curated catalog of NASA/USGS Mars datasets + instruments.",
    {"query": "str"},
    {"instruments": "list", "registry": "list", "orbiters": "list"},
)
def t_search_nasa_datasets(args):
    q = (args.get("query") or "").strip().lower()
    d = load_json_data()
    def match(item):
        if not q: return True
        text = json.dumps(item, default=str).lower()
        return q in text
    return {
        "instruments": [i for i in d["INSTRUMENTS"] if match(i)],
        "orbiters": [o for o in d["ORBITERS"] if match(o)],
        "registry": [r for r in d["REGISTRY"] if match(r)],
    }


@register_tool(
    "get_location_observations",
    "Get available observations (instruments, datasets) for a (lat, lon).",
    {"lat": "float", "lon": "float"},
    {"elev_m": "float", "instruments_with_coverage": "list", "layers": "list"},
)
def t_get_location_observations(args):
    lat = float(args["lat"]); lon = float(args["lon"])
    d = load_json_data()
    elev = sample_elevation(lat, lon)
    return {
        "lat": round(lat, 5), "lon": round(lon, 5),
        "elev_m": round(elev, 1),
        "instruments_with_coverage": d["INSTRUMENTS"][:5],
        "layers": d["LAYERS"],
    }


@register_tool(
    "activate_map_layer",
    "Get the URL template for a specific layer in the registry.",
    {"layer_id": "str"},
    {"layer": "dict"},
)
def t_activate_map_layer(args):
    layer_id = args.get("layer_id")
    d = load_json_data()
    for l in d["LAYERS"]:
        if l["id"] == layer_id:
            return {"layer": l, "activated": True}
    return {"error": f"unknown layer: {layer_id}", "available": [l["id"] for l in d["LAYERS"]]}


@register_tool(
    "compare_geological_layers",
    "Compare available map layers by coverage, resolution, source.",
    {},
    {"comparison": "list of layer dicts"},
)
def t_compare_geological_layers(args):
    d = load_json_data()
    return {
        "comparison": [
            {"id": l["id"], "name": l["name"], "kind": l["kind"],
             "coverage": l.get("coverage"), "resolution": l.get("resolution"),
             "credit": l.get("credit")}
            for l in d["LAYERS"]
        ]
    }


@register_tool(
    "get_elevation_profile",
    "Trace an elevation profile along a path of (lat, lon) points.",
    {"points": "list of [lat, lon]"},
    {"profile": "list of {lat, lon, elev_m, slope_deg, pressure_mbar}"},
)
def t_get_elevation_profile(args):
    pts = [(float(p[0]), float(p[1])) for p in args["points"]]
    return {"profile": elevation_profile(pts), "count": len(pts)}


@register_tool(
    "analyze_terrain",
    "Compute a local terrain grid (elevation, slope, hazard) around a point.",
    {"lat": "float", "lon": "float", "radius_km": "float, default 50", "resolution_deg": "float, optional"},
    {"grid": "dict"},
)
def t_analyze_terrain(args):
    lat = float(args["lat"]); lon = float(args["lon"])
    radius = float(args.get("radius_km", 50))
    res = args.get("resolution_deg")
    if res is not None: res = float(res)
    return terrain_analyze(lat, lon, radius, res)


@register_tool(
    "identify_hazards",
    "Composite hazard readout (slope + roughness + elevation) at a point.",
    {"lat": "float", "lon": "float"},
    {"hazard": "HazardReadout"},
)
def t_identify_hazards(args):
    h = hazard_at(float(args["lat"]), float(args["lon"]))
    return {
        "lat": h.lat, "lon": h.lon, "elev_m": h.elev_m,
        "slope_deg": h.slope_deg, "roughness_m": h.roughness_m,
        "pressure_mbar": h.pressure_mbar,
        "hazard_class": h.hazard_class, "hazard_score": h.hazard_score,
        "notes": h.notes, "provenance": h.provenance,
    }


@register_tool(
    "find_scientific_targets",
    "Find curated literature-cited spectral/science targets near a (lat, lon).",
    {"lat": "float", "lon": "float", "max_radius_km": "float, default 1000"},
    {"targets": "list"},
)
def t_find_scientific_targets(args):
    import math
    lat = float(args["lat"]); lon = float(args["lon"])
    max_r = float(args.get("max_radius_km", 1000))
    R = 3389500.0
    def haversine(a_lat, a_lon, b_lat, b_lon):
        dlat = math.radians(b_lat - a_lat); dlon = math.radians(b_lon - a_lon)
        x = math.sin(dlat/2)**2 + math.cos(math.radians(a_lat))*math.cos(math.radians(b_lat))*math.sin(dlon/2)**2
        return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1-x)) / 1000.0
    d = load_json_data()
    res = []
    for t in d["TARGETS"]:
        dist = haversine(lat, lon, t["lat"], t["lon"])
        if dist <= max_r:
            res.append({**t, "distance_km": round(dist, 1)})
    res.sort(key=lambda x: x["distance_km"])
    return {"query": {"lat": lat, "lon": lon, "max_radius_km": max_r},
            "count": len(res), "targets": res}


@register_tool(
    "create_mission",
    "Create a new mission in the plans store (server-side state).",
    {"name": "str", "objective": "str", "kind": "str (route|area|evacuation|survey)"},
    {"mission_id": "str", "name": "str"},
)
def t_create_mission(args):
    from .state import create_mission as _cm
    m = _cm(args.get("name", "Untitled"), args.get("objective", ""), args.get("kind", "route"))
    return {"mission_id": m["id"], "name": m["name"], "kind": m["kind"]}


@register_tool(
    "generate_route",
    "Plan an A* route between two points on the MOLA grid.",
    {"start_lat": "float", "start_lon": "float", "end_lat": "float", "end_lon": "float",
     "preset": "str (balanced|terrain|speed)"},
    {"route": "RouteResult"},
)
def t_generate_route(args):
    r = plan_route(
        float(args["start_lat"]), float(args["start_lon"]),
        float(args["end_lat"]), float(args["end_lon"]),
        preset=args.get("preset", "balanced"),
    )
    return {
        "ok": r.ok, "preset": r.preset,
        "start": r.start, "end": r.end,
        "waypoints": r.waypoints,
        "stats": (r.stats.__dict__ if r.stats else None),
        "path_cells": r.path_cells,
        "notes": r.notes, "provenance": r.provenance,
    }


@register_tool(
    "optimize_route",
    "Re-plan an existing route with a different preset.",
    {"mission_id": "str", "preset": "str"},
    {"route": "RouteResult"},
)
def t_optimize_route(args):
    from .state import get_mission, update_mission_route
    m = get_mission(args["mission_id"])
    if not m:
        return {"error": "mission not found"}
    if "start" not in m or "end" not in m:
        return {"error": "mission has no start/end"}
    r = plan_route(m["start"]["lat"], m["start"]["lon"],
                   m["end"]["lat"], m["end"]["lon"],
                   preset=args.get("preset", "terrain"))
    update_mission_route(m["id"], r)
    return {
        "ok": r.ok, "preset": r.preset,
        "waypoints": r.waypoints,
        "stats": (r.stats.__dict__ if r.stats else None),
        "notes": r.notes,
    }


@register_tool(
    "add_waypoint",
    "Add a waypoint to an existing mission.",
    {"mission_id": "str", "lat": "float", "lon": "float", "name": "str"},
    {"mission_id": "str", "waypoint": "dict"},
)
def t_add_waypoint(args):
    from .state import add_waypoint
    wp = {"lat": float(args["lat"]), "lon": float(args["lon"]),
          "name": args.get("name", f"WP")}
    added = add_waypoint(args["mission_id"], wp)
    if added is None:
        return {"error": "mission not found"}
    return {"mission_id": args["mission_id"], "waypoint": added}


@register_tool(
    "explain_route",
    "Generate a human-readable explanation of a route plan.",
    {"mission_id": "str"},
    {"explanation": "str"},
)
def t_explain_route(args):
    from .state import get_mission
    m = get_mission(args["mission_id"])
    if not m:
        return {"error": "mission not found"}
    r = m.get("route")
    if not r:
        return {"error": "mission has no route yet"}
    stats = r.get("stats") or {}
    parts = []
    parts.append(f"Route planned from ({r['start']['lat']:.3f}, {r['start']['lon']:.3f}) to ({r['end']['lat']:.3f}, {r['end']['lon']:.3f}) using the '{r['preset']}' preset.")
    if stats:
        parts.append(f"Total length {stats.get('length_km', 0):.1f} km ({stats.get('length_m', 0):.0f} m), ascending {stats.get('ascent_m', 0):.0f} m and descending {stats.get('descent_m', 0):.0f} m.")
        parts.append(f"Maximum slope encountered: {stats.get('max_slope_deg', 0):.1f}° (mean {stats.get('mean_slope_deg', 0):.1f}°).")
        parts.append(f"Estimated traverse time at 100 m/sol EVA pace: {stats.get('est_sols', 0):.1f} sols.")
    if r.get("waypoints"):
        parts.append(f"Path contains {len(r['waypoints'])} sampled waypoints.")
    return {"explanation": " ".join(parts), "provenance": r.get("provenance", {})}


@register_tool(
    "export_mission",
    "Export a mission as a JSON object (downloadable).",
    {"mission_id": "str", "format": "str (json|csv|kml), default json"},
    {"mission": "dict", "format": "str"},
)
def t_export_mission(args):
    from .state import get_mission
    m = get_mission(args["mission_id"])
    if not m:
        return {"error": "mission not found"}
    fmt = args.get("format", "json")
    if fmt == "json":
        return {"format": "json", "mission": m}
    elif fmt == "csv" and m.get("route", {}).get("waypoints"):
        rows = ["lat,lon,elev_m,slope_deg"]
        for wp in m["route"]["waypoints"]:
            rows.append(f"{wp['lat']},{wp['lon']},{wp['elev_m']},{wp['slope_deg']}")
        return {"format": "csv", "csv": "\n".join(rows)}
    elif fmt == "kml" and m.get("route", {}).get("waypoints"):
        coords = " ".join(f"{wp['lon']},{wp['lat']},{wp['elev_m']}" for wp in m["route"]["waypoints"])
        kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>{m['name']}</name>
<Placemark><LineString><coordinates>{coords}</coordinates></LineString></Placemark>
</Document></kml>"""
        return {"format": "kml", "kml": kml}
    return {"error": f"unsupported format: {fmt}"}


# ---------------------------------------------------------------------------
# New tools (8)
# ---------------------------------------------------------------------------

@register_tool(
    "add_node",
    "Create a named node at coordinates (any type).",
    {"name": "str", "type": "str (waypoint|cache|shelter|water|hazard|poi|person|area)",
     "lat": "float", "lon": "float", "radius_m": "float, optional"},
    {"node": "dict"},
)
def t_add_node(args):
    from .state import create_node
    node = create_node(
        name=args["name"],
        type=args["type"],
        lat=float(args["lat"]),
        lon=float(args["lon"]),
        radius_m=float(args.get("radius_m", 0)),
        properties=args.get("properties", {}),
    )
    return {"node": node}


@register_tool(
    "add_stop",
    "Insert an ordered stop into an existing mission plan with a stated reason.",
    {"mission_id": "str", "lat": "float", "lon": "float", "reason": "str", "activity": "str"},
    {"mission_id": "str", "stop": "dict"},
)
def t_add_stop(args):
    from .state import add_stop_to_mission
    stop = {"lat": float(args["lat"]), "lon": float(args["lon"]),
            "reason": args.get("reason", ""), "activity": args.get("activity", "")}
    res = add_stop_to_mission(args["mission_id"], stop)
    if res is None:
        return {"error": "mission not found"}
    return {"mission_id": args["mission_id"], "stop": stop}


@register_tool(
    "plan_area",
    "Define and score a survey/operations area for stated objectives.",
    {"lat": "float", "lon": "float", "radius_km": "float", "objectives": "list of str"},
    {"area": "dict"},
)
def t_plan_area(args):
    lat = float(args["lat"]); lon = float(args["lon"])
    radius = float(args["radius_km"])
    objectives = args.get("objectives", [])
    ta = terrain_analyze(lat, lon, radius)
    # Score per objective (rule-based)
    scores = {}
    for obj in objectives:
        o = obj.lower()
        if "geolog" in o or "rock" in o:
            scores[obj] = 0.7 if ta["cells"][0]["rough_m"] and ta["cells"][0]["rough_m"] > 5 else 0.4
        elif "water" in o or "ice" in o:
            scores[obj] = 0.6 if abs(lat) > 30 else 0.2
        elif "image" in o or "photo" in o:
            scores[obj] = 0.9  # always possible
        elif "shelter" in o:
            scores[obj] = 0.5
        else:
            scores[obj] = 0.5
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius,
        "objectives": objectives,
        "scores": scores,
        "terrain_summary": {
            "grid_shape": ta["grid_shape"],
            "extent": ta["extent"],
            "min_elev_m": min(c["elev_m"] for c in ta["cells"]),
            "max_elev_m": max(c["elev_m"] for c in ta["cells"]),
            "max_slope_deg": max((c["slope_deg"] or 0) for c in ta["cells"]),
        },
        "provenance": ta["provenance"],
    }


@register_tool(
    "plan_storm_response",
    "Plan an evacuation response to a storm/SEP event: shelters, water, route, dose.",
    {"event_id": "str", "current_lat": "float", "current_lon": "float"},
    {"plan": "dict"},
)
def t_plan_storm_response(args):
    from .sim import get_event
    event = get_event(args["event_id"])
    if not event:
        return {"error": f"event not found: {args['event_id']}"}
    cur_lat = float(args["current_lat"]); cur_lon = float(args["current_lon"])
    # Find nearest shelter
    shelters = find_shelters(cur_lat, cur_lon, max_radius_km=1000, limit=3)
    # Find water near the shelter
    evac_plan = {
        "event": {
            "id": event["id"], "kind": event["kind"], "severity": event["severity"],
            "duration_sols": event["duration_sols"],
        },
        "current_position": {"lat": cur_lat, "lon": cur_lon},
        "shelters_within_reach": shelters["shelters"],
        "recommended_shelter": shelters["shelters"][0] if shelters["shelters"] else None,
        "provenance": {
            "engine": "JEV deterministic storm-response planner (v2)",
            "advisory": "Advisory only; field judgement required.",
        },
    }
    if shelters["shelters"]:
        sh = shelters["shelters"][0]
        r = plan_route(cur_lat, cur_lon, sh["lat"], sh["lon"], preset="terrain")
        evac_plan["route_to_shelter"] = {
            "ok": r.ok, "preset": r.preset,
            "stats": (r.stats.__dict__ if r.stats else None),
            "waypoints_count": len(r.waypoints),
            "notes": r.notes,
        }
        # Dose along the path
        if r.waypoints:
            dose = assess_radiation_along_path([(w["lat"], w["lon"]) for w in r.waypoints[:20]])
            evac_plan["dose_estimate"] = dose
    return evac_plan


@register_tool(
    "find_water",
    "Find water-ice candidates near a point (SWIM-derived proxy).",
    {"lat": "float", "lon": "float", "max_radius_km": "float, default 500"},
    {"water_candidates": "list"},
)
def t_find_water(args):
    return find_water(float(args["lat"]), float(args["lon"]),
                      max_radius_km=float(args.get("max_radius_km", 500)))


@register_tool(
    "find_shelter",
    "Find shelter candidates near a point, scored on 4 axes.",
    {"lat": "float", "lon": "float", "max_radius_km": "float, default 500"},
    {"shelters": "list"},
)
def t_find_shelter(args):
    return find_shelters(float(args["lat"]), float(args["lon"]),
                         max_radius_km=float(args.get("max_radius_km", 500)))


@register_tool(
    "assess_radiation",
    "Estimate radiation dose at a point or along a path.",
    {"lat": "float, optional", "lon": "float, optional",
     "path": "list of [lat, lon], optional"},
    {"dose": "dict"},
)
def t_assess_radiation(args):
    if "path" in args:
        pts = [(float(p[0]), float(p[1])) for p in args["path"]]
        return assess_radiation_along_path(pts)
    return assess_radiation(float(args["lat"]), float(args["lon"]))


@register_tool(
    "simulate_storm",
    "Generate a synthetic dust or SEP event for drills.",
    {"kind": "str (dust|sep)", "lat": "float", "lon": "float", "severity": "str (regional|planet_encircling|X-flare-class)"},
    {"event": "dict"},
)
def t_simulate_storm(args):
    from .sim import create_event
    e = create_event(
        kind=args.get("kind", "dust"),
        lat=float(args.get("lat", 0)), lon=float(args.get("lon", 0)),
        severity=args.get("severity", "regional"),
    )
    return {"event": e}


# ---------------------------------------------------------------------------
# Walk view (extra tool — not in v1's 16, but useful for the chat)
# ---------------------------------------------------------------------------

@register_tool(
    "enter_walk_view",
    "Initialize a first-person Walk View at a location.",
    {"lat": "float", "lon": "float", "heading_deg": "float, default 0"},
    {"walk": "dict"},
)
def t_enter_walk_view(args):
    return walk_init(float(args["lat"]), float(args["lon"]),
                    heading_deg=float(args.get("heading_deg", 0)))


# ---------------------------------------------------------------------------
# Deterministic intent router — matches user phrases to tools
# ---------------------------------------------------------------------------

INTENT_PATTERNS: list[tuple[re.Pattern, str, dict]] = [
    (re.compile(r"\b(hi|hello|hey|help|what can you do)\b", re.I), "_help", {}),
    # Explicit action verbs first — "find shelters near X" must beat "X" alone.
    (re.compile(r"\b(route|path|plan (a route|the route)|navigate|drive|from .+ to .+)\b", re.I), "generate_route", {}),
    (re.compile(r"\b(plan )?(storm|sep|dust|solar particle) (response|evac|evacuation|plan|drill)\b", re.I),
     "plan_storm_response", {}),
    (re.compile(r"\b(storm|dust|sep|solar particle|space weather)\b", re.I), "simulate_storm", {"kind": "dust", "severity": "regional"}),
    (re.compile(r"\b(water|ice|h2o|waters?)\b", re.I), "find_water", {}),
    (re.compile(r"\b(shelters?|hide|cave|lava tubes?|crater shelters?)\b", re.I), "find_shelter", {}),
    (re.compile(r"\b(radiation|dose|rad|sievert|msv)\b", re.I), "assess_radiation", {}),
    (re.compile(r"\b(walk|first person|3d view|street view|look around)\b", re.I), "enter_walk_view", {}),
    # Only AFTER explicit action verbs do we match named features (so a feature
    # mention alone triggers a fly-to, but "find shelters near Olympus Mons"
    # already matched find_shelter above).
    (re.compile(r"\b(deepest|lowest (point|place)|hellas)\b", re.I), "_fly_and_say",
     {"text": "The deepest point is in <b>Hellas Planitia</b>: ≈-8.1 km in the MEGDR grid (typical floor ≈-7.1 km), inside a ~2,300 km impact basin.",
      "lat": -42.4, "lon": 70.0, "src": ["MEGDR 4 ppd (embedded)", "IAU Gazetteer"]}),
    (re.compile(r"\b(tallest|highest (point|place|volcano)|olympus)\b", re.I), "_fly_and_say",
     {"text": "The tallest volcano is <b>Olympus Mons</b>: ~21 km above the MOLA areoid, ~600 km wide.",
      "lat": 18.65, "lon": 226.2, "src": ["IAU Gazetteer", "MOLA: Smith et al. (2001)"]}),
    (re.compile(r"\b(jezero|perseverance)\b", re.I), "_fly_and_say",
     {"text": "<b>Jezero crater</b> at 18.4°N, 77.7°E — Perseverance landing site. Delta deposits, hydrated minerals, carbonate-bearing formations.",
      "lat": 18.4447, "lon": 77.4508, "src": ["NASA/JPL Perseverance mission"]}),
    (re.compile(r"\b(gale|curiosity|mount sharp|aeolis)\b", re.I), "_fly_and_say",
     {"text": "<b>Gale crater</b> at 5.4°S, 137.4°E — Curiosity rover's exploration site since 2012. Mount Sharp (Aeolis Mons) rises 5.5 km above the crater floor.",
      "lat": -5.4, "lon": 137.4, "src": ["NASA/JPL Curiosity mission"]}),
    (re.compile(r"\b(valles marineris|canyon)\b", re.I), "_fly_and_say",
     {"text": "<b>Valles Marineris</b> — 4,000 km canyon system up to 7 km deep. Tectonic origin, possible RSL.",
      "lat": -14.0, "lon": 301.0, "src": ["IAU Gazetteer", "MEGDR 4 ppd"]}),
]


def route_intent(text: str) -> dict:
    """Match the text to a tool call. Returns {tool, args, text}."""
    for pat, tool, default_args in INTENT_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        if tool == "_help":
            return {
                "tool": None,
                "text": ("I'm NAM's assistant. I can search Mars features, plan routes, analyze terrain, "
                         "find shelters and water, estimate radiation, and initialize a first-person "
                         "Walk View. Try: 'plan a route from Jezero to Nili Patera', "
                         "'find shelters near Olympus Mons', 'walk view at Gale crater'."),
            }
        if tool == "_fly_and_say":
            return {"tool": None, "text": default_args["text"],
                    "fly_to": {"lat": default_args["lat"], "lon": default_args["lon"]},
                    "src": default_args["src"]}
        # Try to extract lat/lon from the text
        args = dict(default_args)
        lat_m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°\s*)?[NS]\b", text, re.I)
        lon_m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°\s*)?[EW]\b", text, re.I)
        if lat_m and lon_m:
            args["lat"] = float(lat_m.group(1)) * (-1 if re.search(r"\bS\b", text, re.I) else 1)
            args["lon"] = float(lon_m.group(1)) * (-1 if re.search(r"\bW\b", text, re.I) else 1)
        # If tool needs lat/lon and we don't have them, try to resolve a place
        # name in the text (IAU features, mission sites, and well-known aliases).
        if "lat" not in args or "lon" not in args:
            lowered = text.lower()
            for cand in _location_candidates():
                if cand in lowered:
                    f = _find_feature(cand)
                    if f:
                        args["lat"] = f["lat"]
                        args["lon"] = f["lon"]
                        break
        if ("lat" not in args or "lon" not in args) and tool in (
            "find_water", "find_shelter", "assess_radiation", "enter_walk_view"
        ):
            return {"tool": None,
                    "text": ("I need a location for that. Try mentioning a feature like 'Jezero', "
                             "'Gale crater', or 'Olympus Mons', or give me a lat/lon like '18.4N, 77.7E'." )}
        # For generate_route we need a start and end
        if tool == "generate_route":
            # Look for "from X to Y" patterns
            m2 = re.search(r"from\s+(.+?)\s+to\s+(.+?)(?:$|[.,;])", text, re.I)
            if m2:
                start_name, end_name = m2.group(1).strip(), m2.group(2).strip()
                start_feat = _find_feature(start_name)
                end_feat = _find_feature(end_name)
                if start_feat and end_feat:
                    args["start_lat"] = start_feat["lat"]
                    args["start_lon"] = start_feat["lon"]
                    args["end_lat"] = end_feat["lat"]
                    args["end_lon"] = end_feat["lon"]
                    args["preset"] = "balanced"
                else:
                    return {"tool": None,
                            "text": f"Could not find both endpoints ('{start_name}' -> '{end_name}'). Try IAU feature names."}
            else:
                return {"tool": None,
                        "text": "To plan a route, tell me start and end like: 'plan a route from Jezero to Nili Patera'."}
        if tool == "plan_storm_response":
            # Extract event id from text (format event-XXXXXXXXXX)
            eid = re.search(r"event-([a-f0-9]{6,})", text, re.I)
            if eid:
                args["event_id"] = "event-" + eid.group(1)
            else:
                # No event id given — create one on the fly
                from .sim import create_event
                e = create_event(kind="sep", lat=args.get("lat", 18.4447),
                                lon=args.get("lon", 77.4508), severity="X-flare-class")
                args["event_id"] = e["id"]
                # Use the user's current position if they gave one
            if "lat" in args:
                args["current_lat"] = args.pop("lat")
                args["current_lon"] = args.pop("lon")
            else:
                args["current_lat"] = 18.4447  # default to Jezero
                args["current_lon"] = 77.4508
        return {"tool": tool, "args": args}
    return {
        "tool": None,
        "text": ("I didn't catch that. Try: 'find shelters near Olympus Mons', 'plan a route from "
                 "Jezero to Nili Patera', 'show radiation at Gale crater', or 'walk view at 18.4N 77.7E'."),
    }


def _location_candidates() -> list[str]:
    """All resolvable place-name strings for intent matching, longest first."""
    d = load_json_data()
    names = set()
    for f in d["FEATURES"]:
        names.add(f["name"].lower())
    for s in d["SITES"]:
        names.add(s["name"].lower())
    names.update([
        "jezero crater", "jezero", "gale crater", "gale", "mount sharp",
        "mt sharp", "aeolis mons", "perseverance", "curiosity", "nili patera",
    ])
    return sorted(names, key=len, reverse=True)


def _find_feature(name: str) -> dict | None:
    n = name.lower().strip()
    d = load_json_data()
    # Alias table for common mission-site names and colloquial targets
    aliases = {
        "jezero": ("Jezero crater", 18.4447, 77.4508),
        "jezero crater": ("Jezero crater", 18.4447, 77.4508),
        "gale": ("Gale crater", -5.4, 137.4),
        "gale crater": ("Gale crater", -5.4, 137.4),
        "mount sharp": ("Mount Sharp (Aeolis Mons)", -5.4, 137.4),
        "aeolis mons": ("Mount Sharp (Aeolis Mons)", -5.4, 137.4),
        "perseverance": ("Jezero crater (Perseverance)", 18.4447, 77.4508),
        "curiosity": ("Gale crater (Curiosity)", -5.4, 137.4),
        "nili patera": ("Nili Patera", 8.7, 68.1),
        "mt sharp": ("Mount Sharp (Aeolis Mons)", -5.4, 137.4),
    }
    if n in aliases:
        label, la, lo = aliases[n]
        return {"name": label, "lat": la, "lon": lo}
    for f in d["FEATURES"]:
        if n in f["name"].lower() or n in f["id"].lower():
            return {"name": f["name"], "lat": f["lat"], "lon": f["lon"]}
    for s in d["SITES"]:
        if n in s["name"].lower() or n in s["id"].lower():
            return {"name": s["name"], "lat": s["lat"], "lon": s["lon"]}
    return None


def chat_respond(user_text: str, mission_id: str | None = None) -> dict:
    """Process a user message and return a chat turn (no LLM)."""
    routed = route_intent(user_text)
    if routed.get("tool") is None:
        return {
            "text": routed["text"],
            "fly_to": routed.get("fly_to"),
            "sources": routed.get("src", []),
            "tool_calls": [],
        }
    tool = routed["tool"]
    args = routed["args"]
    if mission_id and "mission_id" not in args:
        args["mission_id"] = mission_id
    result = invoke_tool(tool, args)
    # Compose a natural-language summary of the result
    summary = _summarize(tool, args, result)
    return {
        "text": summary,
        "tool_calls": [{
            "tool": tool,
            "args": args,
            "result_summary": (str(result)[:500] + "...") if len(str(result)) > 500 else str(result),
        }],
        "result": result,
        "sources": _extract_sources(result),
    }


def _summarize(tool: str, args: dict, result: dict) -> str:
    if "error" in result:
        return f"⚠️ {result['error']}"
    if tool == "search_planetary_location":
        n = result.get("count", 0)
        names = [r["name"] for r in result.get("results", [])[:5]]
        return f"Found {n} matching features: {', '.join(names) if names else 'none'}."
    if tool == "find_shelter":
        n = result.get("count", 0)
        if n == 0:
            return "No shelter candidates within range. Try a wider search radius."
        top = result["shelters"][0]
        return (f"Found {n} shelter candidates. Nearest: <b>{top['name']}</b> "
                f"({top['kind']}, {top['distance_km']} km away, "
                f"sheltering index {top['scores']['sheltering_index']}).")
    if tool == "find_water":
        n = result.get("count", 0)
        if n == 0:
            return "No water-ice candidates within range."
        top = result["water_candidates"][0]
        return (f"Found {n} water-ice candidates. Best: certainty <b>{top['ice_certainty']}</b> "
                f"at {top['lat']:.2f}°, {top['lon']:.2f}° "
                f"(estimated depth to ice: {top['est_depth_to_ice_m']} m). "
                f"Distance from query: {top['distance_km']} km.")
    if tool == "assess_radiation":
        d = result.get("dose_mSv_per_day", 0)
        y = result.get("dose_mSv_per_year", 0)
        return (f"Radiation at this location: <b>{d} mSv/day</b> "
                f"(~{y} mSv/year). That's "
                f"{result.get('annual_career_limit_fraction_pct', 0):.1f}% of NASA's 1 Sv career limit per year.")
    if tool == "generate_route":
        if not result.get("ok"):
            return "Could not plan a route with that preset. Try a different preset or move endpoints off extreme terrain."
        s = result.get("stats") or {}
        return (f"Route planned ({result['preset']} preset): "
                f"<b>{s.get('length_km', 0):.1f} km</b>, "
                f"max slope {s.get('max_slope_deg', 0):.1f}°, "
                f"est. {s.get('est_sols', 0):.1f} sols at 100 m/sol EVA pace.")
    if tool == "simulate_storm":
        e = result.get("event", {})
        return (f"Simulated <b>{e.get('kind', 'dust')}</b> event created (id: {e.get('id')}). "
                f"Severity: {e.get('severity')}, duration {e.get('duration_sols')} sols. "
                f"Use plan_storm_response with this event_id for evacuation planning.")
    if tool == "enter_walk_view":
        w = result
        return (f"Walk View initialized at {w['lat']:.4f}, {w['lon']:.4f}. "
                f"Eye elevation: {w['eye_elev_m']} m (terrain {w['elev_m']} m + 1.7 m suit). "
                f"Local slope: {w.get('slope_deg', 'unknown')}°. "
                + (f"Nearby POV: {w['nearby_pov']['pov']['caption']}" if w.get("nearby_pov", {}).get("found") else "No pre-cached POV imagery nearby."))
    if tool == "plan_storm_response":
        return ("Storm-response plan ready. See the route_to_shelter and dose_estimate fields in the result. "
                "The recommended shelter has the highest composite sheltering index.")
    if tool == "analyze_terrain":
        cells = result.get("cells", [])
        if not cells:
            return "No terrain cells in the requested area."
        slopes = [c["slope_deg"] or 0 for c in cells]
        elevs = [c["elev_m"] for c in cells]
        return (f"Terrain grid {result['grid_shape']} over {result['extent']}. "
                f"Elevation range {min(elevs)}..{max(elevs)} m, "
                f"max slope {max(slopes):.1f}°.")
    if tool == "add_node":
        n = result.get("node", {})
        return f"Node '{n.get('name')}' (type {n.get('type')}) created at ({n.get('lat')}, {n.get('lon')}). ID: {n.get('id')}."
    if tool == "add_stop":
        return f"Stop added to mission {result.get('mission_id')} at ({result['stop']['lat']}, {result['stop']['lon']}). Reason: {result['stop'].get('reason', '—')}."
    if tool == "plan_area":
        scores = result.get("scores", {})
        score_str = "; ".join(f"{k}: {v:.2f}" for k, v in scores.items())
        return f"Area scored over {result['radius_km']} km. Objectives: {score_str}."
    return f"Tool <b>{tool}</b> executed. See the result field for details."


def _extract_sources(result: dict) -> list[str]:
    if isinstance(result, dict):
        prov = result.get("provenance", {})
        if isinstance(prov, dict):
            url = prov.get("url")
            if url:
                return [url]
            ref = prov.get("reference") or prov.get("catalogue") or prov.get("model")
            if ref:
                return [ref]
    return []
