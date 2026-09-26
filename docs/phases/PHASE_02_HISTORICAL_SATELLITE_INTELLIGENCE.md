# Phase 2 — Historical Satellite Intelligence

> **Canonical Record of Phase 2 Architecture, Design Decisions, Historical Baselines, and Anomaly Mathematics.**  
> *Status: 🟢 PHASE 2A & 2B COMPLETE & SEALED (Subphases 2A & 2B Approved; 2C Next / Pending)*<br>
> *Base Sealed Checkpoint: `60f8d90 — docs: finalize Phase 1 Earth Engine foundation documentation`*<br>
> *Next Step: Subphase 2C — Option C Historical Collection Pipeline*

---

## 1. Executive Summary

Phase 2 builds directly upon the verified, deterministic satellite foundation established in Phase 1 ([`app/satellite/`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite)). While Phase 1 delivers an instantaneous regional NDVI observation and empirical quality evidence (`RegionalNdviAnalysis`), an isolated instantaneous measurement cannot reveal whether vegetative vigor is typical, lagging, or unusually high for a given location.

Phase 2 extends the satellite foundation from an **instantaneous observation** to **historical comparative intelligence**:
$$\text{Current Regional NDVI} \quad \text{vs.} \quad \text{3-Year Seasonally Matched Historical Baseline} \quad \longrightarrow \quad \text{Empirical Anomaly Evidence}$$

### The Three-Tier Separation of Concerns
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. SATELLITE MEASUREMENT (Phase 1 — COMPLETE & SEALED)                                  │
│    - Instantaneous surface reflectance & band math: NDVI = (B8 - B4) / (B8 + B4).        │
│    - Regional zonal summary statistics (mean, median, min, max, valid_pixel_count).      │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. HISTORICAL COMPARISON & ANOMALY EVIDENCE (Phase 2 — CURRENT DESIGN)                  │
│    - Seasonally normalized 3-year historical baseline via Day-of-Year (DOY) matching.   │
│    - Option C: Annual matched-window regional observations [val_{Y-1}, val_{Y-2}, ...]. │
│    - Empirical statistical departures: Absolute Δ, Gated Relative %, Gated Z-Score.     │
│    - Explicit data sufficiency guardrails (N_annual >= 2, Y_distinct >= 2).             │
│    - STRICTLY EXCLUDES crop disease diagnoses, health claims, or fake confidence scores.│
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. AGRONOMIC & MULTI-AGENT REASONING (Phase 5 — FUTURE)                                 │
│    - Gemini 2.5 Flash agent reasoning graphs fusing weather, soil, and crop calendars.  │
│    - Translates empirical anomaly evidence into contextual, actionable farming advice.  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Boundary Invariant:** Phase 2 produces strictly **empirical satellite anomaly evidence** (e.g. *"Moderate Negative Spectral Departure"*), **NOT** agronomic diagnoses (e.g. *"Fungal blight infection"* or *"Drought stress"*). Agricultural interpretation requires external context (weather, soil, sowing dates) and remains deferred to Phase 4 and Phase 5.

---

## 2. Exact Phase 2 Problem Definition

### 2.1 The Core Scientific Question
Phase 2 answers:
> **"How does the current usable regional NDVI observation compare with an empirical historical baseline constructed from quality-verified observations at the exact same geographic location during the identical seasonal calendar window across preceding years?"**

### 2.2 Formal Domain Definitions

| Term | Technical Remote Sensing Definition | Non-Agronomic Boundary |
|---|---|---|
| **Current Observation** | The authoritative, Cloud Score+ masked Sentinel-2 observation selected via Phase 1 (`RegionalNdviAnalysis`) for the user's query window. | A physical optical measurement at timestamp $T_0$. |
| **Historical Observation** | A Sentinel-2 observation over the identical `AnalysisRegion` acquired during a prior year ($Y-1, Y-2, Y-3$) within a matched seasonal window. | Historical physical optical measurements. |
| **Matched Temporal Window** | A bounded calendar window centered on the Day of Year ($\text{DOY}$) of the current observation ($\text{Reference DOY} \pm 15\text{ days}$, 30-day total window) evaluated in prior years. | Enforces astronomical and seasonal comparability without assuming crop type. |
| **Annual Regional Value** | The representative regional mean NDVI derived from all qualifying scenes within a single historical year's 30-day DOY window. | The primary statistical unit of the historical baseline population. |
| **Historical Baseline** | The central tendency statistic (**Median NDVI**) computed across the historical population of annual regional values $[\text{val}_{Y-1}, \text{val}_{Y-2}, \text{val}_{Y-3}]$. | A reference distribution metric, **not** an optimal or target health value. |
| **Anomaly Evidence** | Mathematical departures between current observation and baseline ($\Delta\text{NDVI}$, gated percentage departure, gated standardized z-score). | Pure statistical departures, **never** labeled as crop stress or disease. |
| **Data Sufficiency** | Quantitative thresholding requiring at least 2 annual regional observations across at least 2 distinct historical years ($N_{\text{annual}} \ge 2 \land Y \ge 2$). | Explicit reliability and anti-hallucination guardrail. |

