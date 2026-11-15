# NAM v2 backend

Backend service for **NAM — Navigation Assistant of Mars**, the NASA Space Apps 2026 hackathon entry. This is the **data + planning + assistant layer** that a separate UI team builds against.

The companion single-file v1 app (`NAM.html`) is the reference implementation; this backend exposes the same data and tools over REST + WebSocket so any UI client can consume them.

## What it provides

- **Global Mars terrain**: 1440×720 MOLA MEGDR elevation grid (4 ppd, ~15 km at equator) + 360×180 MOLA roughness grid, embedded as binary data
- **Geospatial**: bilinear elevation sampling, regional slope, roughness, pressure estimate, composite hazard scoring
- **Layer registry + tile proxy**: 6 map layers (OpenPlanetaryMap live, embedded MOLA), with disk-cached tile proxy that degrades honestly (returns 503 + source link if upstream is unreachable)
- **Curated catalogs**: 102 IAU features, 13 mission sites, 8 orbiters, 16 literature-cited spectral targets, 13 instruments, 7-entry registry of documented-but-unavailable sources
- **Route planning**: A* over the MOLA grid with 3 presets (balanced / terrain / speed)
- **Environment simulation**: dust storms (local / regional / planet-encircling MY34 class), solar particle events (M-class / X-class anchored on RAD/Curiosity Sept 2017), presence (simulated crew + rovers + habitats)
- **Shelters**: 12 published candidates (lava-tube skylights, crater rims, canyon alcoves, overhangs) scored on 4 axes
- **Water-ice**: SWIM-derived proxy with certainty labels + estimated depth-to-ice
- **Radiation**: dose estimate anchored on RAD baseline (Hassler et al. 2014)
- **Walk View data feed**: first-person 3D view support — terrain mesh, eye height, nearest pre-cached rover POV imagery (7 entries at Jezero, Gale, Meridiani, Gusev, Elysium)
- **Deterministic assistant**: 24 typed tools (16 v1 + 8 new) wrapped in an OpenAI-compatible SSE chat shape, so a real LLM can replace this endpoint later without breaking the UI
- **WebSocket channels**: `/ws/events` (multiplexed: storm.alert, presence.update, plan.changed, telemetry.tick) and `/ws/presence` (1 Hz presence)

**Every scientific value carries a `provenance` block. Every simulated value is labelled `[SIM]`. All routes/doses/hazard scores are advisory only.**

## Quickstart

### Option A: Docker (recommended)

```bash
docker compose up
```

API at `http://localhost:8000`, OpenAPI docs at `http://localhost:8000/docs`, reference UI at `http://localhost:8000/`.

### Option B: Local Python

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Documentation

- **`API.md`** — full API contract, the single source of truth for the UI team
- **`/docs`** — interactive Swagger UI (auto-generated from the OpenAPI 3.1 spec)
- **`/redoc`** — alternative ReDoc UI
- **`/openapi.json`** — raw OpenAPI 3.1 spec
- **`/`** — reference HTML page that hits every endpoint (proof of life; UI team replaces this)

## Demo scenario

End-to-end test: a Jezero sol-1245 X-class SEP evacuation drill.

```bash
# start server first, then:
python3 scripts/demo_scenario.py
```

This will:
1. Initialize a Walk View at Jezero crater (18.4447°N, 77.4508°E)
2. Get baseline radiation at the site (no SEP)
3. Simulate an X-class solar particle event
4. Have the assistant plan a storm response via the chat endpoint
5. Print the full evacuation plan: nearest shelter, terrain-averse route, dose estimate

## Project layout

```
nam-backend/
├── app/
│   ├── main.py              # FastAPI entrypoint + health + reference UI mount
│   ├── api/
│   │   ├── routes.py        # REST + SSE routes (35+ endpoints)
│   │   └── models.py        # Pydantic request/response models
│   ├── core/
│   │   ├── geo.py           # MOLA sampling, slope, hazard scoring
│   │   ├── router.py        # A* route planner (3 presets)
│   │   ├── environment.py   # shelters, water, radiation
│   │   ├── walk.py          # Walk View data + POV library
│   │   ├── assistant.py     # 24 typed tools + intent router + chat responder
│   │   ├── state.py         # in-memory nodes + plans store
│   │   ├── sim.py           # storm/SEP/presence simulation
│   │   └── tiles.py         # cached tile proxy
│   ├── ws/
│   │   └── handlers.py      # WebSocket connection manager + event broadcast
│   └── data/
│       ├── __init__.py      # grid loaders + Mars constants
│       └── raw/
│           ├── elev.bin     # 4 MB int32 MOLA grid (1440×720)
│           ├── rough.bin   # 260 KB float32 MOLA roughness (360×180)
│           └── nam_data.json # 68 KB gazetteer + missions + instruments + layers
├── reference-ui/
│   └── index.html           # throwaway HTML proving every endpoint
├── scripts/
│   └── demo_scenario.py     # end-to-end demo
├── tests/
├── API.md
├── README.md  (this file)
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## What this is NOT (one-day hackathon scope)

- **No FastAPI production hardening**: in-memory state (resets on restart), single-team token auth only, no rate limiting, CORS wide open. Tighten before public deploy.
- **No local LLM**: the assistant is deterministic. The chat endpoint shape is OpenAI-compatible so a real LLM can drop in later — that's the post-hackathon v2 plan.
- **No real-time rover feeds**: presence is simulated; SWIM is a coarse proxy; Perseverance gallery links are pre-cached entries.
- **No HiRISE/CTX/CRISM/Mars Trek streaming**: documented in the layer registry as unavailable, with source links. The connector probes upstream at runtime and degrades to "honest 503" rather than fabricating content.

## Provenance

The MOLA MEGDR grid, roughness grid, gazetteer, mission sites, instruments, and layers were extracted directly from the NAM v1 single-file HTML application (`NAM.html`, ~5.3 MB) which is the project's delivered baseline.

Primary data sources cited in provenance blocks throughout the API:
- **MOLA MEGDR**: NASA PDS bundle `urn-nasa-pds-mgs_mola_topography_derived` — https://pds-geosciences.wustl.edu/missions/mgs/megdr.html
- **MOLA roughness**: NASA PDS
- **OpenPlanetaryMap**: https://openplanetarymap.org (live tile service, CORS-enabled)
- **USGS Geologic Map of Mars SIM 3292**: Tanaka et al. (2014) — https://pubs.usgs.gov/sim/3292/
- **SWIM (water-ice mapping)**: https://swim.psi.edu — Morgan et al. (2021), Nature Astronomy
- **RAD on Curiosity (radiation baseline)**: Hassler et al. (2014), Science 343, 1244797
- **SEP events**: Guo, J. et al. (2018), Space Weather 16, 977–988
- **Dust climatology**: Montabone et al. (2015), Icarus 251, 65–95
- **Lava-tube skylights**: Cushing, G.E. et al. (2007), Geophys. Res. Lett. 34, L17201

## License & credits

Built for the 2026 NASA Space Apps Challenge. Data sources retain their original NASA / USGS / PDS attributions.
