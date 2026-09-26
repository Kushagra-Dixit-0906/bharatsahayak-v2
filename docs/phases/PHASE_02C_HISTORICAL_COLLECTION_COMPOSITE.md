# Phase 2C — Historical Satellite Collection & Annual Composite Strategy
## Master Architectural Design Review & Specification

> **Status:** 🟢 APPROVED & SEALED (Phase 2C Design Approved & Sealed / Ready for Implementation)  
> **Base Sealed Checkpoints:**  
> - Phase 1 Foundation: `60f8d90 — docs: finalize Phase 1 Earth Engine foundation documentation`  
> - Phase 2A Architecture: `2e5f930 — docs: seal Phase 2A historical satellite architecture`  
> - Phase 2B Temporal Window: `d99c699 — docs: seal Phase 2B temporal window architecture`  
> **Target Subphase:** Phase 2C — Historical Collection & Annual Composite Strategy  
> **Implementation Code:** ZERO (Design & Specification Only)  

---

## 1. Executive Summary & Core Architectural Decisions

Phase 2C defines the data engineering, selection semantics, and compositing mathematics required to construct representative annual historical observations for BharatSahayak V2 under **Option C (Annual Matched-Window Regional Observations)**.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                               PHASE 2C DATA WORKFLOW                                    │
│                                                                                         │
│   Target Historical Years: Y-1, Y-2, Y-3                                               │
│   Each evaluated independently within its Phase 2B 31-day seasonal window [S_h, E_h]   │
│                                                                                         │
│   For each historical year Y_h:                                                         │
│   1. S2 Harmonized Ingestion & Bounding (COPERNICUS/S2_SR_HARMONIZED)                  │
│   2. Phase 1 Quality Gate (cs_cdf >= 0.60, min_usable_coverage >= 70%, scene cloud < 20%)│
│   3. Temporal Recency Sorting: Usable observations sorted newest → oldest               │
│   4. Bounded Selection: Select UP TO 3 most recent usable observations                 │
│      (3+ → select 3 newest, 2 → select 2, 1 → select 1, 0 → no_data)                    │
│   5. Per-Scene NDVI Calculation: NDVI_i = (B8 - B4) / (B8 + B4) on each selected image   │
│   6. Pixel-Wise Median NDVI Compositing: Composite_Raster = pixel_median(NDVI_1..N)     │
│   7. Regional Zonal Reduction: Mean, Median, Min, Max over Composite_Raster            │
│   8. Output: ONE Annual Matched-Window Regional NDVI Observation for Year Y_h          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Findings & Selected Decisions:
1. **Independent Annual Processing (Part A Architecture):**  
   Each historical year ($Y-1, Y-2, Y-3$) is evaluated as an independent, isolated processing pipeline anchored to its Phase 2B seasonal window. Independent processing is selected for the bounded 3-year MVP to maximize simplicity, fault isolation, and unit testability without introducing complex server-side join abstractions.
2. **Reuse of Phase 1 Observation Quality Architecture:**  
   Historical scenes reuse the exact Phase 1 quality gates: `COPERNICUS/S2_SR_HARMONIZED` linked with Cloud Score+ `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` (`cs_cdf >= 0.60`), coarse scene cloud $< 20\%$, and regional usable pixel coverage `min_usable_coverage >= 0.70` (70% unmasked pixels in the 100m `AnalysisRegion`).
3. **Temporal Recency Selection among Usable Scenes (Extension of Phase 1 Philosophy):**  
   Extending Phase 1's temporal selection principle ("prefer temporal recency among observations satisfying the quality gate"), qualifying historical observations that pass the $\ge 70\%$ usable coverage gate are sorted by acquisition date descending (`system:time_start` newest-first). The pipeline selects the **up to 3 most recent usable observations**.
4. **Role of Usable Coverage (Evidence vs. Ranking):**  
   `usable_coverage_percentage` functions strictly as a binary usability gate ($\ge 70\%$) and is preserved as empirical spatial evidence in metadata. It is **not** used to rank qualified observations, and no synthetic quality/recency scores or arbitrary weights are introduced.
5. **Bounded Selection (Up to 3 Usable Scenes):**  
   To prevent single-scene weather artifacts while keeping compute strictly bounded:
   - $\ge 3$ usable scenes $\rightarrow$ select 3 most recent usable scenes.
   - $2$ usable scenes $\rightarrow$ select 2.
   - $1$ usable scene $\rightarrow$ select 1 (accepted as a valid annual observation; overall multi-year sufficiency $N_{\text{annual}} \ge 2 \land Y \ge 2$ protects the baseline).
   - $0$ usable scenes $\rightarrow$ historical year is marked `no_data`.  
   *Zero scene duplication, zero synthetic interpolation, zero synthetic scene generation.*
