"""cruncher.py — Python ctypes binding to the NAM C++ terrain shared library.

This is the "number cruncher" bridge: the Python middle-end calls these
functions for the heavy geospatial compute (slope/roughness/hazard over a full
MOLA grid, A* routing, landing-site scoring). Pure-Python equivalents would be
~50-100x slower; here the loop runs in compiled C++.

Loaded lazily so importing this module never hard-fails if the .so is absent
(the server reports it as offline and falls back to a numpy reference path).
"""
import ctypes, os, sys
import numpy as np
from numpy.ctypeslib import ndpointer

_HERE = os.path.dirname(os.path.abspath(__file__))

def _load():
    # Try every platform's naming so the same code works on Linux (.so),
    # macOS (.dylib) and Windows (terrain.dll / libterrain.dll).
    names = []
    if sys.platform == "win32":
        names += ["terrain.dll", "libterrain.dll"]
    elif sys.platform == "darwin":
        names += ["libterrain.dylib"]
    else:
        names += ["libterrain.so"]
    names += ["libterrain.so", "libterrain.dylib", "terrain.dll", "libterrain.dll"]
    seen = set()
    for name in names:
        if name in seen: continue
        seen.add(name)
        p = os.path.join(_HERE, name)
        if os.path.exists(p):
            try:
                return ctypes.CDLL(p)
            except OSError:
                return None
    return None

_lib = _load()
_ready = _lib is not None

if _ready:
    _lib.terrain_version.restype = ctypes.c_char_p
    _lib.terrain_compute.argtypes = [
        ndpointer(ctypes.c_int16, flags="C_CONTIGUOUS"), ctypes.c_int, ctypes.c_int,
        ctypes.c_double, ctypes.c_int,
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),  # slope
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),  # aspect
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),  # rough
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),  # hazard
    ]
    _lib.astar_path.argtypes = [
        ndpointer(ctypes.c_int16, flags="C_CONTIGUOUS"), ctypes.c_int, ctypes.c_int,
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),  # slope
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),  # rough
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),  # hazard
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,  # s/g x,y
        ctypes.c_double, ctypes.c_double, ctypes.c_double,       # ws, wr, wh
        ndpointer(ctypes.c_int, flags="C_CONTIGUOUS"), ctypes.c_int,  # out, max
    ]
    _lib.astar_path.restype = ctypes.c_int
    _lib.landing_score.argtypes = [
        ndpointer(ctypes.c_int16, flags="C_CONTIGUOUS"),
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),
        ndpointer(ctypes.c_float, flags="C_CONTIGUOUS"),
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
        ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int),
    ]
    _lib.landing_score.restype = ctypes.c_double

def version():
    return _lib.terrain_version().decode() if _ready else "unbuilt (numpy fallback)"

def ready():
    return _ready

# --- cached full-grid compute (slope/rough/hazard for the whole planet) ------
_CACHE = {}
def compute_grid(heights_int16, m_per_px=14820.0, rad=4):
    """Given a full MOLA int16 grid (h,w), return (slope,rough,hazard) float32
    grids of the same shape. Cached keyed by array id+shape."""
    key = (heights_int16.shape, m_per_px, rad)
    if key in _CACHE: return _CACHE[key]
    h, w = heights_int16.shape
    slope = np.zeros((h, w), np.float32)
    aspect = np.zeros((h, w), np.float32)
    rough = np.zeros((h, w), np.float32)
    hazard = np.zeros((h, w), np.float32)
    if _ready:
        _lib.terrain_compute(heights_int16, w, h, m_per_px, rad,
                             slope, aspect, rough, hazard)
    else:
        _numpy_fallback(heights_int16, slope, rough, hazard, m_per_px, rad)
    _CACHE[key] = (slope, rough, hazard)
    return slope, rough, hazard

