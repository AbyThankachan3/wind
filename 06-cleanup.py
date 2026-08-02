"""
Step 06 — Remove regenerable intermediate files after a successful run.

Runs last. It deletes only the intermediate layers that can be rebuilt cheaply
from the raw .nc files (no re-download):

  deleted : per-model derived/ tiffs, the _multimodel/ combine folder, and the
            pre-COG multiband results/*.tif
  kept    : raw .nc downloads, the boundary shapefile, the final COGs
            (results/cog/), and the manifests/ download log

Safety:
  * Does nothing unless at least one final COG exists in results/cog/ (so a
    failed run never triggers deletion).
  * Skipped entirely if WIND_KEEP_INTERMEDIATE is set.
  * Only ever touches paths inside OUTPUT_ROOT.

To rebuild the deleted layers later, just re-run steps 02-05 (the kept raw .nc
files are the source of truth, so nothing is re-downloaded).
"""

import os
import glob
import shutil

import config

BASE_DIR = config.OUTPUT_ROOT


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _mb(n):
    return f"{n / (1024 ** 2):.1f} MB"


def main():
    print("=" * 60)
    print("STEP 06 — Cleanup of intermediate files")
    print("=" * 60)

    if config.KEEP_INTERMEDIATE:
        print("WIND_KEEP_INTERMEDIATE is set — keeping all intermediates.")
        return

    cog_dir = os.path.join(BASE_DIR, "results", "cog")
    cogs = glob.glob(os.path.join(cog_dir, "*.tif"))
    if not cogs:
        print(f"[skip] No final COGs found in {cog_dir}.")
        print("Not deleting anything (nothing verified to keep).")
        return

    print(f"Final COGs present ({len(cogs)}). Cleaning intermediates...")

    # ---- Build the precise delete list (all inside OUTPUT_ROOT) ----
    # 1) per-model derived folders: OUTPUT_ROOT/<model>/<ssp>/<ensemble>/derived
    derived_dirs = glob.glob(os.path.join(BASE_DIR, "*", "*", "*", "derived"))
    # 2) the multi-model combine folder
    multimodel = os.path.join(BASE_DIR, "_multimodel")
    # 3) the pre-COG multiband results (files only; the cog/ subfolder is kept)
    pre_cog = glob.glob(os.path.join(BASE_DIR, "results", "*.tif"))

    freed = 0

    for d in derived_dirs:
        freed += _dir_size(d)
        shutil.rmtree(d, ignore_errors=True)
    if derived_dirs:
        print(f"  removed {len(derived_dirs)} per-model derived/ folder(s)")

    if os.path.isdir(multimodel):
        freed += _dir_size(multimodel)
        shutil.rmtree(multimodel, ignore_errors=True)
        print("  removed _multimodel/ combine folder")

    for f in pre_cog:
        try:
            freed += os.path.getsize(f)
            os.remove(f)
        except OSError:
            pass
    if pre_cog:
        print(f"  removed {len(pre_cog)} pre-COG multiband file(s)")

    print(f"\n[ok] Freed {_mb(freed)}.")
    print("Kept: raw .nc downloads, shapefile, results/cog/, manifests/.")
    print("(Re-run steps 02-05 to rebuild intermediates without re-downloading.)")


if __name__ == "__main__":
    main()