---

## 3. Historical Horizon Strategy (`DEC-012`)

- **Operational Standard for MVP:** Exactly **3 preceding calendar years** ($Y-1, Y-2, Y-3$ relative to current observation year $Y$).
- **Architectural Scope Notice:**
  > [!NOTE]
  > The 3-year historical horizon is an operational engineering choice for the MVP smallholder advisory. It balances data density, archive consistency, and compute budget on Earth Engine community quotas. It is **not** described as a universally optimal climatological baseline. Longer horizons (5–10 years) remain future work.
- **Archive Availability:** Sentinel-2 Level-2A Bottom-of-Atmosphere Harmonized Surface Reflectance (`COPERNICUS/S2_SR_HARMONIZED`) provides continuous, calibrated global coverage over India from early 2018 onwards. A 3-year rolling window is 100% available for any operational query from 2021 to present.

---

## 4. Temporal Normalization & Seasonality (`DEC-012`)

### 4.1 Why All-Year Baselines Fail in Agriculture
Indian agricultural vegetation follows sharp seasonal dynamics:
- **Kharif (Monsoon, June–Oct):** Rapid canopy emergence; peak NDVI $0.65 - 0.85$.
- **Rabi (Winter, Nov–April):** Irrigated wheat/mustard; peak NDVI $0.60 - 0.80$ in Jan–Feb.
- **Zaid (Summer, April–June):** Fallow stubble or dry bare soil; baseline NDVI $0.15 - 0.30$.

Comparing an August observation ($\text{NDVI} = 0.60$) against an *all-year annual mean* ($\text{NDVI} = 0.35$) produces a massive false-positive "anomaly" (+71%) that reflects natural seasonality rather than vegetative health.

### 4.2 Day-of-Year (DOY) Centered Windowing
- **Window Standard:** $\text{Reference DOY} \pm 15\text{ days}$ (30-day total matching envelope) evaluated across $Y-1, Y-2, Y-3$.
- **Astronomical & Calendar Normalization Boundary:**
  > [!IMPORTANT]
  > DOY matching ensures astronomical and seasonal calendar comparability. It does **NOT** guarantee an identical crop phenological stage (sowing dates shift based on monsoon arrival). Aligning crop-specific days-after-sowing (DAS) requires external farmer context and remains strictly within Phase 5 multi-agent reasoning.

---

## 5. Historical Observation Quality Strategy

Historical imagery must adhere strictly to the identical quality policy locked in Phase 1 (`DEC-010`):
1. **Dataset:** `COPERNICUS/S2_SR_HARMONIZED` (identical surface reflectance calibration).
2. **Quality Model:** Google Cloud Score+ `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` linked via `cs_cdf`.
3. **Clear-Sky Pixel Threshold:** `clear_threshold = 0.60` (`cs_cdf >= 0.60`). Sub-threshold pixels are masked via `image.updateMask()`.
4. **Coarse Catalog Pre-Filter:** `CLOUDY_PIXEL_PERCENTAGE < 20.0%` on scene metadata.
5. **Parcel-Level Usable Coverage:** `min_usable_coverage = 0.70` ($70\%$ unmasked pixels within `AnalysisRegion`).
6. **Mask Preservation:** Masked pixels remain null and are strictly excluded from reducers; they are **never converted to $\text{NDVI} = 0.0$**.

---

## 6. Historical Sampling Strategy — Option C (`DEC-013`)

Phase 2 explicitly standardizes on **Option C: Annual Matched-Window Regional Observations**.

