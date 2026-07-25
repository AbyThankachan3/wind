# 04-multiband-tiff-creation.py

Stacks the five combined ensemble layers from stage 03 into a single
multi-band GeoTIFF per SSP — the client-facing deliverable shape.

## What it does

1. `discover_ssps()` lists SSP subfolders under `WindData/_multimodel/{year}/`.
2. For each SSP (`stack_ssp`):
   - Resolves the 5 expected input paths from the `LAYERS` table below.
   - If any are missing, **skips that SSP** and prints which files were
     missing (doesn't raise).
   - Opens all 5 with `rasterio` and calls `check_alignment` — raises if any
     pair differs in `(width, height)`, `crs`, or `transform`
     (`Transform.almost_equals`). This is a hard fail, not a skip: a grid
     mismatch here means stage 03 produced inconsistent outputs, which is a
     real bug worth surfacing loudly.
   - Copies the first raster's profile, updates `count=5`, `dtype=float32`,
     LZW compression with float predictor, tiled, `nodata=NaN`.
   - Writes each band in the fixed order from `LAYERS`, tagging each with a
     `band_description` and a `units` tag (`m s-1`, `days`, or `ratio`), plus
     dataset-level tags (`year`, `ssp`, `source`, `bands`).

## Config

| Constant | Value | Meaning |
|---|---|---|
| `BASE_DIR` | `./WindData` | |
| `TARGET_YEAR` | `"2026"` | **doesn't match 02/03's `"2027"`** — see [overview](00-OVERVIEW.md) |
| `FLAT_NAMING` | `True` | output as `results/{year}_{ssp}.tif` instead of `results/{ssp}/{year}.tif` |

## Band order (fixed, always this order)

| # | Band | Source file | Units |
|---|---|---|---|
| 1 | `baseline_wind_exposure` | `baseline_wind_exposure_{ssp}_mean_{year}.tif` | m/s |
| 2 | `severe_wind_exposure` | `severe_wind_exposure_{ssp}_mean_{year}.tif` | m/s |
| 3 | `peak_wind_exposure` | `peak_wind_exposure_{ssp}_mean_{year}.tif` | m/s |
| 4 | `strong_wind_frequency` | `strong_wind_frequency_{ssp}_mean_{year}.tif` | days |
| 5 | `confidence` | `severe_wind_exposure_{ssp}_confidence_{year}.tif` | ratio |

## Output layout

With `FLAT_NAMING = True` (current setting):
```
WindData/results/{year}_{ssp}.tif    # 5 bands, float32, LZW
```
With `FLAT_NAMING = False` it would instead be `WindData/results/{ssp}/{year}.tif`.

## Things to watch

- `check_alignment` raising is a deliberate hard-stop: unlike stages 01–03,
  which log-and-continue on missing/bad data, a grid mismatch between the 5
  bands going into one file would silently misalign the client's map layers
  if allowed through, so this one is fail-loud by design.
- This is the third distinct `TARGET_YEAR` value across the pipeline
  (`"2026"`, vs `"2027"` in 02/03, vs `"2028"` in 01) — as-is this script will
  find nothing under `_multimodel/2026/` from a run of 01→03 with their
  current constants.
