# 05-cog.py

Final stage: converts the multi-band result GeoTIFFs from stage 04 into
Cloud-Optimized GeoTIFFs (COGs) — the actual format served to end users/tile
servers.

## What it does

1. Globs `WindData/results/*.tif` (top-level only — explicitly does **not**
   recurse into the `cog/` output subfolder, avoiding re-converting its own
   output).
2. For each file, calls `rio_cogeo.cog_translate` with an LZW + floating-point
   predictor profile, `average` overview resampling, no reprojection
   (`web_optimized=False`, keeps native `EPSG:4326`).
3. Validates the result with `cog_validate` and reports valid/invalid + any
   warnings/errors.
4. Prints a final tally: `N valid, M failed`.

Band descriptions, units tags, CRS, and NoData all carry through unchanged
from stage 04 — a COG is just a GeoTIFF with a specific internal tile +
overview-pyramid layout so HTTP range requests can fetch only the needed
region/zoom level, not a different dataset.

## Config

| Constant | Value | Meaning |
|---|---|---|
| `INPUT_DIR` | `./WindData/results` | |
| `COG_DIR` | `WindData/results/cog` | |
| `OVERVIEW_RESAMPLING` | `"average"` | good for continuous layers; use `"nearest"` if exact source values must survive downsampling (e.g. if a categorical layer were ever added) |
| `BLOCKSIZE` | `512` | standard COG internal tile size |

## Output layout

```
WindData/results/cog/{year}_{ssp}.tif
```

## Dependencies

Requires `rio-cogeo` (`pip install rio-cogeo`). The module docstring notes an
alternative if you don't want the extra dependency: GDAL's built-in COG driver
via `rasterio.shutil.copy(src, dst, driver="COG", COMPRESS="LZW",
PREDICTOR="FLOATING_POINT", OVERVIEW_RESAMPLING="AVERAGE", BLOCKSIZE=512)`.

## Things to watch

- Per-file try/except around `make_cog` — one failed conversion doesn't stop
  the batch; it's counted in `bad` and the loop continues.
- This is the last stage and has no `TARGET_YEAR` constant of its own — it
  just processes whatever it finds in `results/`, so it isn't affected by the
  cross-script `TARGET_YEAR` mismatch described in
  [00-OVERVIEW.md](00-OVERVIEW.md), it just depends on stage 04 having
  actually produced something first.
