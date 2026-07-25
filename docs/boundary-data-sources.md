# Boundary Shapefile Source Registry

Administrative boundary files used to clip wind rasters to land, by region.
All sourced from official government or intergovernmental portals.

**Status legend**
- ✅ **Downloaded** — file on disk and verified
- ⏳ **In progress** — downloading
- 🕓 **Deferred** — *to be downloaded later*
- ⚠️ **Provenance issue** — see notes before using client-facing

---

## Summary

| Region | Countries | Source | Status |
|---|---|---|---|
| Canada | 1 | Statistics Canada | ✅ Downloaded |
| United States | 1 | US Census Bureau | ✅ Already in use |
| EU | **37** (EU-27 + EFTA-4 + 5 candidates) | Eurostat GISCO | ✅ Downloaded |
| UK | 4 constituent countries | ONS | ✅ Downloaded |
| Australia | states/territories | ABS | ✅ Downloaded |
| Middle East | 17 (2 already covered by EU file) | Mixed — see below | 🕓 15 deferred |

---

## ✅ Completed

### United States
- **Source:** US Census Bureau — Cartographic Boundary Files
- **File:** `GIS Files/State/cb_2018_us_state_500k.shp`
- **Scale:** 1:500,000 cartographic
- **Note:** already wired into `02-derived.py`

### Canada
- **Source:** [Statistics Canada — 2021 Census Boundary Files](https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21)
- **Direct link:** `https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lpr_000b21a_e.zip`
- **File:** `GIS Files/Canada/lpr_000b21a_e.shp`
- **Contents:** 13 provinces/territories · CRS EPSG:3347 · cartographic (landmass only)
- **Key columns:** `PRUID`, `PRENAME`, `PREABBR`, `LANDAREA`

