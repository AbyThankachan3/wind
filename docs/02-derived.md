# 02-derived.py

Converts each raw per-model `sfcWind` NetCDF file into four clipped, yearly
GeoTIFF layers for the United States.

## What it does

For every `.nc` file found under `WindData/**/*{TARGET_YEAR}*.nc`:

1. Parses `model/ssp/ensemble` out of the path (relative to `BASE_DIR`,
   depth-robust — doesn't care how deep the file actually sits).
2. Loads the dataset with `xarray` (chunked by time, `chunks={"time": 30}`).
3. Detects the real temporal resolution from the time axis
   (`detect_time_unit`) — daily vs monthly vs some other step — so output
   filenames/labels say "days" only when the data is actually daily.
4. Fixes longitude from NASA's native 0–360 convention to -180..180, sorts
   lon ascending and lat descending (north-up, so GeoTIFFs render normally
   in any viewer).
5. Clips to a US state boundary shapefile (`GIS Files/State/cb_2018_us_state_500k.shp`),
   loaded once per worker process (not per file) via a `ProcessPoolExecutor`
   initializer — avoids re-reading/reprojecting the shapefile for every task.
6. Computes four derived layers over the `time` dimension:
   - **mean_wind** — annual mean
   - **extreme_wind** — annual max
   - **p95_wind** — 95th percentile (drops the stray `quantile` scalar coord
     that `xarray.DataArray.quantile()` attaches)
   - **threshold_{THRESHOLD}ms_{unit_plural}** — count of timesteps exceeding
     `THRESHOLD` (12 m/s), re-masked with `.where(spatial_mask)` so cells
     outside the clip boundary read as NoData rather than a misleading `0`
7. Writes each as a compressed, tiled float32 GeoTIFF with CRS/nodata/metadata
   tags via `export_raster`.

## Config

| Constant | Value | Meaning |
|---|---|---|
| `BASE_DIR` | `./WindData` | |
| `SHAPEFILE` | `./GIS Files/State/cb_2018_us_state_500k.shp` | US state boundaries |
| `TARGET_YEAR` | `"2027"` | glob filter — **not the same value as 01's `"2028"`**, see [overview](00-OVERVIEW.md) |
| `THRESHOLD` | `12` (m/s) | wind-speed cutoff for the exceedance-count layer |
| `CONUS_ONLY` | `False` | if `True`, drops AK/HI/PR/VI/GU/MP/AS to avoid antimeridian bbox issues from the Aleutians |
| `MAX_WORKERS` | `4` | process pool size, tuned for ~62 GB RAM |
| `CRS` | `EPSG:4326` | |

## Output layout

```
WindData/{model}/{ssp}/{ensemble}/derived/{year}/
  mean_wind_{year}.tif
  extreme_wind_{year}.tif
  p95_wind_{year}.tif
  threshold_{THRESHOLD}ms_{unit_plural}_{year}.tif
```

## Notable design points (per the file's own header comment)

This is a corrected version of an earlier script. Fixes called out explicitly:

- `if __name__ == "__main__":` guard added so multiprocessing works with
  Windows/macOS "spawn" as well as Linux "fork" — without this, `spawn`
  platforms would re-execute the whole module (including the discovery/dispatch
  code) in every worker.
- Shapefile loaded once per worker via a pool **initializer**, not relied on
  as an inherited global (which only works reliably under `fork`).
- Threshold-count re-masked so "zero exceedances" and "outside the US" are
  distinguishable (both would otherwise read as `0`).
- Time unit is detected rather than assumed, so labels don't lie if the
  source data isn't actually daily.
- CRS/spatial dims/nodata are re-asserted immediately before every write —
  guards against attributes getting silently dropped by intermediate xarray
  operations.

## Things to watch

- No per-file try/except around the shapefile-clip step specifically, but the
  whole body of `process_nc_file` is wrapped in try/except and reports
  `{"success": False, "error": ...}` rather than crashing the pool — one bad
  file doesn't kill the whole batch.
- `TARGET_YEAR` here (`2027`) does not match `01`'s (`2028`) — this script
  will find zero files to process against a fresh `01` run unless you edit
  one of the two constants. See the pipeline-wide note in
  [00-OVERVIEW.md](00-OVERVIEW.md).
