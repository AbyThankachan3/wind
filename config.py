"""
============================================================
WIND PIPELINE — CONFIGURATION
============================================================

Two ways to configure, in order of precedence:

  1) Environment variables (used by Docker / CI). If a WIND_* variable is set,
     it wins. This lets you change country / paths / years WITHOUT editing code.
  2) The defaults in the "EDIT THESE" section below (used for a plain local run).

All relative paths are resolved relative to THIS file, so it does not matter
which folder you launch from.

Environment variables (all optional):
  WIND_COUNTRY            e.g. Canada
  WIND_SHAPEFILE          absolute path to the .shp
  WIND_OUTPUT_ROOT        absolute path for all output
  WIND_YEARS             "2030,2040,2050,2060,2070,2080,2090,2100"
  WIND_SSPS              "ssp245,ssp585"
  WIND_THRESHOLD_MS       12
  WIND_DOWNLOAD_WORKERS   6
  WIND_PROCESS_WORKERS    4
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _resolve(path):
    """Absolute path, relative to this file if not already absolute."""
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(_HERE, path))


def _env(name, default):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _env_int(name, default):
    v = os.environ.get(name)
    return int(v) if v not in (None, "") else default


def _env_list_int(name, default):
    v = os.environ.get(name)
    if v in (None, ""):
        return default
    return [int(x) for x in v.replace(";", ",").split(",") if x.strip()]


def _env_list_str(name, default):
    v = os.environ.get(name)
    if v in (None, ""):
        return default
    return [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]


def _env_bool(name, default):
    v = os.environ.get(name)
    if v in (None, ""):
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


# ============================================================
# EDIT THESE  (defaults for a plain local run)
# ============================================================

# 1) Which country to process. FOR MOST RUNS THIS IS THE ONLY THING YOU SET.
#    The boundary shapefile is downloaded automatically (step 00) and its path
#    is derived from this name (see SHAPEFILE below) -- you do not type a path.
COUNTRY = _env("WIND_COUNTRY", "Canada")

# 2) Which future years to process.
YEARS = _env_list_int("WIND_YEARS", [2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100])

# 3) Which emissions scenarios to process.
SSPS = _env_list_str("WIND_SSPS", ["ssp245", "ssp585"])

# 4) Where to store EVERYTHING. Each country gets its own folder.
OUTPUT_ROOT = _resolve(_env(
    "WIND_OUTPUT_ROOT",
    os.path.join("WindData", COUNTRY),
))


# ============================================================
# BOUNDARY SHAPEFILE  (normally auto-derived -- you don't set this)
# ============================================================
#
# The filename each country's boundary shapefile ends up as, once step 00
# downloads and unzips it. This is what lets you set only COUNTRY: the path is
# looked up here, not typed by hand. The download source for each country lives
# in download_shapefile.py; the resulting filename lives here.
#
# Adding a country: register its download in download_shapefile.py, then add the
# resulting "<subfolder>/<file>.shp" here.
SHAPEFILE_BY_COUNTRY = {
    "Canada":    "Canada/lpr_000b21a_e.shp",
    "EU":        "EU/NUTS_RG_01M_2021_4326_LEVL_0.shp",
    "UK":        "UK/CTRY_DEC_2024_UK_BUC.shp",
    "Australia": "Australia/STE_2021_AUST_GDA2020.shp",
}

# Base folder the boundary shapefiles live in (override with WIND_GIS_DIR, e.g.
# "/data/gis" inside Docker).
GIS_DIR = _resolve(_env("WIND_GIS_DIR", os.path.join("..", "GIS Files")))

# Resolve the shapefile path: an explicit WIND_SHAPEFILE wins (for a custom or
# not-yet-registered country); otherwise it is derived from COUNTRY.
_shp_override = os.environ.get("WIND_SHAPEFILE")
_shp_rel = SHAPEFILE_BY_COUNTRY.get(COUNTRY)
if _shp_override:
    SHAPEFILE = _resolve(_shp_override)
elif _shp_rel:
    SHAPEFILE = os.path.join(GIS_DIR, *_shp_rel.split("/"))
else:
    # Unknown country and no override: leave empty so run_all / step 00 can
    # print a clear message instead of guessing a wrong path.
    SHAPEFILE = ""


# ============================================================
# ADVANCED (safe to leave as-is)
# ============================================================

THRESHOLD_MS = _env_int("WIND_THRESHOLD_MS", 12)
DOWNLOAD_WORKERS = _env_int("WIND_DOWNLOAD_WORKERS", 6)

# After a successful run, step 06 deletes the regenerable intermediate files
# (per-model derived layers, the _multimodel combine folder, and the pre-COG
# multiband results), keeping the raw .nc downloads, the shapefile, and the
# final COGs. Set WIND_KEEP_INTERMEDIATE=1 to keep everything instead.
KEEP_INTERMEDIATE = _env_bool("WIND_KEEP_INTERMEDIATE", False)

# Step-02 CPU workers. Each worker loads a full global dataset + the boundary
# shapefile, so it needs a lot of RAM (~5-8 GB peak). Size this to the machine:
#   16 GB RAM -> 1    (2 is marginal)
#   32 GB RAM -> 4
#   64 GB RAM -> 6
# The default is conservative so it does not run out of memory out of the box.
PROCESS_WORKERS = _env_int("WIND_PROCESS_WORKERS", 2)
CRS = "EPSG:4326"


# ============================================================
# Internal helpers
# ============================================================

def summary_lines():
    return [
        f"Country     : {COUNTRY}",
        f"Years       : {YEARS}",
        f"Scenarios   : {SSPS}",
        f"Threshold   : {THRESHOLD_MS} m/s",
        f"Shapefile   : {SHAPEFILE}",
        f"Output root : {OUTPUT_ROOT}",
    ]
