"""
Run the whole wind pipeline in order: 01 -> 02 -> 03 -> 04 -> 05.

Each step is run as a separate process. If any step fails, the pipeline stops
and tells you which one, so nothing downstream runs on incomplete data.

Usage:
    python run_all.py            # asks for confirmation, then runs everything
    python run_all.py --yes      # skip the confirmation prompt
"""

import os
import sys
import time
import subprocess

import config

HERE = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("download_shapefile.py",         "Ensure the country boundary shapefile is present"),
    ("01-download-wind-data.py",      "Download raw wind data (NASA NEX-GDDP-CMIP6)"),
    ("02-derived.py",                 "Per-model yearly layers (clip to country + statistics)"),
    ("03-ensemble-derived.py",        "Combine across all models"),
    ("04-multiband-tiff-creation.py", "Stack the layers into multi-band GeoTIFFs"),
    ("05-cog.py",                     "Convert to Cloud-Optimized GeoTIFFs (final output)"),
]


def banner(text):
    print("\n" + "=" * 62)
    print(text)
    print("=" * 62)


def main():
    skip_confirm = "--yes" in sys.argv

    banner("WIND PIPELINE")
    for line in config.summary_lines():
        print(line)

    # ---- Pre-flight checks ----
    # The shapefile itself is fetched by step 00 (download_shapefile.py) if it
    # is missing, so it is not required to exist up front.
    for script, _ in STEPS:
        if not os.path.exists(os.path.join(HERE, script)):
            print(f"\n[ERROR] Missing pipeline script: {script}")
            sys.exit(1)

    n_files = len(config.YEARS) * len(config.SSPS)
    print(
        f"\nNOTE: Step 01 downloads GLOBAL climate files (clipping to "
        f"{config.COUNTRY} happens later).\n"
        f"      Roughly 35 models x {len(config.SSPS)} scenarios x "
        f"{len(config.YEARS)} years of source data will be fetched.\n"
        f"      This can be tens of gigabytes and take a long time. Make sure "
        f"there is enough\n      disk space free at: {config.OUTPUT_ROOT}"
    )

    if not skip_confirm:
        try:
            input("\nPress Enter to begin  (Ctrl+C to cancel)... ")
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(1)

    # ---- Run each step ----
    overall_start = time.time()
    for i, (script, desc) in enumerate(STEPS, 1):
        banner(f"STEP {i}/{len(STEPS)} — {desc}")
        start = time.time()
        result = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=HERE)
        if result.returncode != 0:
            print(f"\n[ERROR] Step {i} ({script}) failed with exit code "
                  f"{result.returncode}. Pipeline stopped.")
            sys.exit(result.returncode)
        print(f"\n[ok] Step {i} finished in {time.time() - start:.0f}s")

    banner("ALL DONE")
    print(f"Total time: {time.time() - overall_start:.0f}s")
    print(f"\nFinal Cloud-Optimized GeoTIFFs are in:")
    print(f"  {os.path.join(config.OUTPUT_ROOT, 'results', 'cog')}")


if __name__ == "__main__":
    main()
