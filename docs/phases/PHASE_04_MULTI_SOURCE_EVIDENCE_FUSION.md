# Phase 4 — Multi-Source Evidence Fusion Architecture

> **Canonical Architecture Design and Implementation for Phase 4: Multi-Source Evidence Fusion & Unified Context Assembly.**  
> *Status: 🟢 APPROVED / IMPLEMENTED (`DEC-022`)*<br>
> *Base Implementation Checkpoint: `7a8371c — feat(environment): complete Phase 3C Dynamic World context`*<br>
> *Subphase: Phase 4 (Architecture, Domain Types, Pure Assembly & Root Orchestrator Pipeline)*<br>
> *Verification: 42 Unit Tests Passed | 1 Live EE Integration Test Passed | 919 Full Unit Suite Passed*

---

## 1. Executive Summary

Phases 1, 2, and 3 constructed five independent, decoupled remote-sensing and environmental intelligence subsystems:
1. **Sentinel-2 Regional NDVI (Phase 1 — `60f8d90`):** Instantaneous radiometric vegetation greenness and canopy density at $10\text{ m}$ spatial scale ([`RegionalNdviAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L116)).
2. **Historical Seasonal NDVI Baseline & Anomaly (Phase 2 — `ebba070`):** Departure from a 3-year rolling seasonal baseline ($Y-1, Y-2, Y-3$, $\text{DOY} \pm 15\text{ days}$) ([`HistoricalNdviAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L493)).
3. **ERA5-Land Daily Reanalysis (Phase 3A — `74fd372`):** Ambient 2m temperature, topsoil volumetric water fraction ($0\text{–}7\text{ cm}$), and surface runoff across 7d/30d/90d envelopes ($\approx 11.1\text{ km}$) ([`ERA5LandAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/types.py#L154)).
4. **CHIRPS Daily Precipitation (Phase 3B — `f70dada`):** Satellite-partitioned daily rainfall distribution and cumulative metrics across 7d/30d/90d envelopes ($\approx 5.566\text{ km}$) ([`CHIRPSRainfallAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_types.py#L104)).
5. **Dynamic World Land-Cover Context (Phase 3C — `7a8371c`):** 9-class continuous probability distribution and dominant land-cover class ($10\text{ m}$) ([`DynamicWorldAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world_types.py#L79)).

**Phase 4 introduces Multi-Source Evidence Fusion.** Its sole objective is to assemble these disparate observational streams into a single, strongly typed, coherent, and auditable domain envelope: **[`AgriculturalEnvironmentalEvidence`](#3-proposed-domain-contract-agriculturalenvironmentalevidence)**.

```
                        Farmer Location (lat, lon) + Reference Date
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
             Satellite Intelligence                     Environmental Context
         ┌───────────────────────────────┐        ┌───────────────────────────────┐
         │ 1. Sentinel-2 Current NDVI    │        │ 3. ERA5-Land (Reanalysis)     │
         │ 2. Historical Multi-Year NDVI │        │ 4. CHIRPS (Rainfall Windows)  │
         │    (Baseline & Departure)     │        │ 5. Dynamic World (9-Class LC) │
         └──────────────┬────────────────┘        └───────────────┬───────────────┘
                        │                                         │
                        └────────────────────┬────────────────────┘
                                             ▼
                                ┌─────────────────────────┐
                                │     PHASE 4 FUSION      │
                                │   (Direct Composition   │
                                │   + Status Resolution)  │
                                └────────────┬────────────┘
                                             ▼
                             AgriculturalEnvironmentalEvidence
                               (Single Normalized Payload)
                                             │
                                             ▼
                                       Phase 5 (Future)
                                Gemini Agricultural Reasoning
```

> [!IMPORTANT]
> **Core Architectural Principle:** *"Data sufficiency takes priority over dataset accumulation."*  
> Phase 4 performs **evidence assembly only**. It does NOT perform agricultural diagnosis, crop stress scoring, drought classification, yield prediction, or farmer recommendations. It delivers an objective, multi-scale physical evidence base to Phase 5 for downstream LLM reasoning.

---

## 2. Repository Discovery & Existing Subsystem Inventory

A comprehensive audit of the active codebase ([`app/satellite/`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/), [`app/environment/`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/)) reveals the exact existing entry points and domain contracts:

| Subsystem | Primary Public Entry Point | Native Spatial Resolution | Temporal Scope & Cadence | Primary Domain Output | Status Enums Supported |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **Sentinel-2 Current NDVI** | [`analyze_regional_ndvi`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/pipeline.py#L195) | $10.0\text{ m}$ | Single newest usable scene within lookback window (default 30d) | [`RegionalNdviAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L116) (wrapped in [`EarthEngineResult`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L66)) | `success`, `no_data`, `error` |
| **Historical Seasonal NDVI** | [`analyze_historical_years`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical.py#L663) + [`build_historical_ndvi_analysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical_analysis.py#L47) | $10.0\text{ m}$ | 3-year baseline ($Y-1, Y-2, Y-3$, $\text{DOY} \pm 15\text{ days}$) | [`HistoricalNdviAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L493) | `success`, `insufficient_history`, `no_data`, `error` |
| **ERA5-Land Environmental** | [`analyze_era5_land`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/pipeline.py#L195) | $\approx 11.1\text{ km}$ ($0.1^\circ$) | Daily series + 7d, 30d, 90d retrospective envelopes | [`ERA5LandAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/types.py#L154) | `success`, `no_data`, `error` |
| **CHIRPS Rainfall Backup** | [`analyze_chirps_rainfall`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_pipeline.py#L162) | $\approx 5.566\text{ km}$ ($0.05^\circ$) | Daily series + 7d, 30d, 90d retrospective envelopes | [`CHIRPSRainfallAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_types.py#L104) | `success`, `no_data`, `error` |
| **Dynamic World Land Cover** | [`analyze_dynamic_world_land_cover`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world_pipeline.py#L206) | $10.0\text{ m}$ | Single newest usable observation within 30-day lookback | [`DynamicWorldAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world_types.py#L79) | `success`, `no_data`, `error` |

### Key Discovery Insights:
1. **Shared Spatial Primitives:** All subsystems accept `latitude: float`, `longitude: float`, and `radius_m: float = 100.0`, and output [`AnalysisRegionMetadata`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L103).
2. **Shared Error Primitives:** All subsystems utilize [`EarthEngineError`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L25) (`type: str`, `message: str`) and structured status models.
3. **Phase 1 $\to$ Phase 2 Existing Integration Path:**
   - [`analyze_historical_years`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical.py#L708) natively accepts `reference_date` as a `RegionalNdviAnalysis` instance and extracts `observation.acquisition_date` directly.
   - [`build_historical_ndvi_analysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical_analysis.py#L47) natively accepts `current: Union[RegionalNdviAnalysis, EarthEngineResult, None]` alongside `historical_observations`.
   - Thus, Phase 4 orchestrator passes the output of [`analyze_regional_ndvi`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/pipeline.py#L195) directly into [`analyze_historical_years`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical.py#L663) and [`build_historical_ndvi_analysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical_analysis.py#L47) using **existing sealed APIs**, avoiding redundant optical Earth Engine queries without modifying Phase 1 or Phase 2.

---

## 3. Proposed Domain Contract (`AgriculturalEnvironmentalEvidence`)

### 3.1 Field Naming & Direct Composition Decision
Following architectural review:
- **Field Name:** `reanalysis: ERA5LandAnalysis` (accurately denotes reanalysis data rather than implying exclusive coverage of all weather/soil).
- **Direct Composition:** Directly embed `HistoricalNdviAnalysis`, `ERA5LandAnalysis`, `CHIRPSRainfallAnalysis`, and `DynamicWorldAnalysis` as first-class fields under a shared reference and region header.
- **Zero Schema Duplication:** Preserves sub-model validation invariants, lineage, error metadata, and eliminates duplicate scalar field definitions.

### 3.2 Contract Definition (`app/fusion/types.py`)

```python
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.environment.chirps_types import CHIRPSRainfallAnalysis
from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.types import ERA5LandAnalysis
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    HistoricalNdviAnalysis,
    RegionalNdviAnalysis,
)

FusionStatus = Literal["success", "partial", "no_data", "error"]


class AgriculturalEnvironmentalEvidence(BaseModel):
    """Authoritative multi-source agricultural and environmental evidence envelope (DEC-022).
    
    Synthesizes current vegetation vigor, 3-year historical NDVI departures, ERA5-Land reanalysis,
    CHIRPS precipitation, and Dynamic World land-cover context over the farmer's AnalysisRegion.
    """

    region: AnalysisRegionMetadata = Field(
        description="Shared geographic footprint and circular parcel buffer metadata"
    )
    reference_date: date = Field(
        description="Authoritative reference / query anchor date (UTC)"
    )
    vegetation: HistoricalNdviAnalysis = Field(
        description="Current Sentinel-2 vegetation vigor, historical baseline, and anomaly evidence"
    )
    reanalysis: ERA5LandAnalysis = Field(
        description="ERA5-Land daily reanalysis (temperature, topsoil moisture, runoff, precipitation)"
    )
    rainfall: CHIRPSRainfallAnalysis = Field(
        description="CHIRPS daily precipitation distribution and retrospective rainfall windows"
    )
    land_cover: DynamicWorldAnalysis = Field(
        description="Dynamic World 9-class land-cover probability distribution and dominant class"
    )
    status: FusionStatus = Field(
        description="Unified operational status across all evidence sources: success | partial | no_data | error"
    )
    sources_requested_count: int = Field(
        default=4,
        description="Total distinct evidence subsystems evaluated (Vegetation, Reanalysis, Rainfall, Land Cover)",
    )
    sources_available_count: int = Field(
        ge=0,
        le=4,
        description="Count of distinct evidence subsystems providing usable evidence (full or partial)",
    )
    sources_fully_available_count: int = Field(
        ge=0,
        le=4,
        description="Count of distinct evidence subsystems returning status='success'",
    )
    is_fully_available: bool = Field(
        description="True if all 4 requested sources are fully available (sources_fully_available_count == 4)"
    )
    pipeline_version: str = Field(
        default="4.0.0",
        description="Semantic version of the multi-source evidence fusion pipeline",
    )
    error: EarthEngineError | None = Field(
        default=None,
        description="Structured error details if an unhandled top-level fusion error occurred",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    @property
    def current_vegetation(self) -> RegionalNdviAnalysis | None:
        """Convenience property accessing the current Phase 1 Sentinel-2 observation."""
        return self.vegetation.current
```

---

## 4. Subsystem Availability & Status Resolution Semantics

### 4.1 Subsystem Availability Determination

The fusion engine evaluates each of the 4 subsystems into one of three availability states:
- **`FULL`**: The subsystem completed with complete evidence (`status == "success"`).
- **`PARTIAL`**: Useful evidence exists, but not all requested components are present. Specifically for [`HistoricalNdviAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L493), if `status == "insufficient_history"`, current NDVI evidence ([`RegionalNdviAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L116)) is still fully valid and available even though a 3-year baseline could not be formed.
- **`UNAVAILABLE`**: Zero usable evidence available (`status == "no_data"` or `status == "error"`).

| Subsystem | `FULL` Availability Condition | `PARTIAL` Availability Condition | `UNAVAILABLE` Condition |
| :--- | :--- | :--- | :--- |
| **Vegetation (`HistoricalNdviAnalysis`)** | `status == "success"` (Current NDVI + $\ge 2$-year historical baseline + anomaly valid) | `status == "insufficient_history"` (Current NDVI is valid, but $< 2$ historical years usable) | `status == "no_data"` OR `status == "error"` |
| **Reanalysis (`ERA5LandAnalysis`)** | `status == "success"` (Daily observations and window statistics present) | *N/A* (Window-level missingness handled by `is_complete=False` inside sub-model) | `status == "no_data"` OR `status == "error"` |
| **Rainfall (`CHIRPSRainfallAnalysis`)** | `status == "success"` (Daily precipitation and window statistics present) | *N/A* (Window-level missingness handled by `is_complete=False` inside sub-model) | `status == "no_data"` OR `status == "error"` |
| **Land Cover (`DynamicWorldAnalysis`)** | `status == "success"` (Newest observation, 9-class probabilities, dominant class present) | *N/A* | `status == "no_data"` OR `status == "error"` |

### 4.2 Overall Fusion Status Matrix

The overall fused `status` is evaluated deterministically:

$$\mathbf{status} = f(\text{Vegetation}, \text{Reanalysis}, \text{Rainfall}, \text{Land Cover})$$

| Scenario | Subsystem Availability Combination | Overall `status` | `sources_available_count` | `sources_fully_available_count` | `is_fully_available` | Behavioral Rule |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | All 4 subsystems `FULL` (`status == "success"`) | `success` | 4 | 4 | `True` | Complete multi-source intelligence available. |
| **2** | All 4 have usable data, but 1+ is `PARTIAL` (e.g. Vegetation `insufficient_history`, others `success`) | `partial` | 4 | 3 | `False` | Preserves all available data (e.g. current NDVI + reanalysis + rainfall + land cover). |
| **3** | Some subsystems `FULL`/`PARTIAL`, some `no_data`, some `error` (at least 1 usable source exists) | `partial` | 1, 2, or 3 | 0 to 3 | `False` | Preserves all successful evidence without aborting. |
| **4** | **All 4 subsystems `no_data`** | `no_data` | 0 | 0 | `False` | No usable observation exists across all archives for given location/date. |
| **5** | **All 4 subsystems `error`** | `error` | 0 | 0 | `False` | Fatal failure across all subsystem queries. |
| **6** | **Zero usable evidence with mixed `no_data` and `error`** (e.g. 2 `no_data`, 2 `error`) | `error` | 0 | 0 | `False` | Fails to `error` because execution encountered operational failures without recovering any evidence. |
| **7** | **Top-level execution failure** (e.g. invalid coordinates before sub-pipeline execution) | `error` | 0 | 0 | `False` | Fails to `error` with top-level `EarthEngineError`. |

### 4.3 Key Partial-Failure Invariants:
1. **Preserve Valid Evidence:** If at least one evidence source succeeds, the fusion result returns `status="partial"` and preserves all valid sub-models.
2. **Zero Error Swallowing:** Subsystem errors remain intact in `subsystem.error` and are never silently converted to `no_data` or `None`.
3. **Zero Null Hallucination:** If a source is `no_data`, missing fields remain `None` (never defaulted to `0.0`).
4. **No Synthetic Confidence Scores:** The system does not calculate an arbitrary mathematical confidence percentage (e.g. `75% confidence`). Downstream reasoning inspects `sources_available_count`, `sources_fully_available_count`, and `is_fully_available` directly.

---

## 5. Spatial Semantics

The multi-source evidence spans different native spatial resolutions:
- **Sentinel-2 NDVI:** $10.0\text{ m}$ native spatial scale.
- **Dynamic World:** $10.0\text{ m}$ native spatial scale.
- **CHIRPS Daily Precipitation:** $\approx 5.566\text{ km}$ ($0.05^\circ$) native grid.
- **ERA5-Land Reanalysis:** $\approx 11.1\text{ km}$ ($0.1^\circ$) native grid.

```
Spatial Alignment Model:
┌─────────────────────────────────────────────────────────────────────────┐
│ ERA5-Land Cell (~11.1 km)                                              │
│   ┌───────────────────────────────────────────────────────────────────┐ │
│   │ CHIRPS Cell (~5.566 km)                                           │ │
│   │   ┌─────────────────────────────────────────────────────────────┐ │ │
│   │   │ Sentinel-2 & Dynamic World (10m Pixels)                     │ │ │
│   │   │   [●] 100m AnalysisRegion Circular Buffer (~3.14 ha)       │ │ │
│   │   └─────────────────────────────────────────────────────────────┘ │ │
│   └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Spatial Guarantees:
1. **Shared Requested Footprint:** Every underlying query executes an unweighted zonal mean reduction over the identical $100\text{ m}$ radius circular `AnalysisRegion` ($3.14\text{ ha}$) centered at the farmer's coordinates.
2. **Native Resolution Transparency:** Each subsystem explicitly records its native resolution in its sub-contract (`spatial_resolution_km=11.1`, `spatial_resolution_km=5.566`, `spatial_resolution_m=10.0`).
3. **No Synthetic Resampling:** Prohibits artificial spatial resampling, downscaling, kriging, or synthetic sub-pixel weighting.
4. **Non-Cadastral Invariant:** Coarse reanalysis and satellite grids represent *regional contextual regimes*, never claimed as sub-field cadastral boundaries.

---

## 6. Temporal Semantics

External datasets operate on different publication latencies and cadences:
- **Sentinel-2:** Irregular overpass interval (~2–5 days revisit); newest scene within $[T-29, T]$.
- **Historical Baseline:** Matched Day-of-Year windows $[T_h \pm 15\text{ days}]$ across $Y-1, Y-2, Y-3$.
- **ERA5-Land:** Daily aggregates; operational publication lag $\approx 5\text{ days}$ ($T-5$).
- **CHIRPS:** Daily precipitation; operational publication lag $\approx 1\text{–}3\text{ days}$ ($T-2$).
- **Dynamic World:** NRT Sentinel-2 L1C predictions; newest usable scene within $[T-29, T]$.

```
Temporal Alignment Horizon (Reference Date T):
[T-90d] ────────────────────────────────────────────────────────── [T]
ERA5-Land:    [──────────────── 90-Day Window ────────────────]──► (Lag: e.g. 5d)
CHIRPS:       [──────────────── 90-Day Window ────────────────]──► (Lag: e.g. 2d)
DynamicWorld:                           [─── 30-Day Window ───]──► (Newest Usable: e.g. T-3d)
Sentinel-2:                             [─── 30-Day Window ───]──► (Newest Usable: e.g. T-4d)
Historical:   [T(Y-1) ± 15d], [T(Y-2) ± 15d], [T(Y-3) ± 15d]     (Seasonal DOY Baseline)
```

### Temporal Guarantees:
1. **Unified Query Anchor:** All subsystems receive the identical `reference_date: date`.
2. **Zero Timestamp Fabrication:** The fusion layer never forces a synthetic single timestamp across sources. Each subsystem retains its true `observation_date`, `latest_available_date`, and `data_lag_days`.
3. **Multi-Window Preservation:** Retrospective 7d, 30d, and 90d window statistics are preserved directly as computed by their respective pure aggregation engines.

---

## 7. Recommended Orchestration Architecture

### 7.1 Two-Tier Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Tier 2: Root Orchestration Pipeline (app/fusion/pipeline.py)            │
│   ├── Validates coordinates (lat, lon) and resolves reference_date      │
│   ├── Calls analyze_regional_ndvi (Phase 1 Sentinel-2)                  │
│   ├── Passes Phase 1 result to analyze_historical_years & build_hist    │
│   │   (REUSES EXISTING PHASE 2 APIs WITHOUT DUPLICATE QUERIES)          │
│   ├── Calls analyze_era5_land, analyze_chirps_rainfall, DW land-cover   │
│   │   (Sequential execution; catches exceptions into typed error models)│
│   └── Passes 4 domain objects to Tier 1                                 │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Tier 1: Pure Local Assembly & Status Engine (app/fusion/fusion.py)      │
│   ├── Evaluates status resolution matrix (success | partial | etc.)     │
│   ├── Computes sources_available_count & sources_fully_available_count  │
│   ├── Constructs immutable AgriculturalEnvironmentalEvidence envelope   │
│   └── ZERO Earth Engine imports, ZERO network I/O (100% Offline)        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Exact Execution Flow & Query Coordination:

1. Validate input coordinates (`latitude`, `longitude`, `radius_m`) and resolve `reference_date`.
2. Execute **Vegetation Retrieval**:
   - Call [`analyze_regional_ndvi`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/pipeline.py#L195).
   - If successful, pass the [`RegionalNdviAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py#L116) result into [`analyze_historical_years`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical.py#L663) (which extracts `acquisition_date` natively) and pass both to [`build_historical_ndvi_analysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical_analysis.py#L47).
   - If Phase 1 returns `no_data` or `error`, call [`build_historical_ndvi_analysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical_analysis.py#L47) with `current=current_res, historical_observations=[]` (which cleanly sets `status="no_data"` or `"error"` without executing historical queries).
3. Execute **Reanalysis Retrieval**:
   - Call [`analyze_era5_land`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/pipeline.py#L195). Catch unhandled errors into a structured fallback [`ERA5LandAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/types.py#L154) (`status="error"`).
4. Execute **Rainfall Retrieval**:
   - Call [`analyze_chirps_rainfall`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_pipeline.py#L162). Catch unhandled errors into a structured fallback [`CHIRPSRainfallAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_types.py#L104) (`status="error"`).
5. Execute **Land-Cover Retrieval**:
   - Call [`analyze_dynamic_world_land_cover`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world_pipeline.py#L206). Catch unhandled errors into a structured fallback [`DynamicWorldAnalysis`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world_types.py#L79) (`status="error"`).
6. Pass the 4 domain payloads into Tier 1 `fuse_agricultural_environmental_evidence(...)` to assemble the final immutable [`AgriculturalEnvironmentalEvidence`](#32-contract-definition-appfusiontypespy).

---

## 8. Proposed Module Structure

```
app/
├── fusion/
│   ├── __init__.py                # Exports AgriculturalEnvironmentalEvidence, fuse_*, fetch_*
│   ├── types.py                   # AgriculturalEnvironmentalEvidence, FusionStatus
│   ├── fusion.py                  # Tier 1: Pure local assembly & status resolution (0 EE calls)
│   └── pipeline.py                # Tier 2: Root orchestrator calling sub-pipelines
tests/
├── fixtures/
│   └── fusion/
│       ├── complete_success.json  # 4 sources success
│       ├── partial_chirps_missing.json # CHIRPS no_data
│       ├── partial_ndvi_error.json # NDVI error
│       ├── partial_insufficient_history.json # Vegetation insufficient_history
│       ├── all_no_data.json       # 4 sources no_data
│       ├── all_error.json         # 4 sources error
│       └── mixed_nodata_error_zero_usable.json # Mixed no_data and error with 0 usable
├── unit/
│   ├── test_fusion_types.py       # Pydantic schema validation & immutability
│   └── test_fusion_assembly.py    # Offline status matrix, counts, lag propagation
└── integration/
    └── test_fusion_integration.py # Live EE end-to-end execution against Punjab coordinates
```

---

## 9. Scientific Boundaries & Prohibitions

Phase 4 is strictly an **evidence aggregation engine**. It explicitly enforces the following prohibitions:

- 🔴 Prohibits crop disease diagnosis or pest warnings.
- 🔴 Prohibits classifying agricultural drought severity or drought indices.
- 🔴 Prohibits calculating arbitrary "soil health", "water stress", or "crop stress" index scores.
- 🔴 Prohibits predicting crop yields or economic revenues.
- 🔴 Prohibits prescribing irrigation timing, fertilizer dosing, or crop recommendations.
- 🔴 Prohibits synthesizing artificial percentage confidence scores (e.g. "85% confidence").
- 🔴 Prohibits cross-source normalized mathematical indexes or weighted score formulas.
- 🔴 Prohibits adding new remote sensing datasets, spectral indices, or external APIs.

---

## 10. Test Strategy (20 Test Scenarios)

The test suite will be structured across 20 distinct scenarios covering contract integrity, status resolution, partial failure modes, and provenance:

1. **Scenario 1:** All 4 sources successful $\to$ `status="success"`, `sources_available_count=4`, `sources_fully_available_count=4`, `is_fully_available=True`.
2. **Scenario 2:** CHIRPS `no_data` while other 3 sources succeed $\to$ `status="partial"`, `sources_available_count=3`, `sources_fully_available_count=3`, `is_fully_available=False`.
3. **Scenario 3:** Dynamic World `no_data` while other 3 sources succeed $\to$ `status="partial"`, `sources_available_count=3`, `sources_fully_available_count=3`, `is_fully_available=False`.
4. **Scenario 4:** ERA5-Land `error` while other 3 sources succeed $\to$ `status="partial"`, `sources_available_count=3`, `sources_fully_available_count=3`, `is_fully_available=False`.
5. **Scenario 5:** Historical NDVI `insufficient_history` with valid current NDVI while other 3 sources succeed $\to$ `status="partial"`, `sources_available_count=4`, `sources_fully_available_count=3`, `is_fully_available=False`.
6. **Scenario 6:** Historical NDVI `no_data` while other 3 sources succeed $\to$ `status="partial"`, `sources_available_count=3`, `sources_fully_available_count=3`, `is_fully_available=False`.
7. **Scenario 7:** Historical NDVI `error` while other 3 sources succeed $\to$ `status="partial"`, `sources_available_count=3`, `sources_fully_available_count=3`, `is_fully_available=False`.
8. **Scenario 8:** Mixed `no_data` + `error` with 1 or 2 usable sources $\to$ `status="partial"`, preserving all usable evidence.
9. **Scenario 9:** All 4 sources `no_data` $\to$ `status="no_data"`, `sources_available_count=0`, `sources_fully_available_count=0`, `is_fully_available=False`.
10. **Scenario 10:** All 4 sources `error` $\to$ `status="error"`, `sources_available_count=0`, `sources_fully_available_count=0`, `is_fully_available=False`.
11. **Scenario 11:** Zero usable evidence with mixed `no_data` and `error` (e.g. 2 `no_data` and 2 `error`) $\to$ `status="error"`, `sources_available_count=0`, `sources_fully_available_count=0`.
12. **Scenario 12:** Missing values remain `None` (never converted to `0.0`).
13. **Scenario 13:** Source-specific spatial resolutions preserved ($10\text{ m}$, $5.566\text{ km}$, $11.1\text{ km}$).
14. **Scenario 14:** Source-specific observation dates preserved without fabrication.
15. **Scenario 15:** Source-specific `data_lag_days` preserved without distortion.
16. **Scenario 16:** Reference date correctly propagated to all sub-payloads.
17. **Scenario 17:** Zero Earth Engine imports in pure assembly module (`app/fusion/fusion.py`).
18. **Scenario 18:** Zero network I/O in pure assembly module (`app/fusion/fusion.py`).
19. **Scenario 19:** Existing source domain objects are immutable and never mutated during fusion.
20. **Scenario 20:** Zero synthetic confidence percentages generated.

---

## 11. Architectural Decision Proposal (DEC-022)

The accompanying architectural decision [`DEC-022: Multi-Source Evidence Fusion Architecture`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/docs/DECISION_LOG.md#dec-022-multi-source-evidence-fusion-architecture) is recorded in `docs/DECISION_LOG.md` with status: **`PROPOSED / PENDING REVIEW`**.

---

## 12. Open Design Questions

1. **Top-Level Error Capture:** If an unhandled fatal Python exception occurs at the root orchestrator level (e.g. invalid parameter type), the orchestrator returns an envelope with `status="error"`, `sources_available_count=0`, and `error=EarthEngineError(type="InternalError", message=str(exc))`. This ensures callers never receive unhandled exceptions. *(Recommended: Approved).*
2. **Sequential vs Concurrent Execution:** Sequential execution is standard for Tier 2 in Phase 4. Asynchronous/threaded execution is deliberately not designed here and can be evaluated in Phase 6 (MCP tool layer) if needed. *(Recommended: Approved).*
