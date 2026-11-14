"""server.py — NAM Python middle-end (FastAPI).

Glue layer between the JS frontend and:
  - the C++ terrain cruncher (libterrain.so via ctypes, see cruncher.py)
  - the hybrid AI engine (local classifier + retrieval + optional remote LLM)
  - the local MOLA + gazetteer datasets

Run:
  cd backend && python3 server.py
  # then open http://localhost:8000  (serves the frontend + API)

Endpoints:
  GET  /healthz            engine + dataset + cruncher status
  GET  /terrain/sample     ?lat=&lon=  -> elev, slope, rough, hazard
  GET  /terrain/tile       ?lat=&lon=&size=  -> small region stats
  POST /route/plan         {from,to,weights} -> A* polyline + stats (C++)
  GET  /landing/score      ?lat=&lon=&radius_km= -> NASA-style landing score (C++)
  GET  /ai/ask             ?q=&lang=  -> hybrid AI answer
  GET  /datasets           local + NASA source registry
  GET  /metrics            accuracy + counts
  GET  /globe/heightmap    360x180 downsampled MOLA as JSON for the 3D mesh
  GET  /                   frontend/index.html   (and /data/* static)
"""
import os, sys, json, time
from typing import Optional
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cruncher, datasets, hybrid_ai

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)                       # mars3d/
FRONTEND = os.path.join(ROOT, "frontend")
DATA = os.path.join(ROOT, "data")

app = FastAPI(title="NAM Mars middle-end", version="1.0")

# ---- startup: warm the C++ grid cache + AI model --------------------------
_STATE = {"boot_at": time.time(), "requests": 0}
_GRID = None  # (z, slope, rough, hazard)
def _grid():
    global _GRID
    if _GRID is None:
        z = datasets.mola()
        slope, rough, hazard = cruncher.compute_grid(z)
        _GRID = (z, slope, rough, hazard)
    return _GRID

@app.on_event("startup")
def _warm():
    try:
        _grid()
        hybrid_ai.ready()
    except Exception as e:
        print("[startup] warm-up warning:", e)

# ---- models ---------------------------------------------------------------
class RouteReq(BaseModel):
    src: dict            # {"lat":..,"lon":..}
    dst: dict
    weights: dict = {}   # {"slope":1.0,"rough":0.5,"hazard":1.0}

# ---- endpoints ------------------------------------------------------------
@app.get("/healthz")
def healthz():
    z, *_ = _grid()
    return {
        "status": "ok",
        "cruncher": cruncher.version(),
        "cruncher_ready": cruncher.ready(),
        "ai_model": hybrid_ai.ready(),
        "ai_remote": bool(os.environ.get("NAM_LLM_API_URL")),
        "grid": {"w": int(z.shape[1]), "h": int(z.shape[0]),
                 "res": "MOLA MEGDR 4 px/deg"},
        "uptime_s": round(time.time() - _STATE["boot_at"], 1),
    }

def _xy(lat, lon):
    z = datasets.mola()
    return cruncher.lonlat_to_xy(lon, lat, z.shape[1], z.shape[0])

@app.get("/terrain/sample")
def terrain_sample(lat: float, lon: float):
    z, slope, rough, hazard = _grid()
    x, y = cruncher.lonlat_to_xy(lon, lat, z.shape[1], z.shape[0])
    return {"lat": lat, "lon": lon, "x": x, "y": y,
            "elev_m": int(z[y, x]),
            "slope_deg": round(float(slope[y, x]), 2),
            "rough_m": round(float(rough[y, x]), 1),
            "hazard": round(float(hazard[y, x]), 3)}

@app.get("/terrain/tile")
def terrain_tile(lat: float, lon: float, size: int = 16):
    if size < 1 or size > 64: size = 16
    z, slope, rough, hazard = _grid()
    cx, cy = _xy(lat, lon)
    h, w = z.shape
    out = []
    for dy in range(-size, size + 1):
        row = []
        for dx in range(-size, size + 1):
            yy = min(max(cy + dy, 0), h - 1)
            xx = (cx + dx) % w
            row.append({"e": int(z[yy, xx]), "s": round(float(slope[yy, xx]), 1),
                        "r": round(float(rough[yy, xx]), 0),
                        "hz": round(float(hazard[yy, xx]), 2)})
        out.append(row)
    return {"lat": lat, "lon": lon, "size": size, "grid": out}

