# NAM v2 — Marswalk (frontend + backend, integrated)

**Marswalk** is the NASA Space Apps 2026 "Interplanetary Survival Guide: Martian Map" entry: a Google-Earth-style Mars globe wired to the NAM planning backend. This repository contains BOTH halves, served by a single process.

## Run it

```bash
cd nam-backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Then open **http://localhost:8000** — the full Marswalk app:

- **Globe**: Viking MDIM 2.1 imagery (Mars Trek WMTS, ArcGIS fallback) draped over **real MOLA terrain** rendered from a custom heightmap terrain provider
- **Click anywhere**: the inspector panel fills with live MOLA elevation, slope, roughness, pressure, radiation dose, composite hazard score, nearest shelters + water-ice candidates, and the nearest rover POV image — every value with provenance
- **Traverse planner**: click waypoints, then "Plan walkable route (A*)" — the backend plans a terrain-aware route over the MOLA grid and draws it with length, max slope, and estimated sols
- **Search**: live IAU gazetteer suggestions (102 features) with fly-to
- **Walk View** (the differentiator): pick a point → "Enter Walk View" → first-person ground-level camera locked to terrain, drag to look, W/A/S/D to walk, helmet-style HUD, rover POV card when near a known site (Jezero, Gale, Meridiani, Gusev, Elysium)
- **NAM assistant**: SSE chat drawer — "Take me to Olympus Mons", "find shelters near Jezero", "show radiation at Gale crater", "plan a route from Jezero to Nili Patera" — with tool-activity chips and camera fly-to
- **Storms & presence** [SIM]: simulate dust storms (local/regional/MY34) and SEP events (X-class), draw affected polygons, and stream simulated crew/rover/habitat presence over WebSocket

## Two ways to run the frontend

1. **Served by the backend (default)** — files in `nam-backend/app/static/`, one process, no CORS issues.
2. **Separate dev server** — `cd frontend && python -m http.server 8080` (the JS auto-detects the API origin; set it manually in `app.js` if needed). CORS is open by default.

## Layout

```
nam-v2/
├── frontend/            # Marswalk UI source (CesiumJS + vanilla JS)
│   ├── index.html       # panels: inspector, route, assistant, storms, walk HUD
│   ├── app.js           # globe + NAM integration module (~1,850 lines)
│   └── styles.css
├── nam-backend/         # FastAPI service (see nam-backend/README.md + API.md)
│   ├── app/
│   │   ├── main.py      # serves frontend + API + WS
│   │   ├── api/routes.py    # 36 REST endpoints incl. /terrain/tile
│   │   ├── core/            # geo, router (A*), environment, walk, assistant, sim
│   │   ├── ws/handlers.py   # /ws/events + /ws/presence
│   │   ├── data/raw/        # MOLA grids + catalogs
│   │   └── static/          # deployed copy of frontend/
│   ├── scripts/demo_scenario.py
│   ├── tests/test_smoke.py
│   ├── API.md           # full API contract
│   └── requirements.txt, Dockerfile, docker-compose.yml
```

## Verification status

- 35/35 HTTP smoke tests (every endpoint)
- 15/15 pytest unit tests (MOLA spot-checks, A*, shelters, water, radiation, walk, assistant, sim)
- Browser-verified end-to-end (headless Chromium): globe render with MOLA terrain, click-inspection data, Walk View enter/walk/look/exit cycle, A* route draw, assistant SSE + fly-to, storm polygons, presence WebSocket
- MOLA spot-checks vs published values: Olympus +20.7 km, Jezero -2.65 km, Valles Marineris -5.1 km, Hellas -5.7 km (sampled) — all match

## Data sources

NASA PDS (MOLA MEGDR 4 ppd + roughness), OpenPlanetaryMap (live tiles), NASA/JPL Mars Trek (WMTS imagery), USGS Astrogeology (SIM 3292), SWIM (water-ice proxy), RAD/Curiosity (radiation baseline, Hassler et al. 2014), Cushing et al. 2007 (lava-tube skylights), Montabone et al. 2015 (dust climatology), Guo et al. 2018 (SEP). Full provenance blocks in every API response; all simulated values labelled [SIM].
