# NAM backend v2 — API contract

Base URL: `http://localhost:8000`

Interactive OpenAPI docs: `http://localhost:8000/docs` (Swagger UI) or `/redoc`.

All scientific values carry a `provenance` block (source, model, advisory text, source URL). All simulated values are labelled `[SIM]`. Coordinates: latitude in degrees (south negative), longitude in degrees EAST in 0..360 (negative longitudes are accepted and normalized).

This document is the single source of truth for the UI team. The backend enforces these contracts via Pydantic models + FastAPI's auto-generated OpenAPI 3.1 spec at `/openapi.json`.

## Health & docs

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, version, full endpoint list, provenance baseline |
| GET | `/docs` | Swagger UI (interactive) |
| GET | `/redoc` | ReDoc (alternative docs UI) |
| GET | `/openapi.json` | OpenAPI 3.1 spec |

## Layers (map tile proxy)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/layers` | Layer registry: 6 layers (OPM basemap, OPM color MOLA, OPM hillshade, OPM celestia_textures, generated MOLA color, generated MOLA hillshade) + 7-entry registry of unavailable sources |
| GET | `/api/v1/layers/{layer_id}/tiles/{z}/{x}/{y}` | Proxied tile (PNG). Cached to disk. Returns 503 with `source_url` if upstream is unreachable. Includes `X-NAM-Source` + `X-NAM-Credit` headers. |

## Static catalogs

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/gazetteer?q=&limit=` | Search 102 IAU features by name/id/type/tags |
| GET | `/api/v1/missions/sites` | 13 mission sites (landers + rovers) + 8 orbiters |
| GET | `/api/v1/instruments` | 13 instruments (HiRISE, CRISM, MOLA, MARCI, …) |
| GET | `/api/v1/targets` | 16 literature-cited spectral/science targets |

## Geospatial (MOLA-derived)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/elevation?lat=&lon=` | Bilinear elevation (m), slope (deg), roughness (m), pressure (mbar) |
| GET | `/api/v1/elevation/profile?points=lat1,lon1,lat2,lon2,...` | Per-point elevation/slope/rough/pressure along a path |
| GET | `/api/v1/terrain/analyze?lat=&lon=&radius_km=&resolution_deg=` | Local grid of elev/slope/hazard; defaults to ~1 km cells, clamped to MOLA's 0.25° resolution |
| GET | `/api/v1/hazard?lat=&lon=` | Composite hazard readout: class (low/moderate/high/extreme), score 0..100, notes, provenance |

### Example: elevation at Jezero crater

```bash
curl 'http://localhost:8000/api/v1/elevation?lat=18.4447&lon=77.4508'
```
```json
{
  "lat": 18.4447,
  "lon": 77.4508,
  "elev_m": -2651.0,
  "slope_deg": 2.4,
  "roughness_m": 4.2,
  "pressure_mbar": 5.3,
  "provenance": {
    "elevation": "MOLA MEGDR 4 px/deg (NASA PDS urn-nasa-pds-mgs_mola_topography_derived)",
    "slope": "Derived from MOLA MEGDR 4 ppd, ±0.25 deg neighbourhood (~30 km)",
    "url": "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html"
  }
}
```

## Environment (Part 3 in the v2 plan)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/shelters?lat=&lon=&max_radius_km=&limit=` | Shelter candidates (lava tubes / craters / canyon alcoves / overhangs), scored on 4 axes |
| GET | `/api/v1/water?lat=&lon=&max_radius_km=&limit=` | Water-ice candidates with SWIM-derived certainty + estimated depth |
| GET | `/api/v1/radiation?lat=&lon=` | Dose estimate (mSv/day, mSv/year) anchored on RAD/Curiosity |
| GET | `/api/v1/radiation?path=lat1,lon1,lat2,lon2,...` | Cumulative dose along a path |
| GET | `/api/v1/env/storms` | List all storm events (active + historical) |
| POST | `/api/v1/env/storms/simulate?kind=dust&severity=regional&lat=&lon=` | Generate a synthetic dust/SEP event. Returns event with polygon, intensity, operational impact. **All values labelled `[SIM]`.** |
| GET | `/api/v1/env/storms/{event_id}` | Fetch a single storm by id |
| GET | `/api/v1/presence?lat=&lon=&radius_km=` | Simulated agents (crew, rovers, habitats, caches) near a point. Without lat/lon, returns all. |

### Storm severities

| Kind | Severity | Behaviour |
|---|---|---|
| dust | local | tau ~2, ~5 sols, 3° radius |
| dust | regional | tau ~4.5, ~20 sols, 15° radius |
| dust | planet_encircling | tau ~8.5, ~90 sols, 90° radius — modelled on Mars Year 34 PEDE (2018) |
| sep | (any) | M-class SEP, 1 sol, 5 mSv surface dose |
| sep | X-flare-class | X-class SEP, 3 sols, 50 mSv surface dose — anchored on Sept 2017 RAD observation |

