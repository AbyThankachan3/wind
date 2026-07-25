# Wind Layers — UI Text

All copy for the Wind tab: the ⓘ info button and every "What is this?" tooltip.

**Writing rule for this file:** every section assumes the reader knows nothing
about climate science, statistics, or GIS. No jargon without a plain-English
explanation in the same sentence. Anyone should be able to read a tooltip once
and understand what they're looking at.

---

# 1. Info button (ⓘ)

***Data Sources*** : Wind exposure projections derived from the NASA Earth Exchange Global Daily Downscaled Projections (NEX-GDDP-CMIP6) dataset, incorporating daily-average near-surface wind speed modeled across 35 global climate models downscaled to a 0.25° (~25 km) grid under Shared Socioeconomic Pathway (SSP) climate scenarios.

***Calculation Methodology*** : Wind hazard layers represent multi-model consensus projections of sustained daily-average wind speed. Multi-band rasters contain baseline (annual mean), severe (95th percentile), and peak (annual maximum) wind exposure expressed in metres per second, strong wind frequency as the number of days per year exceeding 12 m/s, and a confidence layer expressing across-model agreement. Ensemble members are averaged within each model before models are combined, so that no single model dominates through additional runs. Confidence is calculated as the coefficient of variation of severe wind exposure across models, where lower values indicate stronger agreement — representing consistency between models rather than a guarantee of accuracy. All values represent day-long average wind speeds rather than instantaneous storm gusts, which are substantially higher and briefer in duration. These datasets are optimized for regional-scale wind risk visualization and scenario comparison rather than property-level engineering or structural design analysis. Modeled wind projections contain inherent uncertainty and may not fully represent localized terrain effects, surface roughness, microclimates, or peak gust conditions.

---

# 2. "What is this?" — LAYER

### Tooltip: the Layer dropdown itself

> Each layer answers a different question about wind at this location. Some
> describe **how strong** the wind gets; others describe **how often** strong
> wind happens, or **how reliable** the estimate is.
>
> No single layer tells the whole story — switching between them gives you a
> fuller picture.
>
> **Important:** every layer here measures wind averaged over a **whole day**,
> not sudden gusts. A gust in a storm is much stronger but lasts seconds. These
> maps describe sustained, all-day windiness.

---

### Tooltip: **Mean**

> **The wind on a typical day.**
>
> This is the average wind speed across every day of the year. It tells you the
> general backdrop — how windy this place usually is — rather than how bad it
> can get.
>
> Think of it as the everyday setting, not the hazard. A location can have a
> calm average and still experience damaging winds occasionally, so use this
> for context and check the other layers for the extremes.
>
> *Example:* 6.5 m/s means that on an ordinary day, this location sees a steady
> moderate breeze (about 14 mph).

---

### Tooltip: **95th Percentile**

> **How strong the wind gets on the windiest days.**
>
> Imagine listing all 365 days of the year and sorting them from calmest to
> windiest. This value is the level reached by the windiest 5% of them — roughly
> the 18 windiest days of the year.
>
> Because it's based on many days rather than a single one, it's a steady,
> dependable measure of a location's strong-wind conditions. **This is usually
> the most useful layer to focus on.**
>
> *Example:* 11 m/s means that on its windier days, this location experiences
> sustained winds around 11 m/s (about 25 mph).

---

### Tooltip: **Maximum**

> **The windiest single day of the year.**
>
> This is the strongest day-long average wind expected across the whole year —
> the worst routine day.
>
> Because it rests on just one day, it moves around more than the other layers:
> a single unusual day can shift it noticeably. For that reason, read it
> alongside the 95th Percentile rather than on its own.
>
> *Example:* 18 m/s means the worst day of the year reaches sustained winds
> around 18 m/s (about 40 mph) — gale-force, held for a full day.


---

# 3. "What is this?" — PROJECTION YEAR

> **The future year these maps describe.**
>
> These are projections, not records of past weather. Selecting a year shows
> the wind conditions expected around that point in the future, based on climate
> models.
>
> Comparing different years reveals how conditions are expected to shift over
> time at this location.
>
> Because the future is uncertain, treat these as well-informed estimates for
> planning and comparison — not as a forecast of a specific date. The pattern of
> change across years is more dependable than any single year's exact number.

---

# 4. "What is this?" — SCENARIO


### Tooltip: **RCP 4.5**

> **A moderate-emissions future.**
>
> In this scenario the world takes meaningful action on emissions. They rise for
> a while, level off around the middle of the century, and then decline. Warming
> continues but is substantially limited.
>
> This is often described as the "middle of the road" path — neither the best
> case nor the worst.
>
> **Use it as:** your central planning case, and the baseline you compare the
> more severe scenario against.

---

### Tooltip: **RCP 8.5**

> **A high-emissions future.**
>
> In this scenario emissions continue rising throughout the century with little
> restraint. It produces the most warming and the largest changes in climate
> conditions of the scenarios shown.
>
> **Use it as:** a stress test. It answers "how exposed would this location be
> if the world does little?" Planning against it is a way of checking whether a
> decision holds up under severe conditions.
>
> Comparing RCP 8.5 against RCP 4.5 shows how much of this location's future
> risk depends on global emissions choices rather than on local factors.

---