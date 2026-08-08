"""
Step 01 — Download raw sfcWind NetCDF files from NASA NEX-GDDP-CMIP6.

Reads all settings from config.py. Downloads the target file for every
model / scenario / ensemble / YEAR in the config, in parallel, and records
every attempt in a manifest CSV.

NOTE: these NASA files are GLOBAL. Clipping to the chosen country happens in
step 02, not here.
"""

import os
import re
import csv
import time
import random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import requests
from bs4 import BeautifulSoup

import config

# =========================================================
# CONFIG (from config.py)
# =========================================================

BASE_URL = "https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/"

# Shared, country-independent: the raw global NASA files live here once and are
# reused when clipping to every country (step 02).
DOWNLOAD_ROOT = config.RAW_DIR
YEARS = [str(y) for y in config.YEARS]
SSPS = config.SSPS
MAX_WORKERS = config.DOWNLOAD_WORKERS
VARIABLE = "sfcWind"

MANIFEST_DIR = os.path.join(DOWNLOAD_ROOT, "manifests")
MANIFEST_FILE = os.path.join(MANIFEST_DIR, "download_manifest.csv")

HEADERS = {"User-Agent": "Mozilla/5.0"}

manifest_lock = Lock()

# =========================================================
# MODELS
# =========================================================

MODELS = [
    "ACCESS-CM2", "ACCESS-ESM1-5", "BCC-CSM2-MR", "CESM2", "CESM2-WACCM",
    "CMCC-CM2-SR5", "CMCC-ESM2", "CNRM-CM6-1", "CNRM-ESM2-1", "CanESM5",
    "EC-Earth3", "EC-Earth3-Veg-LR", "FGOALS-g3", "GFDL-CM4", "GFDL-CM4_gr2",
    "GFDL-ESM4", "GISS-E2-1-G", "HadGEM3-GC31-LL", "HadGEM3-GC31-MM",
    "IITM-ESM", "INM-CM4-8", "INM-CM5-0", "IPSL-CM6A-LR", "KACE-1-0-G",
    "KIOST-ESM", "MIROC-ES2L", "MIROC6", "MPI-ESM1-2-HR", "MPI-ESM1-2-LR",
    "MRI-ESM2-0", "NESM3", "NorESM2-LM", "NorESM2-MM", "TaiESM1", "UKESM1-0-LL",
]

# Optional override (mainly for testing): WIND_MODELS="ACCESS-CM2,MIROC6"
_env_models = os.environ.get("WIND_MODELS")
if _env_models:
    MODELS = [m.strip() for m in _env_models.split(",") if m.strip()]
    print(f"[config] MODELS overridden via WIND_MODELS -> {MODELS}")

# =========================================================
# INIT / MANIFEST
# =========================================================

os.makedirs(MANIFEST_DIR, exist_ok=True)

if not os.path.exists(MANIFEST_FILE):
    with open(MANIFEST_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "timestamp", "year", "model", "ssp", "ensemble",
            "filename", "status", "message", "size_mb",
        ])


def log_manifest(year, model, ssp, ensemble, filename, status, message, size_mb):
    with manifest_lock:
        with open(MANIFEST_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                datetime.now(timezone.utc).isoformat(), year, model, ssp, ensemble,
                filename, status, message, size_mb,
            ])


# =========================================================
# CATALOG HELPERS
# =========================================================

def get_xml_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml-xml")


def ssp_exists(model, ssp):
    url = f"{BASE_URL}{model}/{ssp}/catalog.xml"
    try:
        return requests.get(url, headers=HEADERS, timeout=30).status_code == 200
    except Exception:
        return False


def find_ensemble_folders(model, ssp):
    url = f"{BASE_URL}{model}/{ssp}/catalog.xml"
    try:
        soup = get_xml_soup(url)
    except Exception:
        return []
    ensembles = set()
    for ref in soup.find_all("catalogRef"):
        href = ref.get("xlink:href", "")
        match = re.search(r"(r\d+i\d+p\d+f\d+)", href)
        if match:
            ensembles.add(match.group(1))
    return sorted(ensembles)


def variable_exists(model, ssp, ensemble):
    url = f"{BASE_URL}{model}/{ssp}/{ensemble}/{VARIABLE}/catalog.xml"
    try:
        return requests.get(url, headers=HEADERS, timeout=30).status_code == 200
    except Exception:
        return False


def find_target_nc(model, ssp, ensemble, year):
    """Return the .nc filename for this year, or None."""
    url = f"{BASE_URL}{model}/{ssp}/{ensemble}/{VARIABLE}/catalog.xml"
    try:
        soup = get_xml_soup(url)
    except Exception:
        return None
    for dataset in soup.find_all("dataset"):
        filename = dataset.get("name", "")
        if filename.endswith(".nc") and year in filename:
            return filename
    return None


def build_download_url(model, ssp, ensemble, filename):
    return (
        "https://ds.nccs.nasa.gov/thredds/fileServer/AMES/NEX/GDDP-CMIP6/"
        f"{model}/{ssp}/{ensemble}/{VARIABLE}/{filename}"
    )


# =========================================================
# DOWNLOAD WORKER
# =========================================================

# Number of times to (re)try a single file before giving up. Large climate
# downloads routinely hit transient connection drops (IncompleteRead), so a
# whole run of hundreds of files WILL see some -- we resume rather than fail.
MAX_RETRIES = 8


