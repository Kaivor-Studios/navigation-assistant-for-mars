"""FastAPI app entrypoint.

Mounts:
  - REST API under /api/v1/*
  - WebSocket at /ws/events and /ws/presence
  - Health at /health
  - OpenAPI docs at /docs (FastAPI default)
  - Reference UI at / (proves every endpoint works)
"""
from __future__ import annotations
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

from .api.routes import router as api_router
from .ws.handlers import ws_router
from .data import load_elevation, load_json_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the MOLA grid + JSON data so the first request is fast."""
    t0 = time.time()
    load_elevation()
    load_json_data()
    print(f"[NAM] MOLA grid + data loaded in {time.time() - t0:.2f}s")
    yield


app = FastAPI(
    title="NAM — Navigation Assistant of Mars (backend v2)",
    description=(
        "REST + WebSocket backend for NAM v2. Provides global Mars terrain, "
        "hazards, shelters, water-ice, radiation, route planning, "
        "Walk View data, simulated storms/presence, and a deterministic "
        "assistant with 24 typed tools. All scientific values carry provenance; "
        "all simulated values are labelled [SIM]."
    ),
    version="2.0.0-hack",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS — wide open for the hackathon so the separate UI dev server can call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Liveness + version + dependency status."""
    return {
        "status": "ok",
        "service": "nam-backend",
        "version": "2.0.0-hack",
        "data_loaded": True,
        "endpoints": [
            "GET  /docs                                — OpenAPI spec (interactive)",
            "GET  /api/v1/layers                       — layer registry",
            "GET  /api/v1/layers/{id}/tiles/{z}/{x}/{y} — cached tile proxy",
            "GET  /api/v1/gazetteer?q=                 — IAU feature search",
            "GET  /api/v1/missions/sites                — 13 mission sites",
            "GET  /api/v1/instruments                   — 13 instruments",
            "GET  /api/v1/targets                       — 16 spectral targets",
            "GET  /api/v1/elevation?lat=&lon=            — MOLA elevation + slope + roughness",
            "GET  /api/v1/elevation/profile?points=    — elevation profile along path",
            "GET  /api/v1/terrain/analyze?lat=&lon=&radius_km=",
            "GET  /api/v1/hazard?lat=&lon=              — composite hazard readout",
            "GET  /api/v1/shelters?lat=&lon=            — shelter candidates",
            "GET  /api/v1/water?lat=&lon=               — water-ice candidates",
            "GET  /api/v1/radiation?lat=&lon=  or  ?path=",
            "GET  /api/v1/env/storms                    — list storm events",
            "POST /api/v1/env/storms/simulate?kind=dust&severity=regional&lat=&lon=",
            "GET  /api/v1/presence?lat=&lon=            — nearby agents [SIM]",
            "POST /api/v1/route                          — A* planner",
            "GET  /api/v1/nodes  POST /api/v1/nodes  GET/PATCH/DELETE /api/v1/nodes/{id}",
            "GET  /api/v1/plans  POST /api/v1/plans  GET/DELETE /api/v1/plans/{id}",
            "POST /api/v1/plans/{id}/waypoints  POST /api/v1/plans/{id}/stops",
            "GET  /api/v1/walk/init?lat=&lon=&heading_deg=",
            "GET  /api/v1/walk/terrain?lat=&lon=&radius_m=",
            "GET  /api/v1/walk/pov?lat=&lon=  GET /api/v1/walk/povs",
            "GET  /api/v1/assistant/tools                — 24 typed tools",
            "POST /api/v1/assistant/tool/{name}          — direct tool invocation",
            "POST /api/v1/assistant/chat                 — SSE streaming chat",
            "WS   /ws/events                              — multiplexed event stream",
            "WS   /ws/presence                            — 1 Hz presence updates",
        ],
        "provenance": {
            "baseline": "NAM v1 (single-file HTML, 5.3 MB, delivered 2026-11-14)",
            "elevation_grid": "MOLA MEGDR 4 px/deg, 1440×720, embedded (NASA PDS)",
            "roughness_grid": "MOLA roughness 1 px/deg, 360×180 (NASA PDS)",
        },
    }


# Mount routers
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Marswalk v2 frontend (served from app/static/).

    Your UI guy replaces the files in app/static/ — the backend doesn't care.
    """
    index_path = Path(__file__).resolve().parent / "static" / "index.html"
    if not index_path.exists():
        return HTMLResponse(
            "<h1>NAM backend v2</h1>"
            "<p>Frontend not found in app/static/. API docs at <a href='/docs'>/docs</a>.</p>"
        )
    return HTMLResponse(index_path.read_text())


@app.get("/favicon.svg")
async def favicon():
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
        "<circle cx='16' cy='16' r='13' fill='#c1440e'/>"
        "<circle cx='16' cy='16' r='13' fill='none' stroke='#ff6a2b' stroke-width='1.5'/>"
        "<circle cx='20' cy='12' r='2.2' fill='#ffb02e'/></svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/{static_file}")
async def serve_static(static_file: str):
    """Serve frontend assets (app.js, styles.css, README.md, etc.)."""
    if static_file.startswith(("api", "ws", "docs", "openapi", "health", "redoc")):
        raise HTTPException(404, "not found")
    static_path = Path(__file__).resolve().parent / "static" / static_file
    if not static_path.exists() or not static_path.is_file():
        raise HTTPException(404, "not found")
    media = {
        ".html": "text/html", ".js": "application/javascript", ".css": "text/css",
        ".json": "application/json", ".md": "text/markdown", ".png": "image/png",
        ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".geojson": "application/geo+json",
    }
    ext = static_path.suffix.lower()
    return Response(content=static_path.read_bytes(),
                    media_type=media.get(ext, "application/octet-stream"))


@app.exception_handler(Exception)
async def global_exc_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": traceback.format_exc()[-2000:]},
    )