6. **Compositing Strategy (Pixel-Wise Median of NDVI Images):**  
   Selected scenes are individually converted to masked NDVI rasters ($(\text{B8} - \text{B4}) / (\text{B8} + \text{B4})$), then composited via **pixel-wise median** in Earth Engine (`ee.ImageCollection.median()`). The resulting composite raster is subsequently reduced over the `AnalysisRegion`.
7. **Masked-Pixel Handling Invariant:**  
   Earth Engine's pixel-wise median operates exclusively over unmasked pixels at each spatial location. If a pixel is masked in 1 of 3 scenes, the median is taken across the remaining 2 valid pixels. If all scenes are masked at that pixel, the composite pixel remains masked. Masked pixels are strictly excluded from zonal reduction and **never replaced with artificial zeros** ($\text{NULL} \ne 0.0$).
8. **Clarification on `valid_pixel_count`:**  
   `valid_pixel_count` in the resulting regional statistics represents the number of spatial pixels contributing valid unmasked data to the zonal reduction. It does **not** indicate per-pixel observation depth (the number of times each pixel was observed). Per-pixel observation depth rasters are deferred for the MVP.

---

## 2. Problem Definition & Architectural Requirements

### 2.1 The Core Phase 2C Challenge
Phase 2A established Option C (Annual Matched-Window Regional Observations) as the statistical foundation for multi-year comparison, and Phase 2B defined the exact calendar-date-anchored window $[S_{Y_h}, E_{Y_h}]$ (31 days inclusive) for each historical year $Y_h \in \{Y-1, Y-2, Y-3\}$.

Phase 2C must answer:
> **"How do we query, filter, qualify, select, and combine historical Sentinel-2 satellite scenes within each historical year's 31-day window to produce exactly one representative regional NDVI value per represented year?"**

### 2.2 System Design Invariants
1. **Determinism:** Given an identical spatial region and reference date, historical collection queries and composites must return bit-exact results.
2. **Quality Parity:** Historical scenes must satisfy the exact radiometric and clear-sky quality standards enforced on current observations in Phase 1.
3. **No Synthetic Artifacts:** Never interpolate missing pixels, duplicate scenes to reach arbitrary counts, or invent baseline data.
4. **Resource Bounds:** Execution graph must remain lightweight and predictable, designed to minimize client-side materialization calls.
5. **Cross-Year Ownership Invariant (`DEC-015`):** When a 31-day window crosses January 1, all acquisitions within that window belong entirely to the target historical anchor year $Y_h$.

---

## 3. Part A — Historical Collection Construction Architecture

We evaluate four architectural approaches for ingesting and processing historical satellite imagery across the 3 target historical years ($Y-1, Y-2, Y-3$):

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ APPROACH 1: Independent Yearly Pipelines (RECOMMENDED FOR MVP)                          │
│                                                                                         │
│   Year Y-1 Window ──> get_sentinel2_collection ──> Select <=3 Newest ──> Composite      │
│   Year Y-2 Window ──> get_sentinel2_collection ──> Select <=3 Newest ──> Composite      │
│   Year Y-3 Window ──> get_sentinel2_collection ──> Select <=3 Newest ──> Composite      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ APPROACH 2: Server-Side ee.Join by Year                                                 │
│   Single multi-year query joined to a feature collection of historical year definitions │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ APPROACH 3: ee.ImageCollection.map() over Year List                                     │
│   Server-side iteration using ee.List.map() evaluating inner collections                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ APPROACH 4: Compound Multi-Window Disjoint Filter (ee.Filter.Or)                        │
│   Single collection filtered by Or(date_1, date_2, date_3) and partitioned by year      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Detailed Evaluation of Alternatives

#### Approach 1: Independent Annual Sub-Pipelines (RECOMMENDED)
- **Mechanism:** Execute collection discovery, quality filtering, recency sorting, and compositing independently for each target historical year $Y_h$ using its discrete Phase 2B date range $[S_h, E_h]$.
- **Pros:**
  - *Simplicity:* Direct reuse of Phase 1 functions (`get_sentinel2_collection`, `mask_observation_quality`, `calculate_ndvi`, `calculate_ndvi_statistics`).
  - *Fault Isolation:* An Earth Engine anomaly or missing data in year $Y-3$ does not fail or corrupt processing for years $Y-1$ and $Y-2$.
  - *Testability:* 100% unit-testable per year with clean Python fixtures and mockable response envelopes.
  - *Zero Complex Server-Side Graphing:* Avoids nested `ee.Algorithms.If` and complex Earth Engine server-side collection grouping.
- **Cons & Trade-offs:**
  - For large scale ($K=10$ or $K=20$ years), generalized join/map architectures may be more concise. However, for the bounded $K=3$ MVP horizon, independent processing avoids unnecessary abstraction complexity.