### United Kingdom
- **Source:** [ONS Open Geography Portal](https://geoportal.statistics.gov.uk/) — Countries (December 2024) Boundaries UK BUC
- **File:** `GIS Files/UK/CTRY_DEC_2024_UK_BUC.shp`
- **Contents:** 4 countries (England, Scotland, Wales, N. Ireland) · CRS EPSG:27700 (British National Grid) · ultra-generalised 500 m
- **Key columns:** `CTRY24CD`, `CTRY24NM`
- **Note:** UK is **not** in Eurostat NUTS 2021 (post-Brexit), so it requires this separate source — no overlap with the EU file.

### European Union
- **Source:** [Eurostat GISCO — NUTS 2021](https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics)
- **Direct link:** `https://gisco-services.ec.europa.eu/distribution/v2/nuts/download/ref-nuts-2021-01m.shp.zip`
- **File (use this one):** `GIS Files/EU/NUTS_RG_01M_2021_4326_LEVL_0.shp`
- **CRS:** **EPSG:4326 already** — the only file in the set needing no reprojection
- **Scale:** 1:1,000,000 (~500 m precision)
- **Key columns:** `NUTS_ID`, `CNTR_CODE`, `ISO3_CODE`, `NAME_ENGL`, `EU_STAT`, `EFTA_STAT`, `CC_STAT`

**Coverage — 37 countries at level 0, not just the EU-27:**

| Group | Count | Countries |
|---|---|---|
| EU members (`EU_STAT=T`) | 27 | incl. **Cyprus** |
| EFTA (`EFTA_STAT=T`) | 4 | Iceland, Liechtenstein, Norway, Switzerland |
| Candidates (`CC_STAT=T`) | 5 | Albania, Montenegro, North Macedonia, Serbia, **Türkiye** |

Filter on `EU_STAT` / `EFTA_STAT` / `CC_STAT` to select the group you want.

**Levels 0–3 all extracted** (`LEVL_0` countries … `LEVL_3` small regions).
Other projections (EPSG:3035 ETRS89-LAEA, EPSG:3857 Web Mercator) remain
available in `GIS Files/EU/_archives/` if ever needed.

- **Why 1:1M:** the wind grid is 0.25° (~25 km), so even 1:3M would suffice. 1:1M chosen for quality headroom and consistency with the Canada file.

### Australia
- **Source:** [ABS — ASGS Edition 3 Digital Boundary Files](https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files)
- **Direct link:** `https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files/STE_2021_AUST_SHP_GDA2020.zip`
- **File:** `GIS Files/Australia/STE_2021_AUST_GDA2020.shp`
- **Contents:** 10 records (8 states/territories + Other Territories + an outside-Australia record) · CRS GDA2020
- **Key columns:** `STE_CODE21`, `STE_NAME21`, `AREASQKM21`

---

## 🕓 Middle East — Deferred (download later)

**15 of 17 deferred. Links verified and ready to pull on your go-ahead.**

✅ **Already covered by the Eurostat file — no download needed:**
- **Cyprus** — EU member (`NUTS_ID=CY`)
- **Türkiye** — EU candidate country, included at NUTS level 0

*For Türkiye, the Eurostat version is preferable to the COD-AB one: same
underlying national mapping-agency lineage, but distributed by the European
Commission rather than via a humanitarian working group. The COD-AB link is
retained below as a fallback.*

Distributed via UN OCHA's Common Operational Datasets (COD-AB) on the
Humanitarian Data Exchange. **COD-AB is a distribution wrapper, not a data
source** — the underlying provenance varies per country and is listed
explicitly below, because it varies from "national statistics office" to
"18-year-old FAO dataset."

### Government-sourced — provenance OK

| Country | Source authority | Download link |
|---|---|---|
| **UAE** | Federal Competitiveness and Statistics Centre, Ministry of Cabinet Affairs | [are_admin_boundaries.shp.zip](https://data.humdata.org/dataset/23d41c1f-41ef-4957-a47e-b8c08c984d83/resource/8e3dce55-76e9-4ea1-a4d9-93eccdc4b66d/download/are_admin_boundaries.shp.zip) |
| **Qatar** | Qatar Planning and Statistics Authority | [qat_adm_psa_20240627_ab_shp.zip](https://data.humdata.org/dataset/6a84f3b8-41cd-4769-a61f-6dbd5f61bd05/resource/2345dd03-d14f-4038-9e96-8c235056d25f/download/qat_adm_psa_20240627_ab_shp.zip) |
| **Egypt** | CAPMAS (Central Agency for Public Mobilization and Statistics) | [egy_admin_boundaries.shp.zip](https://data.humdata.org/dataset/b90d81ba-7c7a-4283-9899-827480d80a79/resource/6115d7e5-4ba4-451d-988e-f791f4716e7a/download/egy_admin_boundaries.shp.zip) |
| **Iraq** | Iraq Central Statistics Office | [irq_admin_boundaries.shp.zip](https://data.humdata.org/dataset/488bb3cd-3ce9-49d3-862a-3ce7975c63e1/resource/1d1ed1f3-a295-47b6-800d-356dc1036731/download/irq_admin_boundaries.shp.zip) |
| **Türkiye** ✅ | *Covered by Eurostat NUTS (candidate country)* — fallback: General Command of Mapping | [tur_admin_boundaries.shp.zip](https://data.humdata.org/dataset/d74086a0-f398-4474-9e12-1b9a70907bd0/resource/d2315bc0-033e-4912-aab1-06afe3495694/download/tur_admin_boundaries.shp.zip) *(not needed)* |
| **Yemen** | Central Statistical Organization (CSO) | [yem_admin_boundaries.shp.zip](https://data.humdata.org/dataset/6b2656e2-b915-4671-bfed-468d5edcd80a/resource/eb58b807-bea0-450f-a654-0fa49054b4e0/download/yem_admin_boundaries.shp.zip) |
| **Lebanon** | Council for Development and Reconstruction (CDR) | [lbn_admin_boundaries.shp.zip](https://data.humdata.org/dataset/569beba7-bad7-4951-a19d-468a035461cd/resource/1d8198d3-8f50-405a-9534-6c131fe3d6d2/download/lbn_admin_boundaries.shp.zip) |
| **Palestine** | Palestinian Authority Ministry of Planning | [pse_admin_boundaries.shp.zip](https://data.humdata.org/dataset/2caf8373-816f-458c-9913-71bddb9cab7c/resource/ebf1cc7b-45e0-43bb-bec5-2464cd2d26fc/download/pse_admin_boundaries.shp.zip) |
| **Cyprus** | — *EU member, covered by the Eurostat NUTS file* | *(no separate download)* |

### ⚠️ NOT government-sourced — use with caution

These fail the "official government source" bar. Downloading them gives
complete coverage now; swapping in official files later is the better end state.

| Country | What the file actually is | Issue | Download link |
|---|---|---|---|
| **Saudi Arabia** | GADM (academic aggregator) | Filename is literally `sau_admin_boundaries` from GADM 2021 | [sau_admin_boundaries.shp.zip](https://data.humdata.org/dataset/41ce9023-1d21-4549-a485-94316200aba0/resource/cbe8dbc9-4d5d-462f-9333-bf3cc163b3cc/download/sau_admin_boundaries.shp.zip) |
| **Kuwait** | GADM v2.8, **November 2015** | Over 10 years old | [kwt_admin_boundaries.shp.zip](https://data.humdata.org/dataset/a28f399f-482c-4e62-8dbf-d2c12381674a/resource/9c9ccd7e-7ffb-4005-a301-db7d39127b61/download/kwt_admin_boundaries.shp.zip) |
| **Oman** | GADM | Academic aggregator | [omn_admin_boundaries.shp.zip](https://data.humdata.org/dataset/da87f54e-64bd-4cf4-bd31-3fc520f94609/resource/f08b9646-6bb8-4859-a0f9-295d58c42503/download/omn_admin_boundaries.shp.zip) |
| **Bahrain** | FAO GAUL **2008** | 18 years old — oldest in the set | [boundaries_bahrain_0_gaul.zip](https://data.humdata.org/dataset/23a85209-66d3-4d10-a69f-7baf6d2cc8c1/resource/6b11ac4e-2ef7-4ec4-a1ea-006c7c85ded0/download/boundaries_bahrain_0_gaul.zip) |

**Official alternatives exist but are registration-gated** (an account must be
created manually — this can't be automated):
- Saudi Arabia — [GEOSA National Geospatial Platform](https://www.geosa.gov.sa/en/Pages/default.aspx) (national mapping agency)
- Bahrain — [data.gov.bh](https://data.gov.bh/) (Information & eGovernment Authority, 390+ datasets)
- Oman — [Environment Authority GIS open data](https://ea.gov.om/en/open-data/open-data-sets/gis-data/)
- Kuwait — [e.gov.kw open data](https://e.gov.kw/sites/kgoenglish/Pages/OtherTopics/OpenData.aspx)

### ⚠️ UN-sourced (intergovernmental, not national government)

| Country | Source | Download link |
|---|---|---|
| **Iran** | UNHCR | [irn_admin_boundaries.shp.zip](https://data.humdata.org/dataset/247b4026-79ff-4b16-95b9-0f366792d2cc/resource/515839b3-68cd-4308-818d-7d21b43c22d3/download/irn_admin_boundaries.shp.zip) |
| **Syria** | UN Cartographic Section (UNCS) and partners | [syr_admin_boundaries.shp.zip](https://data.humdata.org/dataset/356a63e9-90aa-4b9c-a938-58ef24469c00/resource/2e69313a-b8a8-46bf-8cc8-fbd132b279bd/download/syr_admin_boundaries.shp.zip) |

### ❌ No COD-AB available — needs separate sourcing

| Country | Situation |
|---|---|
| **Israel** | [Survey of Israel](https://www.gov.il/en/departments/survey_of_israel) is the official mapping agency, but publishes DXF / ARC-INFO rather than open shapefiles. No open download located. |
| **Jordan** | Only geoBoundaries (academic, College of William & Mary). Department of Statistics / Royal Jordanian Geographic Centre have no open shapefile download located. |

---

## ⚠️ Disputed boundaries — read before client-facing use

Middle East boundaries include internationally disputed segments. **Every
dataset encodes one interpretation**, and the choice is a visible editorial
position on a client-facing map:

- Israel / Palestine (West Bank, Gaza, Jerusalem)
- Golan Heights (Israel / Syria)
- Abu Musa and the Greater/Lesser Tunb islands (Iran / UAE)
- Iraq–Kuwait border
- Saudi–Yemen border zones

For clipping a 25 km wind raster the practical impact is negligible — a
disputed strip is smaller than a single pixel in most cases. For map display
and attribution, it matters. Recommend citing the source authority per country
(the table above) rather than presenting boundaries as unattributed fact.

---

## Notes for pipeline integration

- All files get reprojected to **EPSG:4326** by `_init_worker` in
  `02-derived.py` via `.to_crs(CRS)` — no manual conversion needed regardless of
  each file's native CRS.

  | Region | Native CRS | Reprojection needed |
  |---|---|---|
  | EU | EPSG:4326 | none — already correct |
  | US | EPSG:4269 (NAD83) | automatic |
  | Canada | EPSG:3347 (StatCan Lambert) | automatic |
  | UK | EPSG:27700 (British National Grid) | automatic |
  | Australia | GDA2020 | automatic |
- The `CONUS_ONLY` / `NON_CONUS` filter in `02-derived.py` is US-specific
  (keys off `STUSPS`). Each region needs its own equivalent or none at all.
- Column names differ per country — there is no shared schema. See the
  per-region "key columns" notes above.
