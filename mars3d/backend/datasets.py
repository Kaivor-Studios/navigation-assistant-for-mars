"""datasets.py — loads the local MOLA heightmap + gazetteer, and exposes the
NASA/USGS source registry (the URLs the user supplied, documented honestly:
some have no CORS tile endpoint from a browser, so they are listed as
documented rather than streamed)."""
import os, json
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, "..", "data")

_MOLA = None; _MOLA_SMALL = None; _GAZ = None

def mola():
    global _MOLA
    if _MOLA is None:
        _MOLA = np.load(os.path.join(DATA, "mola_elev.npy"))   # (720,1440) int16, metres
    return _MOLA

def mola_small():
    """360x180 downsampled int16, for the 3D globe mesh (lightweight, 64k verts)."""
    global _MOLA_SMALL
    if _MOLA_SMALL is None:
        p = os.path.join(DATA, "mola_elev_360x180.npy")
        if os.path.exists(p):
            _MOLA_SMALL = np.load(p)
        else:
            _MOLA_SMALL = mola()[::4, ::4].astype(np.int16)
    return _MOLA_SMALL

def gazetteer():
    global _GAZ
    if _GAZ is None:
        _GAZ = json.load(open(os.path.join(DATA, "gazetteer.json"), encoding="utf-8"))
    return _GAZ

def planet():
    return gazetteer()["PLANET"]

# ---- NASA / USGS source registry (the user's supplied URLs) ---------------
# "streamable" = has a CORS-enabled tile/feature endpoint we can fetch from a
# browser or server here; "documented" = real public source but no verified
# CORS tile endpoint from this environment, so we link rather than fake it.
SOURCES = [
    {"id":"trek-mars","name":"NASA Trek — Mars","url":"https://trek.nasa.gov/mars/",
     "kind":"interactive map / WMTS","streamable":True,
     "note":"NASA-funded planetary map viewer; WMTS tile endpoints usable server-side."},
    {"id":"usgs-astro-mars","name":"USGS Astrogeology — Interactive Mars Maps",
     "url":"https://astrogeology-usgs.hub.arcgis.com/pages/interactive-maps-mars",
     "kind":"interactive map","streamable":False,
     "note":"ArcGIS Hub page; documented as a source, no verified CORS tile endpoint here."},
    {"id":"nasa-worldview","name":"NASA Worldview (Earth reference)",
     "url":"https://worldview.earthdata.nasa.gov/","kind":"interactive map",
     "streamable":True,"note":"Earth imagery — useful as a comparison/baseline, not Mars."},
    {"id":"mars2020-raw","name":"Mars 2020 / Perseverance Raw Images",
     "url":"https://mars.nasa.gov/mars2020/multimedia/raw-images/","kind":"image archive",
     "streamable":True,"note":"NASA/JPL public raw-image feed; fetchable for surface context."},
    {"id":"mola-megdr","name":"MOLA MEGDR 4 px/deg topography (embedded locally)",
     "url":"https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_3001/",
     "kind":"raster DEM","streamable":True,
     "note":"Embedded in this system as mola_elev.npy (720x1440 int16, metres). "
            "Source: NASA PDS, public domain. Derived: Smith et al. 2001, doi:10.1029/2000JE001364."},
    {"id":"iau-gazetteer","name":"IAU/USGS Gazetteer of Planetary Nomenclature",
     "url":"https://planetarynames.wr.usgs.gov/","kind":"feature catalog",
     "streamable":True,"note":"Embedded locally as gazetteer.json (102 features subset)."},
]

def list_sources():
    return {"sources":SOURCES,
            "local_files":sorted(os.listdir(DATA)) if os.path.isdir(DATA) else []}
