"""
validate_cogs.py — scan every final COG and check it is correct.

It looks under  <DATA_ROOT>/WindData/<country>/results/cog/<year>_<scenario>.tif
and, for each file, runs structural, metadata, data and physical checks:

  structure : opens cleanly, is a valid COG, 5 bands, EPSG:4326, float32
  metadata  : band descriptions and units match the 5 expected layers
  data      : has valid (non-NoData) pixels; no negative wind / frequency
  physics   : baseline <= severe <= peak at every pixel  (mean <= p95 <= max)
  ranges    : values within plausible bounds
  naming    : filename parses to a year + a known scenario

Each file gets PASS / WARN / FAIL. A per-file report is printed and written to
<root>/cog_validation_report.csv. The script exits non-zero if ANY file FAILs
(warnings do not fail the run).

Usage:
    python validate_cogs.py                 # uses WIND_DATA_ROOT / config
    python validate_cogs.py /mnt/disks/winddata/WindData   # explicit root
"""

import os
import sys
import csv
import glob

import numpy as np
import rasterio
from rio_cogeo.cogeo import cog_validate

import config

# The 5 bands step 04 writes, in order: (description, units).
EXPECTED_BANDS = [
    ("baseline_wind_exposure", "m s-1"),
    ("severe_wind_exposure",   "m s-1"),
    ("peak_wind_exposure",     "m s-1"),
    ("strong_wind_frequency",  "days"),
    ("confidence",             "ratio"),
]

CRS_OK = "EPSG:4326"
KNOWN_SCENARIOS = {"ssp245", "ssp585"}

# Plausible value bounds.
WIND_MAX = 60.0        # m/s — a daily-mean wind above this is implausible
FREQ_MAX = 366.0       # days per year
CONF_MAX = 3.0         # coefficient of variation; above this is suspicious
ORDER_TOL = 1e-3       # m/s tolerance for the baseline<=severe<=peak check


def _read_band(src, i):
    """Band i as a float array with NoData -> NaN."""
    return np.ma.filled(src.read(i, masked=True).astype("float64"), np.nan)