def _box_mean(a, R):
    """Local mean over a (2R+1)x(2R+1) window: longitude wraps, latitude clamps
    at the edge. Integral-image implementation — O(N), no scipy."""
    h, w = a.shape
    aw = np.concatenate([a[:, -R:], a, a[:, :R]], axis=1)                 # wrap lon
    aw = np.vstack([np.repeat(aw[:1], R, 0), aw, np.repeat(aw[-1:], R, 0)])  # clamp lat
    c = np.cumsum(np.cumsum(aw.astype(np.float64), 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))                                       # leading zero row/col
    y = np.arange(h)[:, None]; x = np.arange(w)[None, :]
    s = c[y + 2*R + 1, x + 2*R + 1] - c[y, x + 2*R + 1] - c[y + 2*R + 1, x] + c[y, x]
    return s / float((2*R + 1) ** 2)

def _numpy_fallback(z, slope, rough, hazard, m_per_px, rad):
    """Pure-numpy reference path (used when libterrain is not compiled, e.g. on
    a machine without a C++ toolchain). Slower than C++ but correct and has no
    scipy/sklearn dependency."""
    h, w = z.shape
    zf = z.astype(np.float64)
    # Horn 3x3 finite-difference slope (longitude wraps, latitude edge-clamps)
    zl = np.roll(zf, 1, 1); zr = np.roll(zf, -1, 1)
    zu = np.vstack([zf[:1], zf[:-1]]); zd = np.vstack([zf[1:], zf[-1:]])
    zul = np.roll(zu, 1, 1); zur = np.roll(zu, -1, 1)
    zdl = np.roll(zd, 1, 1); zdr = np.roll(zd, -1, 1)
    dzdx = ((zul + 2*zl + zdl) - (zur + 2*zr + zdr)) / (8.0 * m_per_px)
    dzdy = ((zul + 2*zu + zur) - (zdl + 2*zd + zdr)) / (8.0 * m_per_px)
    slp = np.degrees(np.arctan(np.sqrt(dzdx*dzdx + dzdy*dzdy)))
    slope[:] = slp.astype(np.float32)
    # roughness = RMS residual after removing local mean (matches C++)
    mean = _box_mean(zf, rad)
    mean_sq = _box_mean(zf * zf, rad)
    var = np.maximum(mean_sq - mean * mean, 0.0)
    rough[:] = np.sqrt(var).astype(np.float32)
    sF = np.clip(slope / 30.0, 0, 1); rF = np.clip(rough / 400.0, 0, 1)
    hazard[:] = (0.6 * sF + 0.4 * rF).astype(np.float32)

def _astar_py(z, slope, rough, hazard, sx, sy, gx, gy, ws, wr, wh, max_nodes):
    """Pure-Python A* (heapq, 8-connected, longitude wraps). Slower than C++
    but correct; used when libterrain is not compiled."""
    import heapq, math
    h, w = z.shape
    def heur(x, y): return math.hypot(x - gx, y - gy)
    g = {(sx, sy): 0.0}
    came = {}
    pq = [(heur(sx, sy), (sx, sy))]
    closed = set()
    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    while pq:
        f, cur = heapq.heappop(pq)
        if cur in closed: continue
        if cur == (gx, gy): break
        closed.add(cur)
        if len(closed) > max_nodes: return []
        cx, cy = cur
        for dx, dy in dirs:
            nx = (cx + dx) % w
            ny = cy + dy
            if ny < 0 or ny >= h: continue
            nb = (nx, ny)
            if nb in closed: continue
            step = 1.0 if (dx == 0 or dy == 0) else 1.41421356
            s = float(slope[ny, nx]); r = float(rough[ny, nx]); hz = float(hazard[ny, nx])
            cost = step * (1.0 + (s*s/36.0)*ws + (r/300.0)*wr + hz*wh)
            tent = g[cur] + cost
            if nb not in g or tent < g[nb]:
                g[nb] = tent
                came[nb] = cur
                heapq.heappush(pq, (tent + heur(nx, ny), nb))
    if (gx, gy) not in came and (gx, gy) != (sx, sy):
        return []
    rev = []; c = (gx, gy)
    while c != (sx, sy):
        rev.append(c)
        nxt = came.get(c)
        if nxt is None: break
        c = nxt
    rev.append((sx, sy)); rev.reverse()
    return rev

