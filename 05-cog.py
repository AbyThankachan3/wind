"""
Step 05 — Convert the final multiband result GeoTIFFs into Cloud-Optimized
GeoTIFFs (COGs).

Input  : {OUTPUT_ROOT}/results/*.tif          (from step 04)
Output : {OUTPUT_ROOT}/results/cog/*.tif       (valid COGs, same names)

Reads all settings from config.py. Band descriptions, units tags, CRS and
NoData all carry through unchanged; only the internal layout and the added
overviews differ.
"""

import os
import glob

from rio_cogeo.cogeo import cog_translate, cog_validate
from rio_cogeo.profiles import cog_profiles

import config


# =========================================================
# CONFIG (from config.py)
# =========================================================

INPUT_DIR = os.path.join(config.OUTPUT_ROOT, "results")
COG_DIR = os.path.join(INPUT_DIR, "cog")
INPUT_GLOB = os.path.join(INPUT_DIR, "*.tif")

OVERVIEW_RESAMPLING = "average"
BLOCKSIZE = 512


# =========================================================
# HELPERS
# =========================================================

def build_profile():
    """LZW profile with the floating-point predictor (our data is float32)."""
    profile = cog_profiles.get("lzw")
    profile.update(predictor=3, blockxsize=BLOCKSIZE, blockysize=BLOCKSIZE)
    return profile


def make_cog(src_path, dst_path, profile):
    cog_translate(
        src_path, dst_path, profile,
        overview_resampling=OVERVIEW_RESAMPLING,
        web_optimized=False,        # keep native CRS; no reprojection
        forward_band_tags=True,     # carry per-band tags (units) into the COG
        in_memory=False,
        quiet=True,
    )


# =========================================================
# MAIN
# =========================================================

def main():
    os.makedirs(COG_DIR, exist_ok=True)

    sources = sorted(glob.glob(INPUT_GLOB))
    if not sources:
        print(f"No GeoTIFFs found in {INPUT_DIR}")
        return

    profile = build_profile()
    print(f"Converting {len(sources)} file(s) to COG...\n")

    ok, bad = 0, 0
    for src in sources:
        name = os.path.basename(src)
        dst = os.path.join(COG_DIR, name)
        print(f"-> {name}")

        try:
            make_cog(src, dst, profile)
        except Exception as e:
            print(f"   [error] conversion failed: {e}")
            bad += 1
            continue

        is_valid, errors, warnings = cog_validate(dst)
        print(f"   {'valid COG' if is_valid else 'NOT a valid COG'}  ->  {dst}")
        for w in warnings:
            print(f"   [warn] {w}")
        for e in errors:
            print(f"   [error] {e}")
        ok += is_valid
        bad += (not is_valid)

    print(f"\nDone. {ok} valid, {bad} failed. COGs in {COG_DIR}")


if __name__ == "__main__":
    main()