def _stream_download(download_url, temp_path, filename):
    """Download to temp_path with HTTP-range resume + retries.

    Returns True on a fully-completed download. A partial file is left in place
    between attempts (and between whole runs) so we never re-fetch bytes we
    already have.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        existing = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
        headers = dict(HEADERS)
        mode = "wb"
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"
            mode = "ab"

        try:
            with requests.get(download_url, stream=True, headers=headers,
                              timeout=120) as r:
                # 416 = range past EOF: the file is already fully downloaded.
                if r.status_code == 416 and existing > 0:
                    return True
                # Server ignored our Range (sent 200 not 206): restart clean.
                if existing > 0 and r.status_code == 200:
                    existing = 0
                    mode = "wb"
                r.raise_for_status()

                total = int(r.headers.get("content-length", 0)) + existing
                downloaded = existing
                start_time = time.time()

                with open(temp_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = (downloaded - existing) / (1024 ** 2) / max(elapsed, 1)
                        if total > 0:
                            percent = (downloaded / total) * 100
                            print(f"\r{filename[:40]} | {percent:.1f}% | "
                                  f"{downloaded / (1024 ** 2):.1f} MB | "
                                  f"{speed:.2f} MB/s", end="")

            # Confirm we got the whole thing before declaring success.
            if total > 0 and os.path.getsize(temp_path) < total:
                raise IOError(
                    f"incomplete: {os.path.getsize(temp_path)}/{total} bytes")
            return True

        except Exception as e:
            got = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
            print(f"\n[retry {attempt}/{MAX_RETRIES}] {filename}: {e} "
                  f"(have {got / (1024 ** 2):.1f} MB, will resume)")
            time.sleep(min(5 * attempt, 30))

    return False


def download_task(task):
    year = task["year"]
    model = task["model"]
    ssp = task["ssp"]
    ensemble = task["ensemble"]
    filename = task["filename"]
    download_url = task["download_url"]
    final_path = task["output_path"]
    temp_path = final_path + ".part"

    time.sleep(random.uniform(0.5, 2.0))

    if os.path.exists(final_path):
        print(f"\n[SKIP] Already exists:\n{final_path}")
        log_manifest(year, model, ssp, ensemble, filename, "already_exists",
                     "file already downloaded",
                     round(os.path.getsize(final_path) / (1024 ** 2), 2))
        return

    os.makedirs(os.path.dirname(final_path), exist_ok=True)

    print("\n================================================")
    print(f"DOWNLOADING [{year}]: {filename}")
    print("================================================")

    if _stream_download(download_url, temp_path, filename):
        os.rename(temp_path, final_path)
        size_mb = round(os.path.getsize(final_path) / (1024 ** 2), 2)
        print(f"\n[DONE] {filename}")
        log_manifest(year, model, ssp, ensemble, filename, "completed",
                     "download successful", size_mb)
    else:
        msg = f"failed after {MAX_RETRIES} attempts"
        print(f"\n[FAILED] {filename}\n{msg}")
        log_manifest(year, model, ssp, ensemble, filename, "failed", msg, 0)
        # Leave the .part file so the NEXT run can resume it, not restart.


# =========================================================
# BUILD TASK LIST (across all years)
# =========================================================

def build_tasks():
    tasks = []
    for model in MODELS:
        print("\n================================================")
        print(f"MODEL: {model}")
        print("================================================")

        for ssp in SSPS:
            print(f"\nSSP: {ssp}")

            if not ssp_exists(model, ssp):
                print(f"[MISSING SSP] {ssp}")
                log_manifest("", model, ssp, "", "", "missing_ssp",
                             "ssp folder not found", 0)
                continue

            ensembles = find_ensemble_folders(model, ssp)
            if not ensembles:
                print("[MISSING ENSEMBLES]")
                log_manifest("", model, ssp, "", "", "missing_ensemble",
                             "no ensemble folders found", 0)
                continue

            print(f"Found ensembles:\n{ensembles}")

            for ensemble in ensembles:
                print(f"\nChecking ensemble: {ensemble}")

                if not variable_exists(model, ssp, ensemble):
                    print(f"[MISSING VARIABLE] {VARIABLE}")
                    log_manifest("", model, ssp, ensemble, "", "missing_variable",
                                 f"{VARIABLE} folder not found", 0)
                    continue

                for year in YEARS:
                    filename = find_target_nc(model, ssp, ensemble, year)
                    if not filename:
                        print(f"[MISSING YEAR] {year}")
                        log_manifest(year, model, ssp, ensemble, "", "missing_year",
                                     f"{year} file not found", 0)
                        continue

                    print(f"Found file [{year}]:\n{filename}")

                    output_path = os.path.join(
                        DOWNLOAD_ROOT, model, ssp, ensemble, "raw", filename
                    )
                    tasks.append({
                        "year": year,
                        "model": model,
                        "ssp": ssp,
                        "ensemble": ensemble,
                        "filename": filename,
                        "download_url": build_download_url(model, ssp, ensemble, filename),
                        "output_path": output_path,
                    })
    return tasks


# =========================================================
# MAIN
# =========================================================

def main():
    print("\n================================================")
    print("DISCOVERING FILES TO DOWNLOAD")
    print(f"Years: {YEARS}  |  SSPs: {SSPS}")
    print("================================================")

    tasks = build_tasks()

    print("\n================================================")
    print("STARTING PARALLEL DOWNLOADS")
    print("================================================")
    print(f"Total tasks: {len(tasks)}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(download_task, t) for t in tasks]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"\n[THREAD ERROR] {e}")

    print("\n================================================")
    print("ALL DOWNLOADS COMPLETED")
    print("================================================")


if __name__ == "__main__":
    main()