def astar(heights, slope, rough, hazard, start, goal, ws=1.0, wr=1.0, wh=1.0, max_nodes=200000):
    """start/goal = (x,y) in grid coords. Returns list of (x,y) waypoints."""
    h, w = heights.shape
    if _ready:
        out = np.zeros(2*max_nodes, dtype=np.int32)
        n = _lib.astar_path(np.ascontiguousarray(heights, np.int16), w, h,
                            np.ascontiguousarray(slope, np.float32),
                            np.ascontiguousarray(rough, np.float32),
                            np.ascontiguousarray(hazard, np.float32),
                            start[0], start[1], goal[0], goal[1], ws, wr, wh,
                            out, max_nodes)
        return [(int(out[2*i]), int(out[2*i+1])) for i in range(n)]
    return _astar_py(heights, slope, rough, hazard,
                     start[0], start[1], goal[0], goal[1], ws, wr, wh, max_nodes)

def _landing_py(z, slope, rough, cx, cy, R):
    h, w = z.shape
    ys = np.arange(max(0, cy - R), min(h, cy + R + 1))
    xs = np.arange(-R, R + 1)
    n = 0; sm = 0.0; rm = 0.0; esum = 0.0; essum = 0.0
    for dy in ys - cy:
        for dx in xs:
            if dx*dx + dy*dy > R*R: continue
            nx = (cx + dx) % w
            i = (cy + dy) * w + nx
            sm += float(slope.flat[i]); rm += float(rough.flat[i])
            e = float(z.flat[i]); esum += e; essum += e*e; n += 1
    if n == 0: return {"score": 0.0, "slope_mean_deg": 0.0, "rough_rms_m": 0.0,
                       "elev_var_m2": 0.0, "n_cells": 0}
    sm /= n; rm /= n; emu = esum/n; evar = max(essum/n - emu*emu, 0.0)
    sP = 1.0 if sm < 2 else max(0.0, 1.0 - (sm - 2)/15.0)
    rP = 1.0 if rm < 50 else max(0.0, 1.0 - (rm - 50)/250.0)
    vP = 1.0 if evar < 1e4 else max(0.0, 1.0 - (evar - 1e4)/4e5)
    score = max(0.0, min(100.0, 100.0*(0.45*sP + 0.35*rP + 0.20*vP)))
    return {"score": round(score, 2), "slope_mean_deg": round(sm, 3),
            "rough_rms_m": round(rm, 2), "elev_var_m2": round(evar, 1), "n_cells": n}

def landing_score(z, slope, rough, cx, cy, rad):
    if _ready:
        s = ctypes.c_double(); r = ctypes.c_double(); v = ctypes.c_double(); n = ctypes.c_int()
        score = _lib.landing_score(np.ascontiguousarray(z, np.int16),
                                   np.ascontiguousarray(slope, np.float32),
                                   np.ascontiguousarray(rough, np.float32),
                                   z.shape[1], z.shape[0], cx, cy, rad,
                                   ctypes.byref(s), ctypes.byref(r), ctypes.byref(v), ctypes.byref(n))
        return {"score": round(score, 2), "slope_mean_deg": round(s.value, 3),
                "rough_rms_m": round(r.value, 2), "elev_var_m2": round(v.value, 1),
                "n_cells": n.value}
    return _landing_py(z, slope, rough, cx, cy, rad)

# ---- geo helpers -----------------------------------------------------------
def lonlat_to_xy(lon, lat, w, h):
    """lon 0..360 E, lat +90..-90 -> grid (x,y)."""
    x = int(round((lon % 360) / 360.0 * w)) % w
    y = int(round((90 - lat) / 180.0 * (h-1)))
    return x, max(0, min(h-1, y))

def xy_to_lonlat(x, y, w, h):
    lon = (x / w) * 360.0
    lat = 90 - (y / (h-1)) * 180.0
    return lon, lat
