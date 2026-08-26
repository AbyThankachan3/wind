#!/usr/bin/env bash
# ============================================================
#  Wind pipeline launcher for a cloud VM (GCP / EC2 / any Linux box)
#  NO DOCKER NEEDED.
#
#  Difference from run.sh: run.sh assumes a laptop and writes data next to
#  this file. On a VM the data (150+ GB) belongs on a separate attached disk,
#  and the box is headless, so this script also:
#     - installs the two system libraries the geospatial wheels need
#     - points all data at a big disk (DATA_DIR below)
#     - sizes the step-02 workers from the machine's actual RAM
#     - checks free space and warns if you are not in tmux/screen
#  then hands over to run.sh (venv + pip install + run_all.py).
#
#  Usage:
#      chmod +x run_gcp.sh          # once
#      ./run_gcp.sh --dry-run       # show the plan and resolved paths
#      ./run_gcp.sh --yes           # run it (do this inside tmux)
#
#  Override anything without editing this file:
#      DATA_DIR=/mnt/disks/wind WIND_COUNTRIES=Canada,UK ./run_gcp.sh --yes
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

# ============================================================
# EDIT THESE
# ============================================================

# Where ALL data goes: the shared raw NASA downloads, the shapefiles and the
# final COGs. Point this at your attached disk, NOT the boot disk -- the raw
# download alone is ~150 GB.
DATA_DIR="${DATA_DIR:-/mnt/disks/winddata}"

# Which countries. "all" = every registered one (raw data is downloaded once
# and shared). Or a list: "Canada,UK". Or set WIND_COUNTRY for a single one.
WIND_COUNTRIES="${WIND_COUNTRIES:-all}"

# Parallel downloads in step 01. A VM has plenty of bandwidth; 6 is fine.
WIND_DOWNLOAD_WORKERS="${WIND_DOWNLOAD_WORKERS:-6}"

# Free space (GB) we expect on the data disk before starting.
MIN_FREE_GB="${MIN_FREE_GB:-250}"

# ============================================================

echo
echo "=== Wind pipeline — cloud VM launcher ==="
echo

# --yes means "non-interactive": don't stop for any of the warnings below.
NONINTERACTIVE=0
for a in "$@"; do
    if [ "$a" = "--yes" ]; then NONINTERACTIVE=1; fi
done

confirm_or_exit() {
    # Skipped entirely under --yes, and when there is no terminal to ask on.
    if [ "$NONINTERACTIVE" = "1" ] || [ ! -t 0 ]; then
        echo "    (continuing anyway)"
        return
    fi
    read -r -p "    Continue? [y/N] " reply
    case "$reply" in
        [yY]*) ;;
        *) echo "Cancelled."; exit 1 ;;
    esac
}

# ---- 1. System libraries -------------------------------------------------
# The rasterio/geopandas wheels bundle their own GDAL/GEOS/PROJ, so there is
# no system GDAL to install -- but that bundled GDAL still dynamically links
# the system Expat, and numpy/GDAL want OpenMP. Same two packages the
# Dockerfile installs. python3-venv is separate from python3 on Debian/Ubuntu.
MISSING=""
dpkg -s python3-venv >/dev/null 2>&1 || MISSING="$MISSING python3-venv"
dpkg -s libexpat1    >/dev/null 2>&1 || MISSING="$MISSING libexpat1"
dpkg -s libgomp1     >/dev/null 2>&1 || MISSING="$MISSING libgomp1"

if [ -n "$MISSING" ]; then
    echo "Installing system packages:$MISSING"
    sudo apt-get update -qq
    # shellcheck disable=SC2086  # word splitting is what we want here
    sudo apt-get install -y --no-install-recommends $MISSING
    echo
else
    echo "System packages: already present."
fi

# ---- 2. Data disk --------------------------------------------------------
if ! mkdir -p "$DATA_DIR" 2>/dev/null; then
    echo "Creating $DATA_DIR needs root (it is on a mounted disk)..."
    sudo mkdir -p "$DATA_DIR"
    sudo chown "$(id -u):$(id -g)" "$DATA_DIR"
fi

if [ ! -w "$DATA_DIR" ]; then
    echo "[ERROR] $DATA_DIR is not writable by $(whoami)."
    echo "        Fix with: sudo chown $(id -u):$(id -g) $DATA_DIR"
    exit 1
fi

FREE_GB=$(df -BG --output=avail "$DATA_DIR" | tail -1 | tr -dc '0-9')
echo "Data dir   : $DATA_DIR  (${FREE_GB} GB free)"

if [ "$FREE_GB" -lt "$MIN_FREE_GB" ]; then
    echo
    echo "[WARNING] Only ${FREE_GB} GB free, expected ${MIN_FREE_GB}+ GB."
    echo "    The raw NASA download alone is ~150 GB. If this is the boot disk,"
    echo "    attach a persistent disk and set DATA_DIR to its mount point."
    confirm_or_exit
fi

# ---- 3. Size the workers to this machine's RAM ---------------------------
# Each step-02 worker holds a full global dataset in memory (~5-8 GB peak), so
# too many workers = the OOM killer stops step 02. Mirrors the table in
# config.py; override by exporting WIND_PROCESS_WORKERS before running.
MEM_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
if [ -z "${WIND_PROCESS_WORKERS:-}" ]; then
    if   [ "$MEM_GB" -ge 120 ]; then WIND_PROCESS_WORKERS=8
    elif [ "$MEM_GB" -ge 60  ]; then WIND_PROCESS_WORKERS=6
    elif [ "$MEM_GB" -ge 30  ]; then WIND_PROCESS_WORKERS=4
    else                             WIND_PROCESS_WORKERS=1
    fi
fi
CPUS=$(nproc)
echo "Machine    : ${MEM_GB} GB RAM, ${CPUS} vCPU -> WIND_PROCESS_WORKERS=$WIND_PROCESS_WORKERS"

if [ "$WIND_PROCESS_WORKERS" -gt "$CPUS" ]; then
    echo "    (note: more workers than vCPUs; lower WIND_PROCESS_WORKERS if step 02 crawls)"
fi

# ---- 4. Warn if this run would die with the SSH session ------------------
# This is a multi-hour job. Outside tmux/screen, closing the laptop kills it.
if [ -z "${TMUX:-}" ] && [ -z "${STY:-}" ] && [ -t 0 ]; then
    echo
    echo "[WARNING] Not running inside tmux or screen."
    echo "    This job runs for hours and will be killed if your SSH session drops."
    echo "    Recommended:  tmux new -s wind    then re-run this script inside it."
    confirm_or_exit
fi

# ---- 5. Hand over to run.sh (venv + deps + pipeline) ---------------------
# Exported so run_all.py and every step subprocess inherit them. Per-country
# output paths derive from WIND_DATA_ROOT, so nothing else needs setting.
export WIND_DATA_ROOT="$DATA_DIR"
export WIND_GIS_DIR="$DATA_DIR/gis"
export WIND_COUNTRIES
export WIND_DOWNLOAD_WORKERS
export WIND_PROCESS_WORKERS

echo "Countries  : $WIND_COUNTRIES"
echo

exec ./run.sh "$@"
