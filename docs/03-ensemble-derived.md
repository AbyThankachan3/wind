# 03-ensemble-derived.py

Validates every per-model derived GeoTIFF from stage 02, then combines them
across all models into the five final client layers per SSP.

## What it does

### 1. Discover + parse
- Globs `WindData/**/derived/{TARGET_YEAR}/*.tif` (excluding anything already
  under `_multimodel`).
- Parses `model/ssp/ensemble` from the path and a `metric` name from the
  filename (e.g. `mean_wind`, `threshold_12ms_days`).

### 2. Inspect (validate) every file
For each raster (`inspect()`), opens it with `rasterio` and records grid info
(shape, CRS, transform, bounds), value stats (min/max/mean, valid pixel %),
and raises **flags** for anything suspicious:
- `all_nodata` — no valid pixels at all
- `band_count != 1` — expected single-band input
- CRS not `EPSG:4326`
- nodata value set but not `NaN`
- negative values (physically implausible for wind speed)
- `count_out_of_range` — a count-type metric (threshold/valid) with an
  absurdly large max (>1e5)

All records go to `validation_report_{year}.csv` in the output dir regardless
of whether they raised flags, so you have a full audit trail. Flagged rows
are also printed to the console.

### 3. Combine
Groups the *readable* files by `(ssp, metric)` — only metrics listed in
`CLIENT_LAYER_NAMES` are combined (everything else is validated but ignored
for combination):

| Derived metric | Client layer |
|---|---|
| `mean_wind` | `baseline_wind_exposure` |
| `extreme_wind` | `peak_wind_exposure` |
| `p95_wind` | `severe_wind_exposure` |
| `threshold_12ms_days` | `strong_wind_frequency` |

For each group (`combine_group`):
1. Checks whether every file shares an identical grid (CRS, shape, affine
   transform within `GRID_TOL = 1e-6` degrees) via `grids_match`. NEX-GDDP-CMIP6
   is expected to share a common 0.25° grid, so this should normally be `True`;
   if not, everything is reprojected onto the first file's grid with a warning
   (bilinear for continuous metrics, nearest-neighbor for count metrics).
2. **Equal model weighting** (`EQUAL_MODEL_WEIGHT = True`): ensemble members
   of the *same* model are averaged first, then those per-model means are
   combined — so a model contributing 5 ensemble members doesn't get 5x the
   influence of a model contributing 1.
3. Stacks the per-model layers and computes, across the `member` dimension:
   - `mm_mean` — the multi-model mean (this becomes the actual output layer)
   - `mm_std` — multi-model standard deviation
   - `model_support` — count of models contributing at each pixel; pixels
     with fewer than `MIN_MODELS` (currently `1`) contributing are masked out
4. Writes the mean as `{client_metric}_{ssp}_mean_{year}.tif`.
5. **Confidence layer**: only for `metric == "p95_wind"` (`CONFIDENCE_METRIC`),
   also computes the coefficient of variation `cv = mm_std / mm_mean` (masked
   where `mm_mean <= CV_MIN_MEAN = 0.1` to avoid divide-by-near-zero blowups)
   and writes it as `severe_wind_exposure_{ssp}_confidence_{year}.tif`. Low CV
   = models agree; high CV = models disagree. This is the only place in the
   whole pipeline where model agreement is computed, since it requires all
   models loaded side by side.

### 4. Summarize
Writes `combination_summary_{year}.csv` recording, per (ssp, metric): file
count, model count, whether grids were aligned, whether equal weighting was
used, and output paths.

## Config

| Constant | Value | Meaning |
|---|---|---|
| `BASE_DIR` | `./WindData` | |
| `TARGET_YEAR` | `"2027"` | must match what 02 actually produced |
| `OUT_DIR` | `WindData/_multimodel/{year}` | |
| `EQUAL_MODEL_WEIGHT` | `True` | average within-model before across-model |
| `MIN_MODELS` | `1` | minimum contributing models to keep a pixel |
| `GRID_TOL` | `1e-6` degrees | tolerance for "same grid" |
| `CONFIDENCE_METRIC` | `"p95_wind"` | which metric's spread becomes `confidence` |
| `CV_MIN_MEAN` | `0.1` | floor to avoid divide-by-near-zero in CV |

## Output layout

```
WindData/_multimodel/{year}/
  validation_report_{year}.csv
  combination_summary_{year}.csv
  {ssp}/
    baseline_wind_exposure_{ssp}_mean_{year}.tif
    severe_wind_exposure_{ssp}_mean_{year}.tif
    severe_wind_exposure_{ssp}_confidence_{year}.tif
    peak_wind_exposure_{ssp}_mean_{year}.tif
    strong_wind_frequency_{ssp}_mean_{year}.tif
```

## Things to watch

- Per-group combination is itself wrapped in try/except in `main()` — a
  failure combining one (ssp, metric) group is recorded in the summary CSV
  with an `error` field rather than aborting the whole run.
- `is_count_metric` matches on filename **prefix** (`threshold`, `valid`) to
  decide nearest- vs bilinear-resampling — if a new metric is ever added whose
  name doesn't start with one of those prefixes but is still a count, it would
  silently get bilinear-resampled (fractional counts).
- Int-typed outputs (none currently written, since everything here is written
  as the default float32) would get `nodata=-9999` per the `write()` helper;
  currently every output layer is float32 with `NaN` nodata.