### 6.1 Architectural Workflow
```text
Historical Sentinel-2 scenes
        ↓
Group by historical calendar year (Y-1, Y-2, Y-3)
        ↓
Apply Phase 1 quality policy (Cloud Score+ cs_cdf >= 0.60, min coverage >= 70%, scene cloud < 20%)
        ↓
Within each historical year:
    Process all qualifying scenes in that year's DOY ±15-day matched window
        ↓
Produce ONE annual matched-window regional NDVI observation per represented historical year
        ↓
Historical annual observations:
    Y-1 → one regional value
    Y-2 → one regional value
    Y-3 → one regional value
        ↓
Construct historical distribution [val_{Y-1}, val_{Y-2}, val_{Y-3}]
        ↓
Compute Median / Mean / Standard Deviation across annual regional values
```

### 6.2 Definition of Observation Units
To prevent conflating raw satellite scenes with independent statistical samples:
- **Sentinel-2 Source Scene:** Raw satellite granule in the Earth Engine archive.
- **Qualifying Historical Scene:** Individual scene passing Cloud Score+ quality and parcel coverage gates.
- **Annual Matched-Window Regional Observation:** The representative regional mean NDVI value computed for a specific historical year's 30-day window.
- **Primary Statistical Population Unit:** **ONE annual matched-window regional NDVI value per represented historical year**.
- **Historical Population ($P_{\text{hist}}$):** The array of annual regional values, e.g. $[\text{val}_{2023}, \text{val}_{2024}, \text{val}_{2025}]$.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ WHY OPTION C WAS SELECTED OVER ALTERNATIVES:                                            │
│ - Option A (Single Anniversary Scene per Year): REJECTED. High vulnerability to a       │
│   single-day weather artifact (e.g. soil wetting on that exact date).                   │
│ - Option B (Pooled Multi-Scene Collection): REJECTED. Sentinel-2's 5-day revisit means  │
│   consecutive scenes within the same month are highly autocorrelated. Pooling treats   │
│   4 scenes from one year as 4 independent data points, biasing the multi-year baseline. │
│ - Option C (Annual Regional Values): CHOSEN. Aggregates intra-annual passes into a     │
│   single robust yearly representation, treating each past agricultural season as ONE   │
│   independent sample in the multi-year distribution.                                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Historical Baseline & Anomaly Mathematics (`DEC-013`)

### 7.1 Historical Baseline Statistic
- **Primary Baseline Metric:** **Historical Median NDVI** ($\text{median}(P_{\text{hist}})$).
- **Secondary Dispersion Metrics:** **Mean NDVI** ($\mu_{\text{annual}}$) and **Standard Deviation** ($\sigma_{\text{annual}}$) across the annual regional values.

### 7.2 Anomaly Metrics Suite
1. **Absolute NDVI Departure (Primary Metric):**
   $$\Delta\text{NDVI} = \text{current\_regional\_mean\_ndvi} - \text{historical\_annual\_median\_ndvi}$$
   - *Properties:* Robust, linear, never divides by zero, directly interpretable in spectral units.
2. **Gated Relative / Percentage Departure:**
   $$\text{Percentage Departure} = \left(\frac{\text{current\_regional\_mean\_ndvi} - \text{historical\_annual\_median\_ndvi}}{\text{historical\_annual\_median\_ndvi}}\right) \times 100$$
   - *Safety Gate:* Evaluated **ONLY** when $\text{historical\_annual\_median\_ndvi} \ge 0.15$. Returns `None` over fallow/bare ground to prevent near-zero division explosion.
3. **Gated Standardized Anomaly (Z-Score):**
   $$Z\text{-Score} = \frac{\text{current\_regional\_mean\_ndvi} - \mu_{\text{annual}}}{\sigma_{\text{annual}}}$$
   - *Safety Gate:* Evaluated **ONLY** when $N_{\text{annual}} \ge 2$, $Y \ge 2$, and $\sigma_{\text{annual}} \ge 0.02$. Returns `None` when historical variance is negligible.