## Route planning (A*)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/route` | A* over MOLA 4 ppd grid. Body: `{start_lat, start_lon, end_lat, end_lon, preset}` |

Presets: `balanced` (default), `terrain` (terrain-averse), `speed` (distance-dominated).

Returns `{ok, preset, start, end, waypoints: [...], stats, path_cells, notes, provenance}`. If `ok: false`, the planner hit the step limit or encountered terrain too extreme to traverse (max slope > 30°). Try `speed` preset, or move endpoints off Olympus Mons / Valles Marineris walls.

### Example: plan a route from Jezero to Nili Patera region

```bash
curl -XPOST http://localhost:8000/api/v1/route \
  -H 'Content-Type: application/json' \
  -d '{"start_lat":18.4447,"start_lon":77.4508,"end_lat":24.0,"end_lon":80.0,"preset":"balanced"}'
```

## Nodes (user-created features)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/nodes?type=&bbox=lat_min,lon_min,lat_max,lon_max` | List nodes, optional filters |
| POST | `/api/v1/nodes` | Create a node. Body: `{name, type, lat, lon, radius_m, properties}` |
| GET | `/api/v1/nodes/{id}` | Get one |
| PATCH | `/api/v1/nodes/{id}` | Update fields (any subset) |
| DELETE | `/api/v1/nodes/{id}` | Delete |

Node types: `waypoint | cache | shelter | water | hazard | poi | person | area`.

## Plans (missions)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/plans` | List all missions |
| POST | `/api/v1/plans` | Create. Body: `{name, objective, kind}` |
| GET | `/api/v1/plans/{id}` | Get one (includes waypoints, stops, route, hazards) |
| DELETE | `/api/v1/plans/{id}` | Delete |
| POST | `/api/v1/plans/{id}/waypoints` | Add a waypoint. Body: `{lat, lon, name}` |
| POST | `/api/v1/plans/{id}/stops` | Add an ordered stop (AI-style). Body: `{lat, lon, reason, activity}` |

Mission kinds: `route | area | evacuation | survey`.

## Walk View (first-person 3D data feed)

This is the headline new feature's data layer. Your UI client uses these to render a first-person camera locked to MOLA terrain.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/walk/init?lat=&lon=&heading_deg=` | Returns eye elevation (terrain + 1.7 m suit), local slope/roughness, nearest pre-cached POV image |
| GET | `/api/v1/walk/terrain?lat=&lon=&radius_m=&resolution_m=` | Heightmap patch (default 1 km × 1 km box, 25 m cells → 41×41 grid) — use this to build the 3D mesh |
| GET | `/api/v1/walk/pov?lat=&lon=&max_radius_km=` | Nearest rover raw-image thumbnail (caption, mission, instrument, sol, credit, source URL) |
| GET | `/api/v1/walk/povs` | Full POV library (7 pre-cached entries at Jezero, Gale, Meridiani, Gusev, Elysium) |

### Walk View response shape

```json
{
  "lat": 18.4447,
  "lon": 77.4508,
  "elev_m": -2651.0,
  "eye_height_m": 1.7,
  "eye_elev_m": -2649.3,
  "heading_deg": 0.0,
  "pitch_deg": 0.0,
  "fov_deg": 75.0,
  "slope_deg": 2.4,
  "roughness_m": 4.2,
  "nearby_pov": {
    "found": true,
    "distance_km": 0.5,
    "pov": {
      "mission": "Perseverance",
      "instrument": "Navcam (left)",
      "lat": 18.4447, "lon": 77.4508,
      "sol": 100,
      "caption": "Perseverance Navcam view of Jezero crater floor — sol 100, looking across delta deposits.",
      "thumb_url": "https://mars.nasa.gov/...",
      "full_url": "https://mars.nasa.gov/raw_images/1073218/",
      "credit": "NASA/JPL-Caltech"
    }
  },
  "provenance": { ... }
}
```

## Assistant (chat)

