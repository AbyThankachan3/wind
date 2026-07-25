# 01-download-wind-data.py

Downloads raw `sfcWind` NetCDF files from NASA's NEX-GDDP-CMIP6 archive on the
[THREDDS data server](https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/).

## What it does

1. **Builds a manifest** CSV at `WindData/manifests/download_manifest_{TARGET_YEAR}.csv`
   (created once, appended to on every run) logging every attempt: timestamp,
   model, ssp, ensemble, filename, status, message, size in MB.
2. **Crawls the catalog** for each of 35 hardcoded CMIP6 models × 2 SSPs
   (`ssp245`, `ssp585`):
   - Checks the SSP folder exists (`ssp_exists`)
   - Lists ensemble-member folders by regex-matching `r\d+i\d+p\d+f\d+` out of
     `catalogRef` hrefs in the folder's `catalog.xml` (`find_ensemble_folders`)
   - Checks the `sfcWind` variable folder exists per ensemble (`variable_exists`)
   - Finds the specific `.nc` file matching `TARGET_YEAR` (`find_target_nc`)
   - Any missing step is logged to the manifest with a `missing_*` status and
     skipped — nothing raises.
3. **Downloads in parallel** (`ThreadPoolExecutor`, `MAX_WORKERS = 6`):
   - Streams to a `.part` temp file, then renames to the final name on success
     (atomic-ish; a half-downloaded file never masquerades as complete)
   - Skips files that already exist at the final path
   - Removes stale `.part` files before starting a fresh download
   - Prints a live progress line (percent, MB, speed)
   - On failure, logs `failed` with the exception message and deletes the
     partial file

## Config

| Constant | Value | Meaning |
|---|---|---|
| `BASE_URL` | NASA THREDDS catalog root | |
| `DOWNLOAD_ROOT` | `./WindData` | everything lands under here |
| `TARGET_YEAR` | `"2028"` | only files whose name contains this string are grabbed |
| `VARIABLE` | `"sfcWind"` | surface wind speed |
| `SSPS` | `["ssp245", "ssp585"]` | two emissions scenarios |
| `MODELS` | 35 CMIP6 models | hardcoded list |
| `MAX_WORKERS` | 6 | concurrent download threads |

## Output layout

```
WindData/
  manifests/download_manifest_2028.csv
  {model}/{ssp}/{ensemble}/raw/{filename}.nc
```

## Notable behaviors / things to know

- **Not resumable mid-file** — a `.part` file is deleted and restarted from
  zero on the next run, not resumed via HTTP range requests.
- **Silent network failures become manifest rows, not exceptions** — every
  catalog-check helper (`ssp_exists`, `variable_exists`, `find_target_nc`) has
  a bare `except: return False/None/[]`. This is intentional for a long
  unattended crawl (35 models × 2 SSPs × N ensembles) but means transient
  network blips look identical to "genuinely missing data" in the manifest.
- **Random 0.5–2.0s delay** before each download to avoid hammering the
  server.
- **Thread-safe manifest writes** via a single `Lock` shared by all workers.
- This script has no `if __name__ == "__main__":` guard — it runs top-level
  at import time. That's fine for a `python 01-download-wind-data.py` CLI
  invocation but means it can't be safely imported as a module.
