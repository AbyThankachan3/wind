"""
Step 04 — Stack the five combined ensemble layers into one multi-band GeoTIFF
per SSP, for every year in config.YEARS.

Inputs come from step 03:
    {OUTPUT_ROOT}/_multimodel/{year}/{ssp}/
        baseline_wind_exposure_{ssp}_mean_{year}.tif
        severe_wind_exposure_{ssp}_mean_{year}.tif
        peak_wind_exposure_{ssp}_mean_{year}.tif
        strong_wind_frequency_{ssp}_mean_{year}.tif
        severe_wind_exposure_{ssp}_confidence_{year}.tif

Output (one per SSP per year):
    {OUTPUT_ROOT}/results/{year}_{ssp}.tif   (5 bands, float32, LZW)

Reads all settings from config.py.
"""

import os

import rasterio

import config


# =========================================================
# CONFIG (from config.py)
# =========================================================

BASE_DIR = config.OUTPUT_ROOT
YEARS = [str(y) for y in config.YEARS]
RESULTS_DIR = os.path.join(BASE_DIR, "results")

# True  -> flat  {results}/{year}_{ssp}.tif
# False -> nested {results}/{ssp}/{year}.tif
FLAT_NAMING = True

# Band order (band_description, source_filename_template, units).
LAYERS = [
    ("baseline_wind_exposure", "baseline_wind_exposure_{ssp}_mean_{year}.tif", "m s-1"),
    ("severe_wind_exposure",   "severe_wind_exposure_{ssp}_mean_{year}.tif",   "m s-1"),
    ("peak_wind_exposure",     "peak_wind_exposure_{ssp}_mean_{year}.tif",     "m s-1"),
    ("strong_wind_frequency",  "strong_wind_frequency_{ssp}_mean_{year}.tif",  "days"),
    ("confidence",             "severe_wind_exposure_{ssp}_confidence_{year}.tif", "ratio"),
]


# =========================================================
# HELPERS
# =========================================================

def discover_ssps(multimodel_dir):
    if not os.path.isdir(multimodel_dir):
        return []
    return sorted(
        d for d in os.listdir(multimodel_dir)
        if os.path.isdir(os.path.join(multimodel_dir, d))
    )


def check_alignment(srcs, ssp):
    ref = srcs[0]
    for s in srcs[1:]:
        if (s.width, s.height) != (ref.width, ref.height):
            raise ValueError(f"{ssp}: shape mismatch in {os.path.basename(s.name)}")
        if s.crs != ref.crs:
            raise ValueError(f"{ssp}: CRS mismatch in {os.path.basename(s.name)}")
        if not s.transform.almost_equals(ref.transform):
            raise ValueError(f"{ssp}: transform mismatch in {os.path.basename(s.name)}")


def output_path(ssp, year):
    if FLAT_NAMING:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        return os.path.join(RESULTS_DIR, f"{year}_{ssp}.tif")
    out_dir = os.path.join(RESULTS_DIR, ssp)
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{year}.tif")


# =========================================================
# STACK ONE SSP
# =========================================================

def stack_ssp(ssp, year, multimodel_dir):
    in_dir = os.path.join(multimodel_dir, ssp)
    src_paths = [
        os.path.join(in_dir, tmpl.format(ssp=ssp, year=year))
        for _, tmpl, _ in LAYERS
    ]

    missing = [p for p in src_paths if not os.path.exists(p)]
    if missing:
        print(f"[skip] {year}/{ssp}: {len(missing)} layer(s) missing:")
        for p in missing:
            print(f"         {os.path.basename(p)}")
        return None

    srcs = [rasterio.open(p) for p in src_paths]
    try:
        check_alignment(srcs, ssp)

        profile = srcs[0].profile.copy()
        profile.update(
            count=len(LAYERS), dtype="float32", compress="LZW",
            predictor=3, tiled=True, nodata=float("nan"),
        )

        out_path = output_path(ssp, year)
        with rasterio.open(out_path, "w", **profile) as dst:
            for i, (s, (band_name, _tmpl, units)) in enumerate(zip(srcs, LAYERS), start=1):
                dst.write(s.read(1).astype("float32"), i)
                dst.set_band_description(i, band_name)
                dst.update_tags(i, units=units)
            dst.update_tags(
                year=str(year), ssp=ssp, source="NASA NEX-GDDP-CMIP6",
                bands=",".join(n for n, _, _ in LAYERS),
            )

        print(f"[ok]  {year}/{ssp} -> {out_path}  ({len(LAYERS)} bands)")
        return out_path
    finally:
        for s in srcs:
            s.close()


# =========================================================
# MAIN
# =========================================================

def main():
    written = []
    for year in YEARS:
        multimodel_dir = os.path.join(BASE_DIR, "_multimodel", year)
        ssps = discover_ssps(multimodel_dir)
        if not ssps:
            print(f"[skip] no SSP folders under {multimodel_dir}")
            continue
        print(f"\n=== STACKING {year} === (SSPs: {', '.join(ssps)})")
        for ssp in ssps:
            path = stack_ssp(ssp, year, multimodel_dir)
            if path:
                written.append(path)

    print("\n=== DONE ===")
    print(f"Wrote {len(written)} file(s):")
    for p in written:
        print(f"  {p}")


if __name__ == "__main__":
    main()