The deterministic assistant wraps the 24 typed tools with an OpenAI-compatible SSE chat shape, so a real LLM can replace this endpoint without breaking the UI.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/assistant/tools` | List all 24 tools with their input/output schemas |
| POST | `/api/v1/assistant/tool/{tool_name}` | Direct tool invocation. Body: tool args (dict). |
| POST | `/api/v1/assistant/chat` | SSE streaming chat. Body: `{message, mission_id?}` |

### SSE event types (each line is `data: {json}\n\n`)

| type | fields | notes |
|---|---|---|
| `role` | `role: "assistant"` | sent first |
| `token` | `text` | chunked natural-language text (~5 words/chunk) |
| `fly_to` | `lat, lon` | UI hint: fly the camera here |
| `tool_call` | `tool, args` | the assistant invoked this tool with these args |
| `tool_result` | `tool, result_summary` | tool returned (truncated to 500 chars) |
| `result` | `result` | full tool result (may be large) |
| `sources` | `sources: [url, ...]` | provenance URLs cited in this answer |
| `done` | — | terminal event |

### Tool list (24)

**v1 (16)**: `search_planetary_location`, `get_current_map_context`, `search_nasa_datasets`, `get_location_observations`, `activate_map_layer`, `compare_geological_layers`, `get_elevation_profile`, `analyze_terrain`, `identify_hazards`, `find_scientific_targets`, `create_mission`, `generate_route`, `optimize_route`, `add_waypoint`, `explain_route`, `export_mission`

**new (8)**: `add_node`, `add_stop`, `plan_area`, `plan_storm_response`, `find_water`, `find_shelter`, `assess_radiation`, `simulate_storm`

**extra**: `enter_walk_view` (initializes a Walk View session via chat)

### Example: stream a chat

```bash
curl -N -XPOST http://localhost:8000/api/v1/assistant/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"find shelters near Olympus Mons"}'
```

## WebSocket events

Two multiplexed WebSocket channels. Both send JSON messages.

### `WS /ws/events`

Multiplexed event stream: `storm.alert`, `presence.update`, `plan.changed`, `telemetry.tick`. On connect, the server sends a `hello` event and then drives a 1 Hz `telemetry.tick` + a 5-secondly `presence.update`. Other parts of the backend (storm simulator, plan APIs) can publish events by calling `await publish_storm_alert(event)` from `app.ws.handlers`.

### `WS /ws/presence`

Dedicated 1 Hz presence stream. Each tick: `{"type": "presence.update", "agents": [...], "simulated": true, "timestamp": ...}`.

## Demo scenario (Jezero sol-1245 SEP drill)

The script `scripts/demo_scenario.py` runs the end-to-end scenario:

1. Simulate an X-class SEP event at Jezero
2. Plan a storm-response: fetch event → find shelters within 1000 km → plan terrain-averse route to nearest shelter → assess radiation dose along path
3. Print the full evacuation plan with provenance

```bash
python3 scripts/demo_scenario.py
```

## Error handling

- 400 — bad input (missing required params, malformed bbox/path)
- 404 — node/mission/event not found
- 503 — tile upstream unreachable (returns `source_url` in the body so the UI can fall back gracefully)

All errors return JSON: `{"detail": "..."}` or `{"error": "...", "traceback": "..."}` for 500s.

## CORS

Wide open by default (`*`). Tighten in `app/main.py` before deploying publicly.

## Notes for the UI team

- All latitudes south-negative; longitudes 0..360 (negative longitudes are accepted). CesiumJS uses 0..360 by default, so this matches.
- Every response that carries a scientific claim includes a `provenance` block. Render these in a "Sources" panel — it's the project's credibility anchor.
- All `[SIM]`-tagged values (storms, presence, dose estimates, derived shelter/water scores) are clearly labelled. Don't strip these labels in the UI.
- The `/health` endpoint returns a full list of available endpoints — useful for a dev console or "what can I call?" panel.
- The reference UI at `/` (root) is a quick way to verify the backend is alive; delete it once your UI is ready (or leave it as a debug tool).

## v2 additions (frontend-integrated build)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/terrain/tile/{z}/{x}/{y}?grid_size=33` | Heightmap tile for the globe's MOLA terrain provider (geographic quadtree, level 0 = 2×1 tiles, levels 0-8). Consumed by the Marswalk frontend to render real terrain. |

### Storm broadcast

`POST /api/v1/env/storms/simulate` now also broadcasts a `storm.alert` event to all `/ws/events` WebSocket subscribers, so any connected client (including other browsers) reacts to simulated events.

### Frontend served from the backend

The Marswalk frontend (index.html / app.js / styles.css) is served from `app/static/` at `/`. Run **one** process: `uvicorn app.main:app --port 8000` — frontend at `http://localhost:8000/`, API at `/api/v1/*`, docs at `/docs`. CORS stays open so the frontend can also be served separately during UI development.

### Frontend features wired to the backend

- Point inspection → `/elevation`, `/hazard`, `/radiation`, `/shelters`, `/water`, `/walk/pov` (all six fetched in parallel on every globe click)
- Traverse planner → `POST /route` (A*, 3 presets) with planned-path overlay + stats
- Search box → `/gazetteer` live suggestions (102 IAU features) with fly-to
- Walk View → `/walk/init` + `/walk/terrain` heightmap patch + `/walk/pov` rover imagery; first-person camera locked to terrain
- Assistant drawer → `/assistant/chat` SSE with tool chips + camera fly-to
- Storms panel → `/env/storms/simulate` with polygon overlay; presence via `/ws/presence` WebSocket (colour-coded agent markers)
- Globe → `/terrain/tile/{z}/{x}/{y}` custom Cesium terrain provider (real MOLA relief)
