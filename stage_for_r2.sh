#!/usr/bin/env bash
# ============================================================
#  Stage the final COGs into the R2 upload layout.
#
#  Reorganises:
#     <SRC>/<Country>/results/cog/<year>_<ssp>.tif
#  into the exact tree you upload to R2:
#     <DEST>/<iso>/<ssp>/<year>/cog.tiff
#
#  Country -> ISO 3166-1 alpha-2 code. UK uses "gb" (ISO); change to "uk"
#  below if your frontend keys on that. "eu" is the exceptionally-reserved
#  EU code (the whole-Europe bundle).
#
#  Files are COPIED (originals untouched). Then upload <DEST> as-is, e.g.:
#     rclone copy <DEST> r2:<bucket>/wind
#     # or: aws s3 sync <DEST> s3://<bucket>/wind --endpoint-url <r2-endpoint>
#
#  Usage:
#     ./stage_for_r2.sh
#     SRC=/mnt/disks/winddata/WindData DEST=/mnt/disks/winddata/r2_upload/wind ./stage_for_r2.sh
# ============================================================
set -euo pipefail

SRC="${SRC:-/mnt/disks/winddata/WindData}"
DEST="${DEST:-/mnt/disks/winddata/r2_upload/wind}"

# Folder name (as it appears under WindData/) -> ISO alpha-2 code.
declare -A CODE=(
  [USA]=us
  [Canada]=ca
  [EU]=eu
  [UK]=gb
  [Australia]=au
  [UAE]=ae
  [Qatar]=qa
  [Singapore]=sg
)

echo "Source: $SRC"
echo "Dest  : $DEST"
echo

staged=0
skipped=0
for dir in "$SRC"/*/; do
  country="$(basename "$dir")"
  code="${CODE[$country]:-}"
  if [ -z "$code" ]; then
    echo "[skip] no ISO code mapped for country folder '$country'"
    skipped=$((skipped + 1))
    continue
  fi

  cogdir="$dir/results/cog"
  if [ ! -d "$cogdir" ]; then
    echo "[skip] $country: no results/cog folder"
    continue
  fi

  n=0
  for f in "$cogdir"/*.tif; do
    [ -e "$f" ] || continue
    base="$(basename "$f" .tif)"   # e.g. 2030_ssp245
    year="${base%_*}"               # 2030
    ssp="${base#*_}"                # ssp245
    out="$DEST/$code/$ssp/$year/cog.tiff"
    mkdir -p "$(dirname "$out")"
    cp "$f" "$out"
    n=$((n + 1))
    staged=$((staged + 1))
  done
  echo "[ok]  $country -> $code   ($n file(s))"
done

echo
echo "Staged $staged file(s); $skipped country folder(s) skipped."
echo "Tree ready at: $DEST"
echo "Preview:"
find "$DEST" -maxdepth 3 -type d | sort | head -20
