"""
Step 03 — Verify the derived wind GeoTIFFs and combine them across models into
the final five client layers per SSP, for every year in config.YEARS:

  baseline_wind_exposure   (multi-model mean of mean_wind)
  peak_wind_exposure       (multi-model mean of extreme_wind)
  severe_wind_exposure     (multi-model mean of p95_wind)
  strong_wind_frequency    (multi-model mean of threshold_<T>ms_days)
  confidence               (model agreement on severe wind = std / mean of p95)

Reads all settings from config.py.

METHOD NOTES
  * Only like-with-like is combined: grouping key is (ssp, metric).
  * EQUAL_MODEL_WEIGHT: members of the same model are averaged first, then the
    per-model results are combined, so a model with many members doesn't
    dominate.
  * If every file in a group shares an identical grid the rasters are stacked
    with NO resampling; only an offset grid triggers reprojection, with a warning.
"""

import os
import glob

import numpy as np
import pandas as pd
import rasterio
import rioxarray
import xarray as xr
from rasterio.enums import Resampling

import config


# =========================================================
# CONFIG (from config.py)
# =========================================================

BASE_DIR = config.OUTPUT_ROOT
YEARS = [str(y) for y in config.YEARS]
CRS = config.CRS

EQUAL_MODEL_WEIGHT = True
MIN_MODELS = 1
GRID_TOL = 1e-6

COUNT_PREFIXES = ("threshold", "valid")
CONFIDENCE_METRIC = "p95_wind"
CV_MIN_MEAN = 0.1

# The threshold metric name written by step 02 (daily data -> "days").
THRESHOLD_METRIC = f"threshold_{config.THRESHOLD_MS}ms_days"

CLIENT_LAYER_NAMES = {
    "mean_wind": "baseline_wind_exposure",
    "extreme_wind": "peak_wind_exposure",
    "p95_wind": "severe_wind_exposure",
    THRESHOLD_METRIC: "strong_wind_frequency",
}


# =========================================================
# DISCOVERY + PARSING
# =========================================================

def discover(year):
    pattern = f"{BASE_DIR}/**/derived/{year}/*.tif"
    files = glob.glob(pattern, recursive=True)
    files = [f for f in files if "_multimodel" not in f]
    return sorted(files)


def parse(tif, year):
    """model/ssp/ensemble/derived/<year>/<file>.tif -> dict (depth-robust)."""
    rel_parts = os.path.relpath(tif, BASE_DIR).split(os.sep)
    model, ssp, ensemble = rel_parts[0], rel_parts[1], rel_parts[2]

    filename = os.path.basename(tif)
    suffix = f"_{year}.tif"
    metric = filename[:-len(suffix)] if filename.endswith(suffix) \
        else os.path.splitext(filename)[0]

    # Canonicalise the threshold metric so it matches CLIENT_LAYER_NAMES no
    # matter which time-unit word step 02 used (days / steps / months).
    if metric.startswith(f"threshold_{config.THRESHOLD_MS}ms"):
        metric = THRESHOLD_METRIC

    return {
        "path": tif, "model": model, "ssp": ssp, "ensemble": ensemble,
        "metric": metric, "filename": filename,
    }


def is_count_metric(metric):
    return metric.startswith(COUNT_PREFIXES)


# =========================================================
# PER-FILE INSPECTION
# =========================================================

def inspect(meta):
    rec = dict(meta)
    flags = []
    try:
        with rasterio.open(meta["path"]) as src:
            data = src.read(1, masked=True)
            arr = np.ma.filled(data.astype("float64"), np.nan)

            rec["band_count"] = src.count
            rec["width"] = src.width
            rec["height"] = src.height
            rec["shape"] = f"{src.height}x{src.width}"
            rec["crs"] = str(src.crs)
            rec["dtype"] = src.dtypes[0]
            rec["nodata"] = src.nodata
            rec["transform"] = tuple(round(v, 8) for v in src.transform[:6])
            b = src.bounds
            rec["left"], rec["bottom"] = b.left, b.bottom
            rec["right"], rec["top"] = b.right, b.top

            valid = np.isfinite(arr)
            rec["total_pixels"] = int(arr.size)
            rec["valid_pixels"] = int(valid.sum())
            rec["valid_percent"] = round(100.0 * valid.sum() / arr.size, 2)

            if valid.any():
                rec["min"] = float(np.nanmin(arr))
                rec["max"] = float(np.nanmax(arr))
                rec["mean"] = float(np.nanmean(arr))
            else:
                rec["min"] = rec["max"] = rec["mean"] = np.nan
                flags.append("all_nodata")

            if src.count != 1:
                flags.append(f"band_count={src.count}")
            if str(src.crs) != CRS:
                flags.append(f"crs={src.crs}")
            if src.nodata is not None and not np.isnan(src.nodata):
                flags.append(f"nodata={src.nodata}")
            if valid.any() and rec["min"] < 0:
                flags.append("negative_values")
            if is_count_metric(meta["metric"]) and valid.any() and rec["max"] > 1e5:
                flags.append("count_out_of_range")

        rec["readable"] = True
    except Exception as e:
        rec["readable"] = False
        flags.append(f"open_error:{e}")

    rec["flags"] = ";".join(flags)
    return rec


# =========================================================
# COMBINATION
# =========================================================

def grids_match(group_df):
    if group_df["crs"].nunique() != 1 or group_df["shape"].nunique() != 1:
        return False
    transforms = list(group_df["transform"])
    ref = np.array(transforms[0], dtype="float64")
    return all(np.allclose(ref, np.array(t, dtype="float64"), atol=GRID_TOL)
               for t in transforms)


