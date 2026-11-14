"""Probe the C++ cruncher on real MOLA data: slope at Olympus flank vs plain,
Hellas basin hazard, A* route Gale->Jezero, and a landing score at Jezero."""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cruncher

DATA = "/home/z/my-project/download/mars3d/data"
z = np.load(os.path.join(DATA, "mola_elev.npy"))   # (720,1440) int16
h, w = z.shape
print("cruncher version:", cruncher.version(), "| grid", w, "x", h)

t0 = time.time()
slope, rough, hazard = cruncher.compute_grid(z)
print("full-grid compute: %.0f ms" % ((time.time()-t0)*1000))

def at(lon, lat):
    x, y = cruncher.lonlat_to_xy(lon, lat, w, h)
    return x, y

# 1) slope: Olympus Mons flank should be steep, Amazonis plain gentle
ox, oy = at(226.2, 18.4)   # Olympus flank
px, py = at(200.0, 25.0)   # Amazonis Planitia plain
print("Olympus Mons flank slope: %.1f deg, rough %.0f m, hazard %.2f" %
      (slope[oy,ox], rough[oy,ox], hazard[oy,ox]))
print("Amazonis plain slope:     %.1f deg, rough %.0f m, hazard %.2f" %
      (slope[py,px], rough[py,px], hazard[py,px]))
ok1 = slope[oy,ox] > slope[py,px]

# 2) Hellas basin hazard (deep, should be moderate; walls steep)
hx, hy = at(70.5, -42.4)
print("Hellas basin slope %.1f deg, rough %.0f m, hazard %.2f, elev %d m" %
      (slope[hy,hx], rough[hy,hx], hazard[hy,hx], z[hy,hx]))

# 3) A* route Gale crater -> Jezero crater (short, in same hemisphere)
gx, gy = at(137.4, -4.6)   # Gale
jx, jy = at(77.7, 18.4)    # Jezero
t0 = time.time()
path = cruncher.astar(z, slope, rough, hazard, (gx,gy), (jx,jy), ws=1.0, wr=0.5, wh=1.0, max_nodes=200000)
print("A* Gale->Jezero: %d waypoints in %.0f ms" % (len(path), (time.time()-t0)*1000))
ok3 = len(path) > 2
if path:
    sx_, sy_ = path[0]; ex_, ey_ = path[-1]
    print("  start (%d,%d) end (%d,%d)" % (sx_,sy_,ex_,ey_))

# 4) landing score at Jezero (Perseverance landing site -> should be decent)
ls = cruncher.landing_score(z, slope, rough, jx, jy, rad=8)
print("Jezero landing score:", ls)
ok4 = ls["score"] > 0

print("\nPROBE RESULT: slope_ok=%s  astar_ok=%s  landing_ok=%s" % (ok1, ok3, ok4))
print("ALL OK" if (ok1 and ok3 and ok4) else "FAIL")