def check_file(path):
    """Return (status, flags, stats) for one COG. status in PASS/WARN/FAIL."""
    flags = []            # (level, message); level in "FAIL"/"WARN"
    stats = {}

    # ---- naming ----
    name = os.path.basename(path)
    stem = name[:-4] if name.lower().endswith(".tif") else name
    parts = stem.split("_")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1] in KNOWN_SCENARIOS:
        stats["year"], stats["scenario"] = parts[0], parts[1]
    else:
        flags.append(("WARN", f"filename not <year>_<scenario>: {name}"))
        stats["year"], stats["scenario"] = "", ""

    # ---- structure ----
    try:
        with rasterio.open(path) as src:
            stats["bands"] = src.count
            stats["crs"] = str(src.crs)
            stats["dtype"] = src.dtypes[0]
            stats["width"], stats["height"] = src.width, src.height

            if src.count != len(EXPECTED_BANDS):
                flags.append(("FAIL", f"band count {src.count} != {len(EXPECTED_BANDS)}"))
            if str(src.crs) != CRS_OK:
                flags.append(("FAIL", f"CRS {src.crs} != {CRS_OK}"))
            if src.dtypes[0] != "float32":
                flags.append(("WARN", f"dtype {src.dtypes[0]} != float32"))

            # ---- metadata: band descriptions + units ----
            for i, (exp_desc, exp_units) in enumerate(EXPECTED_BANDS, start=1):
                if i > src.count:
                    break
                desc = src.descriptions[i - 1]
                units = src.tags(i).get("units")
                if desc != exp_desc:
                    flags.append(("FAIL", f"band {i} desc '{desc}' != '{exp_desc}'"))
                if units != exp_units:
                    flags.append(("WARN", f"band {i} units '{units}' != '{exp_units}'"))

            # ---- data + ranges (only if band count is as expected) ----
            if src.count == len(EXPECTED_BANDS):
                bands = [_read_band(src, i) for i in range(1, src.count + 1)]
                baseline, severe, peak, freq, conf = bands

                total = baseline.size
                valid = np.isfinite(baseline)
                stats["valid_pixels"] = int(valid.sum())
                stats["valid_pct"] = round(100.0 * valid.sum() / total, 2) if total else 0

                if valid.sum() == 0:
                    flags.append(("FAIL", "all NoData (no valid pixels)"))
                else:
                    if valid.sum() < 4:
                        flags.append(("WARN", f"only {int(valid.sum())} valid pixel(s) "
                                              f"(sub-grid country)"))

                    # negatives (physically impossible)
                    for label, arr in [("baseline", baseline), ("severe", severe),
                                       ("peak", peak), ("frequency", freq)]:
                        amin = np.nanmin(arr) if np.isfinite(arr).any() else np.nan
                        if np.isfinite(amin) and amin < 0:
                            flags.append(("FAIL", f"{label} has negative values (min {amin:.3f})"))

                    # upper bounds
                    for label, arr, hi in [("baseline", baseline, WIND_MAX),
                                           ("severe", severe, WIND_MAX),
                                           ("peak", peak, WIND_MAX),
                                           ("frequency", freq, FREQ_MAX),
                                           ("confidence", conf, CONF_MAX)]:
                        amax = np.nanmax(arr) if np.isfinite(arr).any() else np.nan
                        if np.isfinite(amax) and amax > hi:
                            flags.append(("WARN", f"{label} max {amax:.2f} exceeds {hi}"))

                    # confidence should be non-negative (it's std/mean)
                    cmin = np.nanmin(conf) if np.isfinite(conf).any() else np.nan
                    if np.isfinite(cmin) and cmin < 0:
                        flags.append(("WARN", f"confidence has negative values (min {cmin:.3f})"))

                    # ---- physics: baseline <= severe <= peak, per pixel ----
                    m = np.isfinite(baseline) & np.isfinite(severe) & np.isfinite(peak)
                    if m.any():
                        v1 = (baseline[m] - severe[m])        # should be <= 0
                        v2 = (severe[m] - peak[m])            # should be <= 0
                        bad = int(((v1 > ORDER_TOL) | (v2 > ORDER_TOL)).sum())
                        worst = float(max(v1.max(), v2.max()))
                        stats["order_violations"] = bad
                        stats["order_worst"] = round(worst, 4)
                        if bad > 0:
                            flags.append(("FAIL", f"ordering mean<=p95<=max violated at "
                                                  f"{bad} px (worst +{worst:.3f} m/s)"))

                    stats["baseline_range"] = f"{np.nanmin(baseline):.2f}..{np.nanmax(baseline):.2f}"
                    stats["severe_range"]   = f"{np.nanmin(severe):.2f}..{np.nanmax(severe):.2f}"
                    stats["peak_range"]     = f"{np.nanmin(peak):.2f}..{np.nanmax(peak):.2f}"

        # ---- valid COG? (separate open) ----
        is_valid, errors, _warnings = cog_validate(path, quiet=True)
        if not is_valid:
            flags.append(("FAIL", "not a valid COG: " + "; ".join(errors[:2])))

    except Exception as e:
        flags.append(("FAIL", f"open/read error: {e}"))

    # ---- overall status ----
    if any(level == "FAIL" for level, _ in flags):
        status = "FAIL"
    elif any(level == "WARN" for level, _ in flags):
        status = "WARN"
    else:
        status = "PASS"
    return status, flags, stats


def discover(root):
    return sorted(glob.glob(os.path.join(root, "*", "results", "cog", "*.tif")))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(config.DATA_ROOT, "WindData")
    print("=" * 70)
    print(f"COG VALIDATION — scanning {root}")
    print("=" * 70)

    files = discover(root)
    if not files:
        print(f"No COGs found under {root}/*/results/cog/*.tif")
        sys.exit(1)
    print(f"Found {len(files)} COG file(s).\n")

    rows = []
    n_pass = n_warn = n_fail = 0
    for path in files:
        country = os.path.relpath(path, root).split(os.sep)[0]
        status, flags, stats = check_file(path)
        if status == "PASS":
            n_pass += 1
        elif status == "WARN":
            n_warn += 1
        else:
            n_fail += 1

        mark = {"PASS": "[ok]  ", "WARN": "[warn]", "FAIL": "[FAIL]"}[status]
        print(f"{mark} {country:10s} {os.path.basename(path):22s} "
              f"{stats.get('valid_pct', '?')}% valid")
        for level, msg in flags:
            print(f"         - {level}: {msg}")

        rows.append({
            "country": country,
            "file": os.path.basename(path),
            "status": status,
            "bands": stats.get("bands"),
            "crs": stats.get("crs"),
            "valid_pct": stats.get("valid_pct"),
            "baseline_range": stats.get("baseline_range"),
            "severe_range": stats.get("severe_range"),
            "peak_range": stats.get("peak_range"),
            "order_violations": stats.get("order_violations"),
            "flags": " | ".join(f"{l}:{m}" for l, m in flags),
        })

    out_csv = os.path.join(root, "cog_validation_report.csv")
    try:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        report_note = f"Report: {out_csv}"
    except Exception as e:
        report_note = f"(could not write CSV: {e})"

    print("\n" + "=" * 70)
    print(f"SUMMARY: {len(files)} files | {n_pass} PASS | {n_warn} WARN | {n_fail} FAIL")
    print(report_note)
    print("=" * 70)

    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