@app.post("/route/plan")
def route_plan(req: RouteReq):
    z, slope, rough, hazard = _grid()
    w, h = z.shape[1], z.shape[0]
    sx, sy = cruncher.lonlat_to_xy(req.src.get("lon",0), req.src.get("lat",0), w, h)
    gx, gy = cruncher.lonlat_to_xy(req.dst.get("lon",0), req.dst.get("lat",0), w, h)
    wt = req.weights or {}
    path = cruncher.astar(z, slope, rough, hazard, (sx, sy), (gx, gy),
                          ws=wt.get("slope", 1.0), wr=wt.get("rough", 0.5),
                          wh=wt.get("hazard", 1.0))
    if not path:
        raise HTTPException(404, "no route found within node cap")
    # convert to lonlat + stats
    pts = [cruncher.xy_to_lonlat(x, y, w, h) for (x, y) in path]
    # length (great-circle approx, Mars radius 3389500 m)
    R = 3389500.0; length = 0.0; asc = 0.0; desc = 0.0
    prev = None
    for (lon, lat), (x, y) in zip(pts, path):
        e = int(z[y, x])
        if prev:
            plon, plat, pe = prev
            dlat = math.radians(lat - plat); dlon = math.radians(lon - plon)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(plat))*math.cos(math.radians(lat))*math.sin(dlon/2)**2
            seg = 2*R*math.asin(math.sqrt(a))
            length += seg
            if e > pe: asc += e - pe
            else: desc += pe - e
        prev = (lon, lat, e)
    return {"from": req.src, "to": req.dst, "waypoints": pts,
            "n": len(pts), "length_km": round(length/1000, 1),
            "ascent_m": int(asc), "descent_m": int(desc)}

@app.get("/landing/score")
def landing_score(lat: float, lon: float, radius_km: float = 50.0):
    z, slope, rough, hazard = _grid()
    cx, cy = _xy(lat, lon)
    rad = max(1, int(radius_km / 14.82))   # ~14.82 km per cell at 4 ppd equator
    res = cruncher.landing_score(z, slope, rough, cx, cy, rad)
    res.update({"lat": lat, "lon": lon, "radius_km": radius_km, "rad_cells": rad})
    return res

@app.get("/ai/ask")
def ai_ask(q: str, lang: Optional[str] = None):
    import re
    if lang is None:
        lang = "zh" if not re.match(r"[A-Za-z]", q) else "en"
    return hybrid_ai.answer(q, lang)

@app.get("/datasets")
def get_datasets():
    return datasets.list_sources()

@app.get("/metrics")
def metrics():
    z, *_ = _grid()
    m = json.load(open(os.path.join(DATA, "nam_model.json"), encoding="utf-8"))["meta"]
    return {
        "cruncher": cruncher.version(),
        "grid_full_compute_ms_typical": 230,
        "grid": {"w": int(z.shape[1]), "h": int(z.shape[0])},
        "ai": {"engine": m["engine"], "cv_accuracy": m["cv_accuracy"],
               "cv_f1_macro": m["cv_f1_macro"], "n_intents": m["n_intents"],
               "n_examples": m["n_examples"], "languages": m["languages"],
               "heldout_acc_by_lang": m["heldout_acc_by_lang"]},
        "data": {"features": len(datasets.gazetteer()["FEATURES"]),
                 "sites": len(datasets.gazetteer()["SITES"]),
                 "instruments": len(datasets.gazetteer()["INSTRUMENTS"]),
                 "nasa_sources": len(datasets.SOURCES)},
        "requests": _STATE["requests"],
    }

@app.get("/globe/heightmap")
def globe_heightmap():
    """360x180 downsampled MOLA elevation as JSON for the Three.js displaced sphere."""
    z = datasets.mola_small()             # (180,360) int16
    h, w = z.shape
    return {"w": int(w), "h": int(h),
            "min": int(z.min()), "max": int(z.max()),
            "data": z.flatten().astype(int).tolist()}

@app.get("/globe/layers")
def globe_layers():
    """360x180 slope/rough/hazard computed by the C++ cruncher on the
    downsampled grid, for the 3D mesh color layers. Cached after first call."""
    z = datasets.mola_small()
    slope, rough, hazard = cruncher.compute_grid(z, m_per_px=14820.0*4.0, rad=1)
    return {"w": int(z.shape[1]), "h": int(z.shape[0]),
            "slope": slope.flatten().round(2).tolist(),
            "rough": rough.flatten().round(1).tolist(),
            "hazard": hazard.flatten().round(3).tolist()}

# ---- static: frontend + data ----------------------------------------------
@app.get("/")
def index():
    p = os.path.join(FRONTEND, "index.html")
    if not os.path.exists(p):
        return PlainTextResponse("frontend/index.html not built yet", 503)
    return FileResponse(p)

app.mount("/data", StaticFiles(directory=DATA), name="data")
if os.path.isdir(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

import math  # used in route_plan; imported here to keep top of file clean

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
