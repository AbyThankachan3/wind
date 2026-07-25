# Wind Exposure Layers — Frontend Info

Display copy for the wind layers. Written for end users, grounded in the actual
processing pipeline (`01`–`05`).

---

## Data Sources

**Climate projections**
- **Dataset:** NASA NEX-GDDP-CMIP6 (NASA Earth Exchange Global Daily Downscaled Projections, CMIP6)
- **Provider:** NASA Center for Climate Simulation (NCCS), accessed via the NCCS THREDDS data server
- **Variable:** `sfcWind` — daily-average near-surface wind speed
- **Models:** 35 global climate models, combined into a single multi-model consensus
- **Spatial resolution:** 0.25° grid (approximately 25 km)
- **Coordinate system:** EPSG:4326 (WGS 84 latitude/longitude)
- **Scenarios:**
  - `ssp245` — moderate-emissions future
  - `ssp585` — high-emissions future

**Administrative boundaries** (used to clip results to land)
- **United States:** US Census Bureau — Cartographic Boundary File, states, 1:500,000 scale (`cb_2018_us_state_500k`)
- **Canada:** Statistics Canada — 2021 Census cartographic boundary file, provinces/territories (`lpr_000b21a_e`)

**Important — what "wind" means here.** All values are **daily-average wind
speed** (strength averaged over a full day), not instantaneous gusts. A storm
gust is much higher and much briefer. These layers describe sustained, day-long
windiness — chronic exposure and how it shifts between scenarios — rather than
the peak gust of a single storm.

---

## Calculation Methodology

Processing runs in four steps: per-model statistics → combine across models →
derive confidence → package for delivery.

### Step 1 — Per-model yearly statistics

For each individual climate model, scenario, and ensemble member, the daily wind
series for the target year is clipped to the land boundary, then reduced to four
yearly statistics at every grid cell:

| Statistic | Calculation |
|---|---|
| Mean wind | Average of all daily values in the year |
| Peak wind | Maximum daily value in the year |
| Severe wind | 95th percentile of daily values in the year |
| Strong-wind days | Count of days where daily-average wind exceeds **12 m/s** |

Cells outside the land boundary are marked as no-data — distinct from a genuine
value of zero, so "no strong-wind days" and "outside the study area" never look
the same.

### Step 2 — Combining across models

1. **Ensemble members are averaged within each model first.** A model
   contributing five ensemble members is reduced to one result before models are
   compared, so no single model dominates purely by submitting more runs
   (equal model weighting).
2. **The per-model results are then averaged across all models** at each grid
   cell to produce the published value.

All models share the same 0.25° NEX-GDDP-CMIP6 grid, so layers are stacked
directly with no resampling or interpolation.

### Step 3 — The five published layers

| Layer | What it measures | Calculation | Units |
|---|---|---|---|
| **Baseline wind exposure** | The typical day's wind — the everyday backdrop of how windy a place is | Multi-model mean of each model's annual **mean** daily wind | m/s |
| **Severe wind exposure** | How strong the wind gets on the windiest days (roughly the windiest 5% of days ≈ 18 days/year) | Multi-model mean of each model's annual **95th percentile** | m/s |
| **Peak wind exposure** | The windiest single day of the year | Multi-model mean of each model's annual **maximum** | m/s |
| **Strong wind frequency** | How often a full day of strong wind occurs | Multi-model mean of each model's **count of days above 12 m/s** | days/year |
| **Confidence** | How strongly the models agree on the severe-wind figure | **Coefficient of variation** across models: standard deviation ÷ mean of severe wind exposure | unitless ratio |

### Step 4 — Confidence layer detail

Confidence is the across-model spread of the severe-wind figure, expressed as a
coefficient of variation (standard deviation divided by the mean). **Smaller =
stronger agreement.**

| Value | Interpretation |
|---|---|
| below ~0.15 | strong agreement |
| 0.15 – 0.30 | moderate agreement |
| above ~0.30 | notable disagreement |

*(Bands are indicative, not strict.)*

Confidence measures **models agreeing with each other — not a guarantee they are
correct.** It indicates where to place more or less weight on an estimate; it is
not a probability of being right.

To avoid unstable ratios, confidence is not computed where the mean severe-wind
value is near zero.

### Step 5 — Delivery format

The five layers are stacked into a single multi-band GeoTIFF per scenario and
converted to a Cloud-Optimized GeoTIFF (COG), so a map viewer fetches only the
region and zoom level it needs. Band descriptions and units are embedded in the
file. Data values are identical to the source layers — only the internal layout
and display overviews differ.

---

## Reading the Values

**Wind speed reference (metres per second):**

| Speed | Roughly | Feels like |
|---|---|---|
| 5 m/s | ~18 km/h (11 mph) | light breeze |
| 8 m/s | ~29 km/h (18 mph) | moderate breeze |
| 12 m/s | ~43 km/h (27 mph) | strong, near-gale sustained wind |
| 18 m/s | ~65 km/h (40 mph) | gale-force sustained wind |

**Guidance:**
- **Compare, don't read in isolation.** The greatest value is in comparison —
  one location versus another, `ssp245` versus `ssp585`, or a future period
  versus today. The relative pattern is robust even where an exact number is
  less so.
- **Pair intensity with frequency.** Severe wind exposure (how strong) and
  strong wind frequency (how often) describe different risks; look at both.
- **Let confidence qualify the rest.** Where confidence is poor, present hazard
  figures with appropriate caution.
- **These are projections, not measurements.** They describe a modelled future
  climate, best used for planning and comparison rather than as a single
  guaranteed value.
- **Different units per layer.** Three layers are in m/s, one in days per year,
  one is a ratio — each should be read on its own scale.
- **Fractional day counts are expected.** A value like 1.4 days is an average
  across many models, so it need not be a whole number. Values near zero are
  normal for calm inland locations and simply mean such days are very rare.
- **Peak wind exposure is more variable** than severe wind exposure — read it
  alongside that layer rather than on its own.
