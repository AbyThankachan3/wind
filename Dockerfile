# Wind pipeline image.
#
# Modern rasterio / geopandas wheels bundle their own GDAL/GEOS/PROJ, so a slim
# Python base is enough -- no system GDAL install needed. Keeps the image small.

FROM python:3.12-slim

# Faster, quieter Python in containers.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System libraries the geospatial wheels load at runtime but do not bundle.
# rasterio's bundled GDAL dynamically links the system Expat (libexpat.so.1);
# libgomp is used by GDAL/numpy for OpenMP threading.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libexpat1 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the pipeline code (data folders are excluded via .dockerignore).
COPY . .

# All output and the downloaded shapefile live on the mounted /data volume, so
# nothing large is written into the container's own layer. The shapefile path
# is derived from WIND_COUNTRY + WIND_GIS_DIR, so a different country only needs
# WIND_COUNTRY changed (see docker-compose.yml).
ENV WIND_OUTPUT_ROOT=/data/WindData/Canada \
    WIND_GIS_DIR=/data/gis

# Non-interactive: --yes skips the confirmation prompt (no TTY in a container).
CMD ["python", "run_all.py", "--yes"]
