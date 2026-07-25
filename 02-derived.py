"""
Step 02 — Process raw sfcWind NetCDF files into clipped, derived GeoTIFF layers
for the configured country.

Produces four per-model yearly layers: mean, extreme (annual max), p95, and
threshold-exceedance count. The model-agreement "confidence" layer is NOT made
here -- it is derived downstream at the ensemble stage (step 03).

Reads all settings from config.py. Processes every year in config.YEARS; the
year for each file is taken from the file name.

Key design points (unchanged from the original corrected version):
  * Multiprocessing is guarded by `if __name__ == "__main__":` so it works on
    Windows / macOS (spawn) as well as Linux (fork).
  * The shapefile is loaded ONCE PER WORKER via a pool initializer.
  * The threshold-exceedance count is re-masked so cells outside the study area
    read as NoData, not 0.
  * Temporal frequency is detected from the time axis.
  * The stray `quantile` coordinate is dropped from the p95 layer.
  * Latitude is sorted north-up so the output GeoTIFFs render conventionally.
  * CRS, spatial dims and NoData are re-asserted right before every write.
"""

import os
import glob
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import geopandas as gpd
import xarray as xr
import rioxarray  # noqa: F401  (registers the .rio accessor)

import config


# =========================================================
# CONFIG (from config.py)
# =========================================================

BASE_DIR = config.OUTPUT_ROOT
SHAPEFILE = config.SHAPEFILE
YEARS = [str(y) for y in config.YEARS]
THRESHOLD = config.THRESHOLD_MS
CRS = config.CRS
MAX_WORKERS = config.PROCESS_WORKERS

# Set True to keep only the contiguous US (US shapefiles only). Harmless for
# other countries: it only acts if a "STUSPS" column is present.
CONUS_ONLY = False
NON_CONUS = {"AK", "HI", "PR", "VI", "GU", "MP", "AS"}


# =========================================================
# WORKER STATE  (one geodataframe loaded per worker process)
# =========================================================

_WORKER_GDF = None


def _init_worker(shapefile, conus_only):
    """Pool initializer: load and reproject the boundary shapefile once."""
    global _WORKER_GDF
    gdf = gpd.read_file(shapefile).to_crs(CRS)
    if conus_only and "STUSPS" in gdf.columns:
        gdf = gdf[~gdf["STUSPS"].isin(NON_CONUS)]
    _WORKER_GDF = gdf


# =========================================================
# HELPERS
# =========================================================

def year_from_name(path):
    """Return the config year that appears in this file name, or None."""
    name = os.path.basename(path)
    for y in YEARS:
        if y in name:
            return y
    return None


def detect_time_unit(time_values):
    """Infer temporal resolution from the time coordinate."""
    if len(time_values) < 2:
        return "step", "steps", float("nan")

    diffs_days = []
    for d in np.diff(time_values):
        if isinstance(d, np.timedelta64):
            diffs_days.append(d / np.timedelta64(1, "D"))
        else:  # cftime / datetime.timedelta-like
            diffs_days.append(d.days + getattr(d, "seconds", 0) / 86400.0)

    median_days = float(np.median(diffs_days))
    if median_days < 1.5:
        return "day", "days", median_days
    if 25 <= median_days <= 35:
        return "month", "months", median_days
    return "step", "steps", median_days


def export_raster(da, path, layer_name, model, ssp, ensemble, year, threshold=None):
    """Re-assert CRS, spatial dims and NoData, then write a GeoTIFF."""
    da = da.astype("float32")
    da = da.rio.write_crs(CRS)
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    da = da.rio.write_nodata(np.float32(np.nan))
    da.attrs.update({
        "layer_name": layer_name,
        "model": model,
        "ssp": ssp,
        "ensemble": ensemble,
        "year": str(year),
        "variable": "sfcWind",
        "units": "m s-1",
        "crs": CRS,
        "source": "NASA NEX-GDDP-CMIP6",
        "processing": "Derived yearly climate raster",
        "threshold_mps": str(threshold) if threshold is not None else "N/A",
    })
    da.encoding.clear()
    da.rio.to_raster(path, compress="LZW", tiled=True, dtype="float32")


# =========================================================
# PROCESSING FUNCTION
# =========================================================

