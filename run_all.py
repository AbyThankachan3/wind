"""
Run the whole wind pipeline.

The raw NASA data is GLOBAL, so it is downloaded ONCE into a shared folder
(config.RAW_DIR) and then clipped to each country. So the order is:

    step 01  (once)         download shared global wind data
    then, for EACH country:
        step 00             boundary shapefile
        steps 02-06         clip -> stats -> combine -> stack -> COG -> cleanup

Which countries are processed comes from config.COUNTRIES
(WIND_COUNTRIES="all" or a list; otherwise just the single WIND_COUNTRY).

Usage:
    python run_all.py            # confirm, then run
    python run_all.py --yes      # skip the confirmation prompt
    python run_all.py --dry-run  # print the plan (and resolved paths) and exit
"""

import os
import sys
import time
import subprocess

import config

HERE = os.path.dirname(os.path.abspath(__file__))

# Runs ONCE (country-independent) — the big shared download.
GLOBAL_STEPS = [
    ("01-download-wind-data.py", "Download raw wind data — shared across all countries"),
]

# Runs once PER COUNTRY.
PER_COUNTRY_STEPS = [
    ("download_shapefile.py",         "Boundary shapefile"),
    ("02-derived.py",                 "Clip to country + per-model stats"),
    ("03-ensemble-derived.py",        "Combine across all models"),
    ("04-multiband-tiff-creation.py", "Stack layers into multi-band GeoTIFFs"),
    ("05-cog.py",                     "Convert to Cloud-Optimized GeoTIFFs"),
    ("06-cleanup.py",                 "Remove regenerable intermediates"),
]

ALL_SCRIPTS = [s for s, _ in GLOBAL_STEPS + PER_COUNTRY_STEPS]


def banner(text):
    print("\n" + "=" * 62)
    print(text)
    print("=" * 62)


def _country_env(country, multi):
    """Environment for one country's subprocesses."""
    env = os.environ.copy()
    env["WIND_COUNTRY"] = country
    if multi:
        # Let each country derive its own output/shapefile paths.
        env.pop("WIND_OUTPUT_ROOT", None)
        env.pop("WIND_SHAPEFILE", None)
        env.pop("WIND_COUNTRIES", None)
    return env


def _run(script, env):
    return subprocess.run([sys.executable, os.path.join(HERE, script)],
                          cwd=HERE, env=env).returncode


def _print_resolved(country, multi):
    """Show the paths a country would resolve to (for the dry-run plan)."""
    env = _country_env(country, multi)
    subprocess.run(
        [sys.executable, "-c",
         "import config; print('\\n'.join('    ' + l for l in config.summary_lines()))"],
        cwd=HERE, env=env,
    )


def main():
    args = sys.argv[1:]
    skip_confirm = "--yes" in args
    dry_run = "--dry-run" in args or "--plan" in args

    countries = config.COUNTRIES
    multi = len(countries) > 1

    banner("WIND PIPELINE")
    print(f"Countries   : {', '.join(countries)}")
    print(f"Years       : {config.YEARS}")
    print(f"Scenarios   : {config.SSPS}")
    print(f"Shared raw  : {config.RAW_DIR}")

    # ---- Pre-flight: all scripts present ----
    for script in ALL_SCRIPTS:
        if not os.path.exists(os.path.join(HERE, script)):
            print(f"\n[ERROR] Missing pipeline script: {script}")
            sys.exit(1)

    print(
        f"\nNOTE: the global NASA data (~35 models x {len(config.SSPS)} scenarios "
        f"x {len(config.YEARS)} years) is downloaded\n"
        f"      ONCE to {config.RAW_DIR} (~150+ GB) and reused for every country.\n"
        f"      Adding countries does NOT re-download it."
    )

    # ---- Dry run: show the plan and the resolved paths per country ----
    if dry_run:
        banner("PLAN (dry run — nothing will be downloaded or written)")
        print("Global (once):")
        for s, d in GLOBAL_STEPS:
            print(f"  - {s}: {d}")
        for ci, country in enumerate(countries, 1):
            print(f"\nCountry {ci}/{len(countries)}: {country}")
            _print_resolved(country, multi)
            for s, d in PER_COUNTRY_STEPS:
                print(f"      - {s}: {d}")
        return

    if not skip_confirm:
        try:
            input("\nPress Enter to begin  (Ctrl+C to cancel)... ")
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(1)

    overall_start = time.time()

    # ---- 1) Global download (once) ----
    banner("GLOBAL — Download raw wind data (shared)")
    rc = _run("01-download-wind-data.py", os.environ.copy())
    if rc != 0:
        print(f"\n[ERROR] Download step failed (exit {rc}). Stopping — nothing "
              f"downstream can run without the data.")
        sys.exit(rc)

    # ---- 2) Per-country processing ----
    results = {}
    for ci, country in enumerate(countries, 1):
        banner(f"COUNTRY {ci}/{len(countries)} — {country}")
        env = _country_env(country, multi)
        ok = True
        for i, (script, desc) in enumerate(PER_COUNTRY_STEPS, 1):
            print(f"\n--- [{country}] step {i}/{len(PER_COUNTRY_STEPS)}: {desc} ---")
            rc = _run(script, env)
            if rc != 0:
                print(f"\n[ERROR] {country}: '{script}' failed (exit {rc}).")
                ok = False
                if multi:
                    print("Continuing with the next country.")
                break
        results[country] = "ok" if ok else "FAILED"
        if not ok and not multi:
            sys.exit(1)

    # ---- Summary ----
    banner("ALL DONE")
    print(f"Total time: {time.time() - overall_start:.0f}s\n")
    for country, status in results.items():
        mark = "[ok] " if status == "ok" else "[!!] "
        cog = os.path.join(config.DATA_ROOT, "WindData", country, "results", "cog")
        print(f"  {mark}{country:12s} {status:7s} -> {cog}")

    if any(v != "ok" for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