#### Approach 2: Server-Side `ee.Join` Architecture
- **Mechanism:** Query a 3-year contiguous collection, attach a `year` property, and execute an `ee.Join.saveAll` against a feature collection of target years.
- **Evaluation:** Highly complex server-side construct. Cross-year windows (e.g. Dec 21 to Jan 20) break simple `year` property joining because scenes have acquisition timestamps across two different calendar years, requiring artificial seasonal key properties. Unnecessary for a 3-year MVP.

#### Approach 3: `ee.List.map()` Server-Side Iteration
- **Mechanism:** Pass a server-side list of date ranges `ee.List([[s1, e1], [s2, e2], [s3, e3]])` into a mapped server function returning an `ee.ImageCollection` of composite images.
- **Evaluation:** Inner collection operations inside `ee.List.map()` require complex type casting (`ee.Image(ee.ImageCollection(...).median())`) and make error inspection more difficult in client debugging.

#### Approach 4: Compound Disjoint Filter (`ee.Filter.Or`)
- **Mechanism:** Apply `ee.Filter.Or(ee.Filter.date(s1, e1), ee.Filter.date(s2, e2), ee.Filter.date(s3, e3))` to a single collection, then group by year.
- **Evaluation:** Grouping an `ImageCollection` into sub-collections server-side still requires mapping over years and re-filtering, adding graph overhead without simplifying logic.

### 3.2 Part A Decision: Adopt Approach 1 (Independent Annual Pipelines)
For the bounded 3-year historical horizon ($K=3$), **Approach 1** delivers high operational reliability, complete fault isolation, zero server-side graph obfuscation, and seamless compliance with the Phase 2B cross-calendar-year ownership invariant.

---

## 4. Historical Observation Quality Gates & Threshold Reuse

### 4.1 Policy Alignment with Phase 1
To ensure scientific consistency between the current observation and historical baselines, historical scenes must adhere to the **identical quality policy** locked in Phase 1 (`DEC-010`):

| Quality Parameter | Phase 1 Standard | Phase 2C Historical Standard | Architectural Rationale |
|---|---|---|---|
| **Satellite Collection** | `COPERNICUS/S2_SR_HARMONIZED` | `COPERNICUS/S2_SR_HARMONIZED` | Identical sensor calibration and surface reflectance processing. |
| **Quality Model** | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | Identical clear-sky machine learning quality assessment. |
| **Clear-Sky Threshold** | `clear_threshold = 0.60` (`cs_cdf >= 0.60`) | `clear_threshold = 0.60` (`cs_cdf >= 0.60`) | Consistent pixel-level cloud/shadow masking. Sub-threshold pixels masked. |
| **Scene Cloud Pre-Filter** | `CLOUDY_PIXEL_PERCENTAGE < 20.0%` | `CLOUDY_PIXEL_PERCENTAGE < 20.0%` | Rejects heavily overcast catalog scenes before regional extraction. |
| **Regional Usable Coverage** | `min_usable_coverage = 0.70` (70%) | `min_usable_coverage = 0.70` (70%) | Guarantees that every candidate scene has $\ge 70\%$ clear pixels inside the parcel buffer. |
| **Mask Preservation** | Masked pixels remain null | Masked pixels remain null | Masked pixels are never converted to $0.0$; excluded from reductions. |

### 4.2 Rejection of Relaxed or Divergent Historical Thresholds
- *Considered Alternative:* Lowering `min_usable_coverage` to $0.50$ for historical scenes to increase data density.
- *Rejection Reason:* Relaxing quality standards for historical scenes would introduce cloudy/shadowed pixels into the baseline, artificially depressing historical NDVI values and causing false-positive positive anomalies today. Quality criteria must remain strictly uniform across time.

---

## 5. Historical Observation Selection Strategy

### 5.1 Quality Gate vs. Temporal Selection
Phase 2C establishes an explicit architectural distinction between qualifying an observation and selecting among qualified observations:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. QUALITY GATE (Binary Usability Qualification):                                       │
│    "Is this observation usable?"                                                        │
│    - Cloud Score+ cs_cdf >= 0.60 pixel masking applied.                                  │
│    - Scene CLOUDY_PIXEL_PERCENTAGE < 20.0%.                                             │
│    - AnalysisRegion USABLE_COVERAGE >= 0.70 (70% unmasked pixel survival).              │
│    -> Observations meeting all 3 criteria are designated USABLE.                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. TEMPORAL SELECTION (Temporal Sampling within Seasonal Window):                       │
│    "Among usable observations, which observations represent the seasonal window?"       │
│    - Sort usable observations by acquisition timestamp descending (newest → oldest).     │
│    - Select the UP TO 3 most recent usable observations.                                │
│    - usable_coverage_percentage is NOT used to re-rank qualified observations.           │
│    - No synthetic scores, arbitrary weights, or ranking formulas are introduced.        │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Explicit Connection to Phase 1 Temporal Philosophy
This selection strategy deliberately extends the Phase 1 temporal philosophy to multi-scene historical baseline construction:

