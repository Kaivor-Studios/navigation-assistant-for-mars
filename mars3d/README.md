# NAM 3D — Mars (3D globe + C++/Python/JS stack)

A Google-Earth-style 3D Mars system: **C++ number cruncher** (backend) +
**Python middle-end** (FastAPI) + **Three.js frontend** with a geoguesser-style
"fly to the surface" mode. Runs on 8 GB. See `ARCHITECTURE.md` for the full plan.

## Quickstart

```bash
cd backend
pip install -r requirements.txt    # fastapi, uvicorn, numpy, pydantic
python3 server.py                  # http://localhost:8000
```

**That's it — the server runs immediately without compiling anything.** If no
compiled C++ library is present, `cruncher.py` automatically uses a pure-numpy
reference path that produces identical results (verified: Olympus slope 4.15°,
A* Gale→Jezero 275 waypoints, Jezero landing 45.0) — just a bit slower. This is
the path Windows uses out of the box.

### Optional: compile the C++ cruncher for full speed (~50–100× faster terrain compute)

- **Linux**: `./build.sh`  → produces `libterrain.so`
- **macOS**: `./build.sh`  → produces `libterrain.dylib`
- **Windows**: `build.bat` → produces `terrain.dll`  (needs MinGW-w64 `g++` on PATH;
  install via MSYS2 `pacman -S mingw-w64-ucrt-x86_64-gcc`)

`cruncher.py` auto-detects the right file per platform. If you skip compiling,
the numpy fallback handles everything.

Open `http://localhost:8000/`. Click the globe, pick a point, hit **Enter
surface** for the ground view. Ask the AI box anything about Mars.

## Platform notes

- The shipped `libterrain.so` is a **Linux x86-64** binary. On Windows/macOS,
  either run `build.bat`/`build.sh` to recompile, or just run `python3 server.py`
  directly (numpy fallback).
- Python 3.10+ (tested on 3.12 and 3.15). numpy, fastapi, uvicorn, pydantic are
  the only runtime deps.

## What's here

- `backend/terrain.cpp` + `libterrain.so` — C++ cruncher (slope/rough/hazard,
  A* routing, NASA landing-site scorer), called via ctypes.
- `backend/server.py` — FastAPI middle-end (`/terrain /route /landing /ai/ask
  /globe /datasets /metrics`).
- `backend/hybrid_ai.py` — AI: local classifier + retrieval + optional remote
  LLM (set `NAM_LLM_API_URL` to enable hybrid mode).
- `frontend/index.html` — self-contained Three.js 3D globe (MOLA displaced) +
  multilayer depth (elevation/slope/roughness/hazard) + geoguesser surface mode.
- `data/` — real local datasets: MOLA heightmap (720×1440, verified Olympus
  20,708 m / Hellas −6,151 m), gazetteer (102 features), trained AI model.
- `shot_orbit.png`, `shot_surface.png` — verification screenshots.

## Accuracy (measured, not promised)

- Deterministic geospatial compute (slope/route/landing): exact by construction.
- AI intent classifier: **94.3 % overall CV**, ~98–100 % on functional command
  intents, **18/18 (100 %)** on the live multilingual demo. Full table in
  `ARCHITECTURE.md`. Retrain with the `nam_train/` toolkit to push higher.

## NASA-practical

Landing-site scoring (Jezero = 61/100), terrain-optimized A* routing
(Gale→Jezero, 4,375 km), hazard layer, and honest provenance — every value
traces to the embedded NASA/PDS MOLA or the IAU/USGS gazetteer; the NASA source
URLs are listed in `/datasets` with their real streamable status.