### 7.3 MVP Empirical Spectral-Departure Bands
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                      MVP EMPIRICAL SPECTRAL-DEPARTURE BANDS                             │
├───────────────────────────────┬─────────────────────────────────────────────────────────┤
│ Absolute Departure (Δ NDVI)   │ Empirical Spectral Classification                       │
├───────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Δ_NDVI >= +0.15               │ Strong Positive Spectral Departure                      │
│ +0.05 <= Δ_NDVI < +0.15       │ Moderate Positive Spectral Departure                    │
│ -0.05 < Δ_NDVI < +0.05        │ Near-Baseline Spectral Alignment                        │
│ -0.15 < Δ_NDVI <= -0.05       │ Moderate Negative Spectral Departure                    │
│ Δ_NDVI <= -0.15               │ Strong Negative Spectral Departure                      │
└───────────────────────────────┴─────────────────────────────────────────────────────────┘
```
> [!CAUTION]
> These bands are **empirical mathematical classifications** of optical reflectance departure. They must **NEVER** be presented as crop health diagnoses (e.g. "Severe Crop Stress" or "Pest Damage").

---

## 8. Data Sufficiency & Result States (`DEC-014`)

### 8.1 Sufficiency Rules
A historical baseline is scientifically valid if and only if:
$$N_{\text{annual}} \ge 2 \quad \text{AND} \quad Y \ge 2$$
- $N_{\text{annual}}$: Count of annual regional observations represented.
- $Y$: Count of distinct historical calendar years represented.

If $N_{\text{annual}} < 2$ or $Y < 2$, the result is classified as `insufficient_history`. The current Phase 1 observation is returned, but baseline and anomaly metrics are withheld.

### 8.2 Universal Result-State Semantics

| Result Status | Meaning | Current Observation | Historical Baseline | Anomaly Evidence |
|---|---|---|---|---|
| `"success"` | Valid current observation AND sufficient historical data ($N_{\text{annual}} \ge 2 \land Y \ge 2$). | `RegionalNdviAnalysis` | `HistoricalNdviBaseline` | `NdviAnomalyEvidence` |
| `"insufficient_history"` | Valid current observation, BUT historical data is sparse ($N_{\text{annual}} < 2$ or $Y < 2$). | `RegionalNdviAnalysis` | `None` / Partial | `None` |
| `"no_data"` | No usable current Phase 1 observation found in query lookback window. | `None` | `None` | `None` |
| `"error"` | Remote Earth Engine exception, runtime error, or invariant violation. | `None` | `None` | `None` (Returns `EarthEngineError`) |

---

## 9. Uncertainty & Evidence Strategy

### 9.1 Explicit Rejection of Synthetic Confidence Scores
> [!CAUTION]
> Phase 2 **explicitly rejects** fabricating scalar confidence numbers (e.g. `confidence: 0.88`). Such heuristics mislead users and LLMs with fake precision.

### 9.2 Transparent Multi-Dimensional Evidence Contract
Instead, Phase 2 exposes transparent empirical evidence:
- `historical_annual_observation_count: int` ($N_{\text{annual}}$)
- `distinct_years_count: int` ($Y$)
- `raw_qualifying_scenes_count: int` (Provenance only)
- `temporal_matching_window_days: int` (30 days)
- `historical_std_dev: float | None` ($\sigma_{\text{annual}}$)
- `is_sufficient: bool`

---

## 10. Earth Engine Materialization & Quota Design

### 10.1 Materialization Budget (Design Target)
- **Target:** A maximum of **3 explicit client-side materialization calls** (`.getInfo()`) is established as an engineering design target to limit client/server round trips and control latency.
- **Latency Notice:** Latency expectations are architectural design targets, **not** benchmarked results. Actual timings will be established during Phase 2I testing.

### 10.2 Quota & Cost Safeguards (Non-Commercial Tier)
- **Bounded Scope:** Bounded to 3 preceding years, DOY $\pm 15$ days, 100m `AnalysisRegion`.
- **Spatial Clipping:** All rasters clipped to 100m circular buffer prior to reduction.
- **Server-Side Grouping:** Multi-temporal filtering and annual reductions execute server-side.

---

## 11. Proposed Typed Domain Output Contract (`DEC-014`)

```text
EarthEngineResult
 └── data: HistoricalNdviAnalysis
      ├── current: RegionalNdviAnalysis (Preserved Phase 1 Root Contract)
      │    ├── observation: Sentinel2ImageMetadata
      │    ├── quality: ObservationQualityEvidence
      │    ├── freshness: ObservationFreshness
      │    ├── region: AnalysisRegionMetadata
      │    ├── statistics: NdviRegionalStatistics
      │    └── pipeline_version: "1.0.0"
      ├── baseline: HistoricalNdviBaseline
      │    ├── median: float
      │    ├── mean: float | None
      │    ├── std_dev: float | None
      │    ├── min: float | None
      │    ├── max: float | None
      │    └── valid_pixel_count: int | None
      ├── temporal_matching: HistoricalTemporalWindow
      │    ├── reference_doy: int
      │    ├── window_days: int
      │    ├── years_evaluated: list[int]
      │    ├── start_doy: int
      │    └── end_doy: int
      ├── sufficiency: HistoricalSufficiencyEvidence
      │    ├── historical_annual_observation_count: int
      │    ├── distinct_years_count: int
      │    ├── raw_qualifying_scenes_count: int
      │    ├── is_sufficient: bool
      │    └── sufficiency_notes: str | None
      ├── anomaly: NdviAnomalyEvidence
      │    ├── absolute_departure: float
      │    ├── percentage_departure: float | None
      │    ├── z_score: float | None
      │    ├── spectral_departure_class: str
      │    └── is_anomalous: bool
      └── pipeline_version: str = "2.0.0"