- **Phase 1 (Instantaneous Observation):** Selects the single **most recent usable observation** ($N=1$) within the lookback window.
- **Phase 2C (Seasonal Window Baseline):** Selects the **up to 3 most recent usable observations** ($N \le 3$) within that historical year's 31-day seasonal window.

The underlying operational principle remains identical:
> **"Prefer temporal recency among observations that satisfy the quality/usability gate."**

### 5.3 Nature of the MVP Sampling Strategy
- Selecting the most recent up to 3 usable observations is a **deterministic, bounded, and explainable MVP temporal sampling strategy**.
- It does **not** claim that more recent observations within a 31-day window are universally more scientifically representative of peak crop vigor, nor that 3 observations is a universally optimal sample size.
- It provides a clean, predictable mechanism that avoids arbitrary weighting formulas while ensuring historical observations meet high radiometric standards.

---

## 6. Historical Observation Selection Semantics ($N \in \{0, 1, 2, 3, >3\}$)

Within each historical year's 31-day window, candidate scenes passing Cloud Score+ quality gates ($\ge 70\%$ usable coverage) are sorted newest-first and selected up to a **strict maximum of 3 observations**:

```text
Usable Scenes Discovered (N)
           │
     ┌─────┴──────────────────────────────┐
     │                                    │
   N >= 3                               N = 2, 1, 0
     │                                    │
Select 3 Newest                     Select All N
(Sorted by Date Descending)               │
     │                                    ├─ N = 2: Composite across 2 scenes
     │                                    ├─ N = 1: Single scene (identity composite)
     │                                    └─ N = 0: Year marked status="no_data"
     ▼                                    ▼
Pixel-Wise Median Composite          Historical Year Payload (with N_selected evidence)
```

### 6.1 Behavior Matrix by Observation Count

| Usable Count ($N$) | Action | Selected Count ($N_{\text{selected}}$) | Compositing Operation | Historical Year Status |
|---|---|---|---|---|
| **$N \ge 3$** | Sort newest $\to$ oldest, select 3 newest | 3 | Pixel-wise median of 3 NDVI rasters | `success` |
| **$N = 2$** | Select both scenes | 2 | Pixel-wise median of 2 NDVI rasters (mean of 2 unmasked pixels) | `success` |
| **$N = 1$** | Select single available scene | 1 | Single NDVI raster (identity / no median reduction needed) | `success` |
| **$N = 0$** | No scenes met quality threshold | 0 | None | `no_data` |

### 6.2 Acceptance of $N=1$ as a Valid Annual Representation
- **Architectural Question:** Should a historical year with only 1 usable scene be rejected as `insufficient`?
- **Analysis:** In Indian agriculture, prolonged monsoon cloud cover (July–August) frequently leaves only 1 clear Sentinel-2 overpass in a 30-day window. Rejecting a valid, quality-verified ($> 70\%$ clear) observation would cause catastrophic data loss in Kharif season advisory.
- **Safety Invariant:** A year with $N=1$ produces a valid annual observation, but the overall multi-year baseline remains strictly protected by Phase 2A's sufficiency guardrail:
  $$N_{\text{annual}} \ge 2 \quad \text{AND} \quad Y \ge 2$$
  The multi-year baseline is computed only if at least 2 distinct historical years provide valid data.

---

## 7. How to Combine Selected Images — Compositing Evaluation

To produce **ONE** representative regional NDVI value for target year $Y_h$, how should the $N_{\text{selected}}$ observations ($1 \le N \le 3$) be mathematically combined?

### 7.1 Comprehensive Comparison of 6 Aggregation Approaches

```
Approach A: Single Image Selection
[Img 1, Img 2, Img 3] ──> Pick Newest ──> NDVI ──> Regional Zonal Stats

Approach B: Scalar Mean of Regional Means
Img 1 ──> NDVI ──> Stats 1 (mean_1) ──┐
Img 2 ──> NDVI ──> Stats 2 (mean_2) ──┼──> Mean(mean_1, mean_2, mean_3)
Img 3 ──> NDVI ──> Stats 3 (mean_3) ──┘

Approach C: Scalar Median of Regional Means
Img 1 ──> NDVI ──> Stats 1 (mean_1) ──┐
Img 2 ──> NDVI ──> Stats 2 (mean_2) ──┼──> Median(mean_1, mean_2, mean_3)
Img 3 ──> NDVI ──> Stats 3 (mean_3) ──┘

Approach D: Pixel-Wise Mean of NDVI Images
[Img 1, Img 2, Img 3] ──> [NDVI_1, NDVI_2, NDVI_3] ──> pixel_mean() ──> Regional Zonal Stats

Approach E: Pixel-Wise Median of NDVI Images (RECOMMENDED)
[Img 1, Img 2, Img 3] ──> [NDVI_1, NDVI_2, NDVI_3] ──> pixel_median() ──> Regional Zonal Stats

Approach F: Reflectance-First Median Composite
[Img 1, Img 2, Img 3] ──> pixel_median(B4), pixel_median(B8) ──> compute_ndvi() ──> Regional Zonal Stats
```

