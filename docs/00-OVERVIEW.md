# Wind Pipeline Overview

Five-stage pipeline that turns NASA NEX-GDDP-CMIP6 `sfcWind` climate projections
into client-ready, web-servable wind-exposure raster layers for the US.

```
01-download-wind-data.py        Scrape THREDDS catalog, download raw .nc files
        |
        v  WindData/{model}/{ssp}/{ensemble}/raw/*.nc
02-derived.py                   Per-model, per-year stats -> 4 GeoTIFFs each
        |
        v  WindData/{model}/{ssp}/{ensemble}/derived/{year}/*.tif
03-ensemble-derived.py          Validate + combine across all models -> 5 client layers
        |
        v  WindData/_multimodel/{year}/{ssp}/*.tif
04-multiband-tiff-creation.py   Stack the 5 layers into one multi-band GeoTIFF per SSP
        |
        v  WindData/results/{year}_{ssp}.tif
05-cog.py                       Convert to Cloud-Optimized GeoTIFF (COG)
        |
        v  WindData/results/cog/{year}_{ssp}.tif   <- final deliverable
```

## Stages at a glance

| # | Script | Input | Output | Parallelism |
|---|--------|-------|--------|-------------|
| 01 | [01-download-wind-data.py](01-download-wind-data.md) | NASA THREDDS catalog (HTTP) | raw `.nc` files | `ThreadPoolExecutor` (I/O bound) |
| 02 | [02-derived.py](02-derived.md) | raw `.nc` | 4 GeoTIFFs/model (mean, max, p95, threshold count) | `ProcessPoolExecutor` (CPU/memory bound) |
| 03 | [03-ensemble-derived.py](03-ensemble-derived.md) | all models' derived GeoTIFFs | 5 combined client layers + validation/summary CSVs | single-process |
| 04 | [04-multiband-tiff-creation.py](04-multiband-tiff-creation.md) | 5 combined layers | 1 five-band GeoTIFF per SSP | single-process |
| 05 | [05-cog.py](05-cog.md) | multiband GeoTIFF | Cloud-Optimized GeoTIFF | single-process |

## The five final bands (in order)

1. `baseline_wind_exposure` — multi-model mean of annual mean wind (m/s)
2. `severe_wind_exposure` — multi-model mean of annual p95 wind (m/s)
3. `peak_wind_exposure` — multi-model mean of annual max wind (m/s)
4. `strong_wind_frequency` — multi-model mean of days/year over threshold (12 m/s)
5. `confidence` — coefficient of variation of p95 across models (low = models agree)

## ⚠️ Known inconsistency: TARGET_YEAR is hardcoded differently per script

Each script has its own `TARGET_YEAR` constant, and **they don't currently match**:

| Script | TARGET_YEAR |
|--------|-------------|
| 01-download-wind-data.py | `"2028"` |
| 02-derived.py | `"2027"` |
| 03-ensemble-derived.py | `"2027"` |
| 04-multiband-tiff-creation.py | `"2026"` |

As written today, a straight run of 01→05 would download 2028 data, then 02
would find nothing to process (it globs for `*2027*.nc`), and 04 would look
for 2026 combined layers that 03 never produced. This only works if you
manually edit the constant in each file before running that stage for a given
year. Worth centralizing (e.g. one config file or a CLI arg) if you plan to
run this repeatedly for multiple years.

## Other cross-cutting notes

- **Path convention**: every stage after 01 discovers files by walking
  `WindData/{model}/{ssp}/{ensemble}/...` and parses those path segments
  positionally (`rel_parts[0..2]`) rather than trusting filenames — robust to
  extra nesting but sensitive to reordering the folder structure.
- **CRS is fixed at `EPSG:4326`** everywhere (lat/lon degrees, NASA NEX-GDDP-CMIP6's native grid).
- **NoData is `NaN`** for all float32 outputs, `-9999` for any int-typed output (see 03).
- 02 and 03 split "single-model stats" from "cross-model agreement" deliberately:
  confidence (model spread) can't be computed until all models are loaded together, which only happens in 03.