def process_nc_file(nc_file):
    try:
        print("\n================================================")
        print(f"PROCESSING:\n{nc_file}")
        print("================================================")

        year = year_from_name(nc_file)
        if year is None:
            raise ValueError(f"No configured year found in filename: {nc_file}")

        # ---- Path components (relative to BASE_DIR, depth-robust) --------
        rel_parts = os.path.relpath(nc_file, BASE_DIR).split(os.sep)
        if len(rel_parts) < 4:
            raise ValueError(
                f"Unexpected path layout, expected "
                f"model/ssp/ensemble/.../file.nc but got: {rel_parts}"
            )
        model, ssp, ensemble = rel_parts[0], rel_parts[1], rel_parts[2]

        print(f"\nYear: {year}\nModel: {model}\nSSP: {ssp}\nEnsemble: {ensemble}")

        output_dir = os.path.join(BASE_DIR, model, ssp, ensemble, "derived", year)
        os.makedirs(output_dir, exist_ok=True)

        # ---- Load dataset -------------------------------------------------
        print("Loading dataset...")
        ds = xr.open_dataset(nc_file, chunks={"time": 30})
        wind = ds["sfcWind"]

        # ---- Detect temporal resolution -----------------------------------
        unit, unit_plural, median_days = detect_time_unit(wind["time"].values)
        n_steps = wind.sizes["time"]
        print(f"Time axis: {n_steps} steps, median spacing "
              f"{median_days:.2f} days -> treating as '{unit}'")

        # ---- Fix longitude 0-360 -> -180..180, order axes -----------------
        print("Fixing longitude / ordering axes...")
        wind = wind.assign_coords(lon=((wind.lon + 180) % 360) - 180)
        wind = wind.sortby("lon")
        wind = wind.sortby("lat", ascending=False)

        # ---- CRS + spatial dims ------------------------------------------
        wind = wind.rio.write_crs(CRS)
        wind = wind.rio.set_spatial_dims(x_dim="lon", y_dim="lat")

        # ---- Clip to boundary --------------------------------------------
        print("Clipping raster...")
        clipped = wind.rio.clip(_WORKER_GDF.geometry, _WORKER_GDF.crs, drop=True)
        print(f"Clipped shape: {clipped.shape}")

        spatial_mask = clipped.notnull().any(dim="time")

        # ---- Derived layers ----------------------------------------------
        print("Generating yearly layers...")
        mean_wind = clipped.mean(dim="time", skipna=True)
        max_wind = clipped.max(dim="time", skipna=True)

        p95_wind = clipped.quantile(0.95, dim="time", skipna=True)
        p95_wind = p95_wind.drop_vars("quantile", errors="ignore")

        threshold_count = (clipped > THRESHOLD).sum(dim="time").where(spatial_mask)

        # ---- Export GeoTIFFs ---------------------------------------------
        print("Exporting GeoTIFFs...")
        mean_path = os.path.join(output_dir, f"mean_wind_{year}.tif")
        max_path = os.path.join(output_dir, f"extreme_wind_{year}.tif")
        p95_path = os.path.join(output_dir, f"p95_wind_{year}.tif")
        threshold_path = os.path.join(
            output_dir, f"threshold_{THRESHOLD}ms_{unit_plural}_{year}.tif"
        )

        export_raster(mean_wind, mean_path, "mean_wind", model, ssp, ensemble, year)
        export_raster(max_wind, max_path, "extreme_wind", model, ssp, ensemble, year)
        export_raster(p95_wind, p95_path, "p95_wind", model, ssp, ensemble, year)
        export_raster(threshold_count, threshold_path, "threshold_exceedance",
                      model, ssp, ensemble, year, threshold=THRESHOLD)

        stats = {
            "model": model, "ssp": ssp, "ensemble": ensemble, "year": year,
            "time_unit": unit, "n_steps": int(n_steps),
            "mean_min": float(mean_wind.min().values),
            "mean_max": float(mean_wind.max().values),
            "max_min": float(max_wind.min().values),
            "max_max": float(max_wind.max().values),
        }

        ds.close()
        del wind, clipped, spatial_mask
        del mean_wind, max_wind, p95_wind, threshold_count

        print(f"\nCOMPLETED: {model} | {ssp} | {year}")
        return {"success": True, "file": nc_file, "stats": stats}

    except Exception as e:
        traceback.print_exc()
        return {"success": False, "file": nc_file, "error": str(e)}


# =========================================================
# MAIN
# =========================================================

def discover_nc_files():
    files = set()
    for year in YEARS:
        files.update(glob.glob(f"{BASE_DIR}/**/raw/*{year}*.nc", recursive=True))
    return sorted(files)


def main():
    print("\n======================================")
    print("DISCOVERING NC FILES")
    print(f"Years: {YEARS}")
    print("======================================")

    nc_files = discover_nc_files()
    print(f"\nFound {len(nc_files)} files.")
    if not nc_files:
        print("No files to process. Exiting.")
        return

    print("\n================================================")
    print("STARTING PARALLEL PROCESSING")
    print(f"Workers: {MAX_WORKERS}")
    print("================================================")

    results = []
    with ProcessPoolExecutor(
        max_workers=MAX_WORKERS,
        initializer=_init_worker,
        initargs=(SHAPEFILE, CONUS_ONLY),
    ) as executor:
        futures = [executor.submit(process_nc_file, f) for f in nc_files]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result["success"]:
                s = result["stats"]
                print("\n--- SUCCESS ---")
                print(f"{s['model']} | {s['ssp']} | {s['year']} | "
                      f"{s['time_unit']} ({s['n_steps']} steps)")
                print(f"Mean {s['mean_min']:.2f}->{s['mean_max']:.2f}  "
                      f"Extreme {s['max_min']:.2f}->{s['max_max']:.2f}")
            else:
                print("\n--- FAILED ---")
                print(f"File: {result['file']}")
                print(f"Error: {result['error']}")

    success = sum(1 for r in results if r["success"])
    print("\n================================================")
    print("FINAL SUMMARY")
    print("================================================")
    print(f"Total: {len(results)}  Successful: {success}  Failed: {len(results) - success}")


if __name__ == "__main__":
    main()