### 7.2 Technical & Mathematical Invariants

#### Invariant 1: Scalar Median of Means $\ne$ Mean of Spatial Median
$$\text{median}(\text{reduce}(I_1), \text{reduce}(I_2), \text{reduce}(I_3)) \ne \text{reduce}(\text{median}(I_1, I_2, I_3))$$
- *Explanation in Simple Terms:* If Image 1 has high NDVI on the left half of a farm and low on the right, and Image 2 has the reverse, averaging their scalar summaries collapses intra-parcel spatial structure. Combining pixels first preserves the true spatial distribution across the parcel before computing summary statistics.

#### Invariant 2: Median of NDVI $\ne$ NDVI of Median Reflectance
$$\text{median}\left(\frac{B8_i - B4_i}{B8_i + B4_i}\right) \ne \frac{\text{median}(B8_i) - \text{median}(B4_i)}{\text{median}(B8_i) + \text{median}(B4_i)}$$
- *Explanation in Simple Terms:* NDVI is a non-linear ratio. Because the median of a non-linear function is not equal to the function of medians, compositing raw surface reflectance bands across different days can pair a wet-soil Red band from Day 1 with a dry-canopy NIR band from Day 2, producing synthetic spectral ratios that never existed in nature. Computing NDVI per-scene first preserves radiometric integrity.

### 7.3 Detailed Trade-Off Matrix

| Evaluation Dimension | Approach A (Single Image) | Approach B (Scalar Mean) | Approach C (Scalar Median) | Approach D (Pixel Mean) | Approach E (Pixel Median — RECOMMENDED) | Approach F (Reflectance Composite) |
|---|---|---|---|---|---|---|
| **Outlier Resilience** | None (1 outlier corrupts) | Low (mean sensitive to artifact) | Moderate (scalar only) | Low (mean pulled by cloud leak) | **High (rejects single-pixel artifacts)** | High (reflectance level) |
| **Spatial Structure** | Preserved | Lost before reduction | Lost before reduction | Preserved | **Fully Preserved** | Preserved |
| **Radiometric Integrity** | High | High | High | High | **High (per-scene band ratio preserved)** | Low (mixes multi-date bands) |
| **Masked Pixel Handling** | N/A | Complex (weights vary) | Complex | Weighted sum | **Native in Earth Engine** | Native in Earth Engine |
| **Phase 1 Parity** | High | Moderate | Moderate | High | **Direct (same NDVI definition)** | Divergent |
| **Implementation Complexity** | Minimal | Moderate | Moderate | Low | **Low (native `ee.ImageCollection.median`)** | Moderate |

### 7.4 Selected Compositing Method: Approach E (Pixel-Wise Median NDVI)
1. For each selected image $i \in [1..N]$, compute masked NDVI raster: $\text{NDVI}_i = \text{calculate\_ndvi}(\text{masked\_image}_i)$.
2. Stack into an `ee.ImageCollection([NDVI_1, ...])`.
3. Compute spatial median raster: $\text{Composite\_NDVI} = \text{collection.median}()$.
4. Execute regional zonal reduction (`calculate_ndvi_statistics`) over `Composite_NDVI`.

---

## 8. Masked-Pixel Behavior in Earth Engine Composites

A critical design requirement is verifying how Earth Engine treats masked (cloudy/shadowed) pixels during pixel-wise median compositing and subsequent zonal reduction.

### 8.1 Pixel Stack Compositing Mechanics

Consider 3 selected historical scenes over a 4-pixel parcel:

```
Spatial Location       Image 1 (NDVI)       Image 2 (NDVI)       Image 3 (NDVI)       ee.ImageCollection.median()
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Pixel A (Fully Clear)     0.65                 0.70                 0.75              median(0.65, 0.70, 0.75) = 0.70
Pixel B (1 Masked)        0.60                MASKED                0.64              median(0.60, 0.64) = 0.62
Pixel C (2 Masked)       MASKED               MASKED                0.58              median(0.58) = 0.58
Pixel D (All Masked)     MASKED               MASKED               MASKED             MASKED (Null / No Value)
```