```

---

## 12. Phase 1 Compatibility Guarantee

- ✅ **Unaltered Phase 1 Models:** `RegionalNdviAnalysis`, `Sentinel2ImageMetadata`, `ObservationQualityEvidence`, `ObservationFreshness`, `AnalysisRegionMetadata`, `NdviRegionalStatistics`, and `EarthEngineResult` remain 100% backward-compatible.
- ✅ **Unaltered Phase 1 Functions:** `create_analysis_region`, `calculate_ndvi`, `calculate_ndvi_statistics`, `get_sentinel2_collection`, `mask_observation_quality`, and `analyze_regional_ndvi` remain unmodified.
- ✅ **Independent Pipeline:** Phase 2 introduces `analyze_historical_ndvi(...)` as a higher-order orchestrator composing Phase 1 outputs.

---

## 13. Phase 2 Subphase Roadmap

```
Phase 2: Historical Satellite Intelligence
├── 2A: Architecture & Design Review (🟢 COMPLETE / APPROVED / DEC-012, DEC-013, DEC-014)
├── 2B: Temporal Window & Seasonality Strategy (🟢 COMPLETE / APPROVED / DEC-015)
├── 2C: Option C Historical Collection Pipeline (🟡 NEXT / PENDING)
├── 2D: Multi-Year Baseline Computation Engine (🟡 PLANNED)
├── 2E: Anomaly Mathematics & Departure Verification
├── 2F: Data Sufficiency & Sparse History Handlers (DEC-014 Formalized)
├── 2G: Typed Domain Contracts (Pydantic Models)
├── 2H: Historical Pipeline Orchestration (analyze_historical_ndvi)
├── 2I: Comprehensive Unit & Live Integration Testing
├── 2J: Canonical Documentation Consolidation
└── 2K: Final Verification & Git Checkpoint
```

---

## 14. Architecture Decisions Summary

- **`DEC-012`:** 3-Year Rolling Historical Horizon with Day-of-Year Centered Temporal Matching ($\text{DOY} \pm 15\text{ days}$).
- **`DEC-013`:** Option C Annual Matched-Window Regional Observations & Primary Baseline / Anomaly Metrics.
- **`DEC-014`:** Layered Historical Analysis Contract with Explicit Annual Observation Units & Sufficiency Guardrails.
- **`DEC-015`:** Calendar-Date-Anchored Seasonal Windowing & Cross-Calendar-Year Target-Year Ownership Invariant.

---

## 15. Implementation Boundary & Non-Scope

### In-Scope for Phase 2:
- Multi-year Sentinel-2 querying across historical DOY windows ($Y-1, Y-2, Y-3$).
- Option C annual matched-window regional reductions.
- Historical baseline computation (median, mean, standard deviation).
- Anomaly calculation (absolute departure, gated percentage departure, gated z-score).
- Strongly typed Pydantic models (`HistoricalNdviAnalysis`) and comprehensive test suites.

### Strictly Out-of-Scope (Deferred):
- ❌ **No NDWI or Dynamic World** (Deferred to **Phase 3**).
- ❌ **No Weather or Soil Data Fusion** (Deferred to **Phase 4**).
- ❌ **No Gemini Agronomic Reasoning or Crop Health Diagnosis** (Deferred to **Phase 5**).
- ❌ **No Live FastMCP Tool Registration** (Deferred to **Phase 6**).
- ❌ **No Frontend Heatmaps or UI Charts** (Deferred to **Phase 9**).

---

## 16. Open Technical Questions for Implementation

1. **Earth Engine Server-Side Aggregation Construct:** Determine whether Option C annual reductions are best implemented via `ee.Join` / `ee.ImageCollection.map` or via server-side filtered sub-collections within a combined compute graph. *(To be investigated in Phase 2C).*
2. **Leap Year & Temporal Window Alignment:** Formalized in Phase 2B (`DEC-015`) using pure Python calendar-date-anchored seasonal windowing and cross-year target-year ownership. Sealed in `docs/phases/PHASE_02B_TEMPORAL_WINDOW_SEASONALITY.md`.