def load_member(path, ref_da, resampling):
    da = rioxarray.open_rasterio(path, masked=True).squeeze("band", drop=True)
    if ref_da is not None:
        da = da.rio.reproject_match(ref_da, resampling=resampling)
    return da


def combine_group(group_df, metric, ssp, year, out_dir):
    aligned = grids_match(group_df)
    resampling = (Resampling.nearest if is_count_metric(metric)
                  else Resampling.bilinear)

    ref_path = group_df.iloc[0]["path"]
    ref_da = rioxarray.open_rasterio(ref_path, masked=True).squeeze("band", drop=True)

    if not aligned:
        print(f"  [warn] grids differ for {ssp}/{metric}; reprojecting onto "
              f"{os.path.basename(ref_path)} ({resampling.name}).")

    match_da = None if aligned else ref_da

    if EQUAL_MODEL_WEIGHT:
        members = []
        for model, model_df in group_df.groupby("model"):
            parts = [load_member(p, match_da, resampling) for p in model_df["path"]]
            stacked = xr.concat(parts, dim="m") if len(parts) > 1 else parts[0]
            model_mean = stacked.mean(dim="m", skipna=True) if len(parts) > 1 else stacked
            members.append(model_mean)
    else:
        members = [load_member(p, match_da, resampling) for p in group_df["path"]]
    n_models = group_df["model"].nunique()

    cube = xr.concat(members, dim="member")
    mm_mean = cube.mean(dim="member", skipna=True)
    mm_std = cube.std(dim="member", skipna=True, ddof=1)
    model_support = cube.notnull().sum(dim="member")

    keep = model_support >= MIN_MODELS
    mm_mean = mm_mean.where(keep)
    mm_std = mm_std.where(keep)

    out_sub = os.path.join(out_dir, ssp)
    os.makedirs(out_sub, exist_ok=True)

    def write(da, stat, dtype="float32"):
        client_metric = CLIENT_LAYER_NAMES[metric]
        path = os.path.join(out_sub, f"{client_metric}_{ssp}_{stat}_{year}.tif")
        da = da.astype(dtype).rio.write_crs(CRS)
        x_dim = "x" if "x" in da.dims else "lon"
        y_dim = "y" if "y" in da.dims else "lat"
        da = da.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim)
        nodata_value = np.nan if dtype == "float32" else -9999
        da = da.rio.write_nodata(nodata_value)
        da.encoding.clear()
        predictor = 3 if dtype == "float32" else 2
        da.rio.to_raster(path, compress="LZW", predictor=predictor, tiled=True)
        return path

    paths = {"mean": write(mm_mean, "mean")}

    if metric == CONFIDENCE_METRIC:
        cv = (mm_std / mm_mean).where(mm_mean > CV_MIN_MEAN)
        paths["confidence"] = write(cv, "confidence")

    return {
        "year": year, "ssp": ssp, "metric": metric,
        "n_files": len(group_df), "n_models": n_models,
        "grid_aligned": aligned, "equal_model_weight": EQUAL_MODEL_WEIGHT,
        **{f"out_{k}": v for k, v in paths.items()},
    }


# =========================================================
# PER-YEAR DRIVER
# =========================================================

def process_year(year):
    out_dir = os.path.join(BASE_DIR, "_multimodel", year)

    print(f"\n=== YEAR {year}: DISCOVERING TIFFs ===")
    files = discover(year)
    print(f"Found {len(files)} TIFF files.")
    if not files:
        print("Nothing to do for this year.")
        return []

    os.makedirs(out_dir, exist_ok=True)

    print("=== INSPECTING FILES ===")
    records = [inspect(parse(f, year)) for f in files]
    df = pd.DataFrame(records)

    val_csv = os.path.join(out_dir, f"validation_report_{year}.csv")
    df.to_csv(val_csv, index=False)
    print(f"Per-file validation written to {val_csv}")

    flagged = df[df["flags"].astype(bool) & (df["flags"] != "")]
    if len(flagged):
        print(f"[!] {len(flagged)} file(s) raised flags:")
        print(flagged[["model", "ssp", "metric", "valid_percent", "flags"]]
              .to_string(index=False))
    else:
        print("No per-file flags raised.")

    good = df[df["readable"]].copy()

    print("=== COMBINING (per ssp + metric) ===")
    summaries = []
    for (ssp, metric), group_df in good.groupby(["ssp", "metric"]):
        if metric not in CLIENT_LAYER_NAMES:
            continue
        spread = group_df["valid_percent"].max() - group_df["valid_percent"].min()
        note = " [check: valid% varies >5 across models]" if spread > 5 else ""
        print(f"- {ssp} / {metric}: {len(group_df)} files, "
              f"{group_df['model'].nunique()} models{note}")
        try:
            summaries.append(combine_group(group_df, metric, ssp, year, out_dir))
        except Exception as e:
            print(f"  [error] failed to combine {ssp}/{metric}: {e}")
            summaries.append({"year": year, "ssp": ssp, "metric": metric, "error": str(e)})

    summary_csv = os.path.join(out_dir, f"combination_summary_{year}.csv")
    pd.DataFrame(summaries).to_csv(summary_csv, index=False)
    print(f"Combined rasters in: {out_dir}")
    return summaries


# =========================================================
# MAIN
# =========================================================

def main():
    for year in YEARS:
        process_year(year)
    print("\n=== DONE (all years) ===")


if __name__ == "__main__":
    main()