### 8.2 Earth Engine Mask Invariants
1. **Unmasked Evaluation:** Earth Engine's `collection.median()` computes the median **only across valid, unmasked pixels** at each coordinate.
2. **Partial Pixel Survival:** If a pixel is valid in at least 1 image, it receives a valid composite NDVI value.
3. **Total Cloud Coverage:** If a pixel is masked in all selected images, it remains masked (null) in the composite raster.
4. **Zonal Reduction Protection:** During `calculate_ndvi_statistics`, `ee.Reducer.mean()` automatically skips masked pixels. The valid pixel count is captured in `NdviRegionalStatistics.valid_pixel_count`.
5. **Zero Replacement Prohibition:** Masked pixels are **never unmasked or filled with $0.0$**, eliminating artificial baseline skew.

### 8.3 Clarification on `valid_pixel_count` vs. Observation Depth
- `valid_pixel_count` on the final composite represents the **count of spatial pixels in the `AnalysisRegion` contributing valid unmasked data to the zonal reduction**.
- It does **not** mean "each pixel was observed $N$ times."
- Generating a per-pixel observation contribution depth raster is intentionally deferred for the MVP to keep the zonal reduction graph lightweight.

---

## 9. Historical Evidence Fields & Output Contracts

### 9.1 Evidence-First Architectural Principle
The historical pipeline exposes transparent empirical evidence regarding the data density and provenance of each annual observation, rather than fabricating synthetic confidence scores.

### 9.2 Proposed Annual Historical Observation Schema
```python
from datetime import date
from pydantic import BaseModel, Field
from app.satellite.types import NdviRegionalStatistics, Sentinel2ImageMetadata

class HistoricalObservationSummary(BaseModel):
    """Provenance metadata for a single qualifying historical satellite scene."""
    image_id: str
    acquisition_date: str
    usable_coverage_percentage: float = Field(ge=0.0, le=100.0)
    cloud_percentage: float = Field(ge=0.0, le=100.0)
    system_time_start: int


class AnnualHistoricalNdviObservation(BaseModel):
    """Representative seasonal-window NDVI observation for a single historical year."""
    target_year: int = Field(description="The authoritative historical anchor year")
    anchor_date: str = Field(description="Seasonal anchor date YYYY-MM-DD")
    window_start_date: str = Field(description="Inclusive search window start date YYYY-MM-DD")
    window_end_date: str = Field(description="Inclusive search window end date YYYY-MM-DD")
    
    # Observation Evidence (DEC-014 / DEC-016)
    available_usable_scenes_count: int = Field(ge=0, description="Total scenes in window meeting quality threshold")
    selected_scenes_count: int = Field(ge=0, le=3, description="Number of scenes selected for composite (0 to 3)")
    selected_scenes: list[HistoricalObservationSummary] = Field(default_factory=list)
    
    # Compositing & Statistics
    composite_method: str = Field(default="pixel_median", description="Compositing strategy applied")
    statistics: NdviRegionalStatistics | None = Field(default=None, description="Regional zonal stats over composite")
    status: str = Field(description="Status of this annual observation: success | no_data | error")
```

---

## 10. Historical Year Semantics & Target-Year Ownership

### 10.1 Definition of "Annual Historical Value"
In BharatSahayak V2, the term **"2023 Historical Value"** does NOT denote a 365-day annual average. It formally denotes:
> **"The representative regional NDVI value derived from the 31-day seasonal matching window centered on the reference calendar anchor in historical target year 2023."**

### 10.2 Strict Adherence to Cross-Year Ownership (`DEC-015`)
When the reference date is near January 1 (e.g. January 5, 2026), the historical search window for target year $Y_h = 2025$ spans:
$$\text{Start Date: } \text{2024-12-21} \quad \longrightarrow \quad \text{End Date: } \text{2025-01-20}$$
- All satellite acquisitions in this continuous 31-day window belong strictly to the **2025 annual historical observation**.
- Scenes acquired in late December 2024 are NOT split into 2024. They serve as the head of the 2025 seasonal window.

---

## 11. Spatial, Geometric & NDVI Calculation Contracts

Phase 2C strictly preserves the spatial and mathematical definitions established in Phase 1:

1. **Spatial Footprint (`DEC-007`):**  
   `AnalysisRegion` constructed via `create_analysis_region(latitude, longitude, radius_m=100.0)` generating a 100m circular `PointBuffer`.
2. **Spatial Reduction Scale (`DEC-007`):**  
   Zonal reductions executed at `scale = 10.0` meters (native Sentinel-2 spatial resolution).
3. **NDVI Band Mathematics (`DEC-009`):**  
   $$\text{NDVI} = \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4}}$$
   Executed via Earth Engine native `image.normalizedDifference(['B8', 'B4']).rename('NDVI')`.
4. **Scope Boundaries:**  
   Zero alternative indices (EVI, SAVI, NDWI), zero dynamic land cover masks, and zero crop health classification thresholds.

---

## 12. Earth Engine Execution Graph & Materialization Constraints

### 12.1 Execution Graph Design
For each target historical year $Y_h \in \{Y-1, Y-2, Y-3\}$:

```text
[ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")]
       │
       ├─ filterBounds(region)
       ├─ filterDate(start_str, ee_end_str)
       ├─ filter(CLOUDY_PIXEL_PERCENTAGE < 20)
       ├─ linkCollection(CloudScore+, ["cs_cdf"])
       ├─ map(_score_usable_coverage)
       ├─ filter(USABLE_COVERAGE >= 0.70)
       │
[Qualified Sub-Collection]
       │
       ├─ sort("system:time_start", False)  (newest first)
       ├─ limit(3)                          (select up to 3)
       │
[Selected <= 3 Images]
       │
       ├─ map(mask_observation_quality)
       ├─ map(calculate_ndvi)
       │
[NDVI ImageCollection (<= 3 Images)]
       │
       ├─ .median()
       │
[Composite NDVI Image (ee.Image)]
       │
       └─ reduceRegion(combined_reducer, region, scale=10)
```

### 12.2 Materialization Design Constraints
- The implementation should minimize client-side materialization calls (`.getInfo()`).
- The materialization budget of **maximum 3 client-side `.getInfo()` calls** established in Phase 2A serves as an architectural design constraint to prevent round-trip overhead.
- Exact performance numbers and EECU consumption will be measured and validated during integration testing rather than asserted beforehand.

---

## 13. Result States & Error Handling Semantics

To ensure full transparency without swallowing failures:

### 13.1 Individual Historical Year States
- **`success`:** $\ge 1$ usable scene qualified, median composite generated, and zonal reduction succeeded with `valid_pixel_count > 0`.
- **`no_data`:** 0 qualifying scenes in the 31-day window, or zonal reduction returned 0 valid pixels due to total parcel cloudiness.
- **`error`:** Earth Engine API exception, network timeout, or invariant violation during year processing.

### 13.2 Multi-Year Historical Baseline Impact (Phase 2D Preview)
- An individual year returning `no_data` does not fail the overall pipeline.
- If at least 2 distinct historical years return `success` ($N_{\text{annual}} \ge 2 \land Y \ge 2$), the multi-year baseline status is **`success`**.
- If fewer than 2 historical years succeed, the overall historical status becomes **`insufficient_history`** (withholding anomaly calculations while returning Phase 1 current observation).
- If an Earth Engine system failure occurs, the status becomes **`error`** with structured error details.

---

## 14. Comprehensive Edge-Case Testing Strategy

The Phase 2C test suite must validate the following 19 conceptual test categories:

| Test ID | Category | Scenario | Expected Behavior |
|---|---|---|---|
| **TC-C01** | Selection Count | Exactly 3 usable scenes in window | Selects all 3 scenes; builds 3-scene median composite. |
| **TC-C02** | Selection Count | Exactly 2 usable scenes in window | Selects both 2 scenes; builds 2-scene median composite. |
| **TC-C03** | Selection Count | Exactly 1 usable scene in window | Selects 1 scene; composite is single image; status `success`. |
| **TC-C04** | Selection Count | 0 usable scenes in window | Returns status `no_data`; `selected_scenes_count = 0`. |
| **TC-C05** | Selection Count | 6 usable scenes in window | Selects 3 newest usable scenes; excludes older 3. |
| **TC-C06** | Temporal Selection | 5 usable scenes with varying dates | Selects top 3 by `system:time_start` descending (newest-first). |
| **TC-C07** | Coverage Independence | Scene A (72% cov, newer) vs Scene B (95% cov, older) | Selects Scene A if among 3 newest (coverage is gate, not rank). |
| **TC-C08** | Masked Pixels | Pixel valid in 2 of 3 images | Median computed over 2 valid values; pixel is valid in composite. |
| **TC-C09** | Masked Pixels | Pixel valid in 1 of 3 images | Composite pixel takes value of the single unmasked observation. |
| **TC-C10** | Masked Pixels | Pixel masked in all 3 images | Composite pixel remains masked; excluded from mean reduction. |
| **TC-C11** | Total Masking | Entire parcel masked in all 3 images | Regional reduction returns `valid_pixel_count = 0` $\rightarrow$ `no_data`. |
| **TC-C12** | Year Crossing | Window spans Dec 21 to Jan 20 | All scenes assigned to target anchor year $Y_h$ (`DEC-015`). |
| **TC-C13** | Leap Year Handling | Window in leap year with Feb 29 anchor | Valid date span $[S_h, E_h]$ generated without Python errors. |
| **TC-C14** | Threshold Reuse | Candidate with 68% usable coverage | Rejected by `min_usable_coverage >= 0.70` gate. |
| **TC-C15** | NDVI Invariant | Composite pixel values | Strictly bounded in $[-1.0, 1.0]$. |
| **TC-C16** | Statistical Invariant | Zonal stats on composite | Validates $\text{min} - 10^{-6} \le \text{median/mean} \le \text{max} + 10^{-6}$. |
| **TC-C17** | Heterogeneous Years | $Y-1$ has 3 scenes, $Y-2$ has 1, $Y-3$ has 0 | $Y-1$ `success`, $Y-2$ `success`, $Y-3$ `no_data`. Multi-year has $N_{\text{annual}}=2 \rightarrow$ `success`. |
| **TC-C18** | Extreme Sparsity | $Y-1$ has 1 scene, $Y-2$ has 0, $Y-3$ has 0 | $Y-1$ `success`, $Y-2$ `no_data`, $Y-3$ `no_data`. Multi-year has $N_{\text{annual}}=1 \rightarrow$ `insufficient_history`. |
| **TC-C19** | Remote Exception | Earth Engine throws quota/runtime error | Encapsulated in `EarthEngineResult(status="error", error=...)`. |

---

## 15. Scientific Boundaries & Non-Goals

To maintain rigorous architectural discipline, Phase 2C explicitly enforces the following scientific boundaries:

- **What Phase 2C Produces:**  
  A bounded, quality-filtered, multi-scene pixel-wise median NDVI composite representing vegetative surface reflectance over an approximate 100m circular area during a specific historical 31-day seasonal window.
- **Scientific Sampling Boundaries:**
  - Selecting the most recent up to 3 usable scenes is an **MVP temporal sampling strategy**. It does not establish that recent observations are universally more representative or that 3 observations is a scientifically optimal sample size.
- **What Phase 2C Strictly Excludes:**
  - ❌ **No Crop Growth Stage Alignment:** Does not assume identical phenological growth stages across years (sowing dates fluctuate with monsoon arrival).
  - ❌ **No Disease or Health Diagnosis:** Does not classify NDVI values into "diseased", "stressed", or "healthy".
  - ❌ **No Yield Forecasting:** Does not extrapolate biomass to crop yield.
  - ❌ **No Weather / Soil Attribution:** Does not attribute spectral variations to rainfall deficits or soil nutrient deficiencies.

---

## 16. Sealed Phase 2C Decision (`DEC-016`)

```markdown
### DEC-016: Historical Satellite Collection Pipeline & Annual Pixel-Median Compositing

- **Status:** 🟢 APPROVED & SEALED
- **Date:** 2026-09-27
- **Context:** Phase 2A selected Option C (Annual Matched-Window Regional Observations) and Phase 2B formalized the 31-day seasonal window. We must define the historical collection querying, quality filtering, observation selection, and compositing mechanics to generate annual historical NDVI values.
- **Decision:**
  1. **Independent Annual Processing:** Evaluate each historical year (Y-1, Y-2, Y-3) independently within its Phase 2B 31-day window [S_h, E_h] using isolated collection queries.
  2. **Quality Gate Parity:** Enforce identical Phase 1 quality standards: Sentinel-2 Harmonized, Cloud Score+ (cs_cdf >= 0.60), scene cloud < 20%, and regional usable coverage >= 70%.
  3. **Temporal Recency Selection (Phase 1 Extension):** Among candidate scenes meeting the usability gate, sort by acquisition timestamp descending (`system:time_start` newest-first) and select the up to 3 most recent usable observations. Usable coverage acts as a qualification gate and evidence field, not a ranking score.
  4. **Bounded Selection (Up to 3 Scenes):** Select up to 3 usable scenes per year (3+ → 3, 2 → 2, 1 → 1, 0 → no_data). Accept N=1 as a valid annual observation while relying on multi-year sufficiency (N_annual >= 2, Y >= 2) to guard the baseline. Zero synthetic scene generation.
  5. **Pixel-Wise Median NDVI Compositing:** For selected scenes, compute masked NDVI rasters first, composite via pixel-wise median (`ee.ImageCollection.median()`), and execute regional zonal reduction over the composite.
  6. **Masked-Pixel Preservation:** Earth Engine's median reducer operates only over unmasked pixels. Never inject artificial zeros (NULL != 0.0). `valid_pixel_count` reflects unmasked spatial pixels contributing to the regional reduction.
- **Consequences:**
  - Robust, outlier-resistant annual historical NDVI baselines.
  - Full preservation of spatial parcel structure without multi-date reflectance mixing artifacts.
  - Bounded, predictable compute execution designed to minimize Earth Engine materialization overhead.
```

---
