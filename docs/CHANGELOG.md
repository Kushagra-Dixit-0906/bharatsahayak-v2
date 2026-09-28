# BharatSahayak V2 — Project Changelog

> **Chronological record of architectural changes, feature implementations, and documentation milestones.**  
> *Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).*

---

## [Unreleased] — Planned Phases 1 through 11

### 🟢 Complete & Sealed — Phase 5C: Grounded Gemini Explanation Layer & Unified Assessment Pipeline (`DEC-024`, `DEC-025` — 68 Unit/Integration Tests)
- **Step 1 — Gemini Context Boundary ([`app/assessment/gemini_types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/gemini_types.py), `74c9f49`):**
  - Implemented `GeminiAssessmentContext` root context model, `ContextPatternSummary`, `VerifiedFarmerContext`, and `PresentationPreferences`.
  - Implemented pure projection function `assessment_to_gemini_context()` mapping authoritative Phase 5B `AgriculturalAssessment` into minimal, immutable context.
  - Enforced strict PII exclusion and personal-context boundaries (`crop`, `crop_stage`, `irrigation_available`, `preferred_language`, `context_status`). Farmer context serves strictly as personalization, never as environmental evidence.
- **Step 2 — Controlled Gemini Prompt Builder ([`app/assessment/gemini_prompt.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/gemini_prompt.py), `dc1fd39`):**
  - Implemented `build_gemini_prompt()` utilizing a strict 5-tier structural hierarchy: System Role & Safety $\to$ Output Schema $\to$ `<assessment_data>` $\to$ `<farmer_context>` $\to$ Task Instructions.
  - Enforced prompt-injection defense isolating user data in passive XML tags, epistemic invariants (no uncalibrated thresholds, no disease diagnosis, no drought declarations), and explicit prohibited output classes (chemicals, dosages, yield numbers).
- **Step 3 — Isolated Gemini Explanation Service ([`app/assessment/gemini_service.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/gemini_service.py), `39a7617`):**
  - Implemented `GeminiModelClient` abstraction and `DefaultGeminiClient` utilizing `gemini-2.5-flash` via project configuration.
  - Implemented structured JSON generation with 3-stage validation: Stage 1 Pydantic schema validation (`FarmerAgriculturalResponse`), Stage 2 defense-in-depth banned-content regex scanner (blocking chemical units and active ingredients), and Stage 3 agronomic invariant checks.
  - Implemented deterministic offline fallback engine (`generate_deterministic_fallback_explanation`) providing complete, compliant responses for all 8 Phase 5B overall environmental conditions in English and Hindi.
- **Step 4 — Unified Assessment & Explanation Pipeline ([`app/assessment/pipeline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/pipeline.py), `b05fc54`):**
  - Implemented `AgriculturalAssessmentExplanationResponse` domain envelope containing `assessment`, `explanation`, and `context_used`.
  - Implemented `evaluate_and_explain_agricultural_assessment()` and `fetch_agricultural_assessment_explanation()`.
  - Implemented error assessment Gemini bypass: assessments with `status == "error"` bypass Gemini completely to produce a deterministic error response while preserving `assessment.status == "error"`.
  - Implemented fallback status preservation: on valid assessments (`success`, `partial`, `insufficient_evidence`), original assessment status is preserved if Gemini fallback is triggered.
- **Public Package Exports & Decoupling ([`app/assessment/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/__init__.py)):**
  - Exported all Phase 5C contracts and functions (`AgriculturalAssessmentExplanationResponse`, `FarmerAgriculturalResponse`, `GeminiAssessmentContext`, `VerifiedFarmerContext`, `PresentationPreferences`, `assessment_to_gemini_context`, `evaluate_and_explain_agricultural_assessment`, `fetch_agricultural_assessment_explanation`).
- **Testing & Verification:**
  - Created 27 context and prompt unit tests in `tests/unit/test_assessment_gemini_types.py` and `tests/unit/test_assessment_gemini_prompt.py`.
  - Created 27 explanation service and fallback unit tests in `tests/unit/test_assessment_gemini_service.py` (with fake client fixtures and regex scanning).
  - Created 14 unified pipeline integration tests in `tests/unit/test_assessment_pipeline.py`.
  - Verified 41 Phase 5B regression tests. Full repository unit suite: 1,028 passed, 0 failures, 0 regressions. 100% offline test execution with zero live Gemini API calls.

### 🟢 Complete & Verified — Phase 5B: Deterministic Agricultural Evidence Interpretation (`DEC-023` — 41 Unit Tests)
- **Domain Models & Assessment Contracts ([`app/assessment/types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/types.py)):**
  - Implemented `AgriculturalAssessment` root domain envelope (`pipeline_version="5.0.0"`) with direct composition of the authoritative Phase 4 `AgriculturalEnvironmentalEvidence` envelope.
  - Implemented `SupportingEvidenceItem` domain model capturing multi-source physical observation provenance (`source: vegetation | reanalysis | rainfall | land_cover`, `metric_name`, `observed_value`, `reference_context`).
  - Implemented `EnvironmentalStressPattern` domain model representing discrete physical stress patterns (`pattern_type: EnvironmentalStressPatternType`, `evidence_support: EvidenceSupportLevel`, `severity: str | None = None` [reserved for future agronomic calibration], `description`, `supporting_evidence`, `conflicting_signals`).
  - Implemented `AssessmentSufficiency` domain model tracking physical completeness and publication latency (`is_sufficient`, `sources_evaluated_count=4`, `sources_available_count`, `sources_fully_available_count`, `missing_evidence_sources`, `partial_evidence_sources`, `maximum_data_lag_days`, `sufficiency_summary`).
  - Implemented standardized 8-value `OverallEnvironmentalCondition` summary literal (`"stable"`, `"vegetation_stress"`, `"moisture_stress_consistent"`, `"heat_stress_consistent"`, `"combined_stress_consistent"`, `"favorable"`, `"mixed"`, `"insufficient_evidence"`).
  - Enforced strict model immutability (`frozen=True`, `extra="forbid"`) and model validators enforcing status-error invariants and count bounds.
- **Pure Deterministic Reasoning Engine ([`app/assessment/reasoning.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/reasoning.py)):**
  - Implemented `interpret_agricultural_evidence(...)` with zero Earth Engine imports, zero network calls, zero LLM calls, zero filesystem I/O, and zero global mutable state.
  - Implemented pattern detection rules based strictly on validated Phase 1–4 semantics without arbitrary or invented universal numerical agronomic thresholds:
    - `water_stress_consistent_pattern`: Optical vegetation decline corroborated by meteorological rainfall or topsoil moisture deficit.
    - `vegetation_stress_pattern`: Isolated optical vegetation decline without confirmed environmental driver.
    - `near_baseline_stable_condition`: Vegetative vigor aligned with 3-year historical seasonal baseline.
    - `favorable_growth_condition`: Elevated vegetative greenness supported by favorable conditions.
    - `heat_stress_consistent_pattern`: Elevated ambient 2m temperature records observed over retrospective windows (annotated with future calibration requirement).
    - `excess_moisture_waterlogging_consistent_pattern`: Heavy precipitation and elevated runoff consistent with surface moisture accumulation.
    - `combined_environmental_stress_pattern`: Convergence of multiple distinct stress drivers (thermal + hydrological).
    - `conflicting_environmental_signals`: Observable divergence between vegetation vigor and environmental metrics.
  - Implemented observable divergence handling:
    - Case A: Depressed NDVI + normal/high rainfall -> identifies observable divergence without speculating on ungrounded causes (e.g. pests, diseases, nutrients).
    - Case B: Low rainfall + stable/normal NDVI -> identifies observable stability without asserting unverified tube-well irrigation or moisture reserves.
  - Implemented non-crop contextual land cover evaluation using Dynamic World context without claiming cadastral ground truth.
  - Enforced `missing != zero`: Missing sources record pattern-specific insufficiency and limitations rather than inferring negative physical conditions.
- **Assessment Orchestration Pipeline & Public Exports ([`app/assessment/pipeline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/pipeline.py), [`app/assessment/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/assessment/__init__.py)):**
  - Implemented `evaluate_agricultural_assessment(evidence)` and `fetch_agricultural_assessment(...)` orchestration boundaries.
  - Exported all public types and functions.
- **Testing & Verification:**
  - Created 20+ canonical test scenario builders in `tests/fixtures/assessment_fixtures.py`.
  - Added unit test suites `tests/unit/test_assessment_types.py` (10 tests), `tests/unit/test_assessment_reasoning.py` (26 tests), `tests/unit/test_assessment_pipeline.py` (4 tests).
  - Verified 100% pass rate across 40 Phase 5 unit tests and full repository unit suite (959 passed, 0 failures, 0 regressions).

### 🟢 Complete & Verified — Phase 4: Multi-Source Evidence Fusion (`DEC-022` — 42 Unit Tests + 1 Live Integration Test)
- **Multi-Source Evidence Fusion Envelope & Domain Contracts ([`app/fusion/types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/fusion/types.py)):**
  - Implemented strongly typed `AgriculturalEnvironmentalEvidence` root envelope (`pipeline_version="4.0.0"`) with direct composition of validated domain models: `vegetation: HistoricalNdviAnalysis`, `reanalysis: ERA5LandAnalysis`, `rainfall: CHIRPSRainfallAnalysis`, `land_cover: DynamicWorldAnalysis`.
  - Defined 4-tier `FusionStatus` literal (`success`, `partial`, `no_data`, `error`) and exact availability counters (`sources_requested_count=4`, `sources_available_count`, `sources_fully_available_count`, `is_fully_available`).
  - Added `@property current_vegetation` returning `vegetation.current` for direct backward-compatible access to current NDVI without object duplication.
  - Enforced strict model immutability (`frozen=True`, `extra="forbid"`) and model validator enforcing count bounds and status-error invariants.
- **Pure Mathematical & Assembly Engine ([`app/fusion/fusion.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/fusion/fusion.py)):**
  - Implemented `fuse_agricultural_environmental_evidence(...)` with zero Earth Engine imports, zero network calls, and zero filesystem I/O.
  - Implemented deterministic subsystem availability evaluation:
    - Treats `status == "success"` as FULL.
    - Treats `HistoricalNdviAnalysis.status == "insufficient_history"` with valid current NDVI as PARTIAL availability (preserving valid instantaneous NDVI).
    - Evaluates 4-tier fusion matrix (`success` if all 4 FULL; `partial` if usable evidence exists; `no_data` if all 4 `no_data`; `error` if all 4 `error` or mixed zero-usable).
  - Preserves all input domain objects, missing fields (`None`), native spatial resolutions (10m, 5.566km, 11.1km), observation dates, and data lags without mutation or synthetic scoring.
- **Root Orchestration Pipeline ([`app/fusion/pipeline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/fusion/pipeline.py)):**
  - Implemented `fetch_agricultural_environmental_evidence(...)` coordinating sequential sub-pipeline executions: Current NDVI $\to$ Historical NDVI (with Phase 1 pre-computed result reuse) $\to$ ERA5-Land $\to$ CHIRPS $\to$ Dynamic World $\to$ Pure Fusion Assembly.
  - Implemented failure isolation: subsystem execution failures or unhandled exceptions are captured into structured fallback error domain models without aborting healthy subsystems.
- **Public API Exports & Test Infrastructure ([`app/fusion/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/fusion/__init__.py)):**
  - Exported `AgriculturalEnvironmentalEvidence`, `FusionStatus`, `fuse_agricultural_environmental_evidence`, `fetch_agricultural_environmental_evidence`.
  - Created 7 deterministic offline JSON scenarios in `tests/fixtures/fusion/` and typed loader in `tests/fixtures/fusion_fixtures.py`.
  - Added unit test suites `tests/unit/test_fusion_types.py` (11 tests), `tests/unit/test_fusion_assembly.py` (20 design scenarios), `tests/unit/test_fusion_pipeline.py` (11 tests).
  - Added live Earth Engine integration test in `tests/integration/test_fusion_integration.py` (1 live test passing against `bharatsahayak-v2`).
- **Regression Verification:** Full repository test suite passed with 919 unit tests passing (0 failures, 0 regressions).

### 🟢 Complete & Frozen — Phase 3: Additional Agricultural & Environmental Data Sources (Subphases 3A, 3B & 3C Complete & Verified — `DEC-018`, `DEC-019`, `DEC-020`, `DEC-021`; Phase 3D Deferred)
- **Phase 3 Scope Freeze & Phase 3D Deferral (🔴 DEFERRED):**
  - Formally froze the environmental data foundation for the initial prototype across 5 complementary evidence streams (Sentinel-2 NDVI, historical NDVI anomaly, ERA5-Land reanalysis, CHIRPS precipitation, Dynamic World land cover).
  - Established architectural principle: *"Data sufficiency takes priority over dataset accumulation."*
  - Formally deferred Phase 3D ("Additional Environmental Signal", candidate MODIS MOD16A2 evapotranspiration / land-atmosphere water flux) as future backlog to avoid unnecessary complexity, test surface expansion, and failure modes in the absence of a demonstrated reasoning gap.
  - Advanced project trajectory toward Phase 4 (Multi-Source Data Fusion) and Phase 5 (Gemini Agricultural Reasoning).

- **Phase 3C — Dynamic World Land-Cover Context Implementation (🟢 COMPLETE & VERIFIED — `DEC-021` — 39 Unit Tests + 3 Live Integration Tests):**
  - Implemented strongly typed domain models in [`app/environment/dynamic_world_types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world_types.py):
    - `DynamicWorldLandCoverClass`: Literal representing 9 canonical classes (`water`, `trees`, `grass`, `flooded_vegetation`, `crops`, `shrub_and_scrub`, `built`, `bare`, `snow_and_ice`).
    - `DynamicWorldClassProbabilities`: Frozen, extra-forbid Pydantic model for 9 continuous float probabilities in $[0.0, 1.0]$.
    - `DynamicWorldAnalysis`: Root domain payload (`pipeline_version="3.1.0"`, dataset `GOOGLE/DYNAMICWORLD/V1`, spatial resolution $10.0\text{ m}$), integrating `AnalysisRegionMetadata`, dynamic publication lag tracking (`observation_date`, `data_lag_days`), satellite granule lineage (`observation_id` from `system:index`), and universal status semantics (`success`, `no_data`, `error`).
  - Created Earth Engine Dynamic World adapter module [`app/environment/dynamic_world.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world.py):
    - Queries `GOOGLE/DYNAMICWORLD/V1` collection over parcel circular buffer (`create_analysis_region`) across 30-day window $[E-29, E+1)$.
    - Selects 9 probability bands, applies unweighted zonal mean spatial reduction (`ee.Reducer.mean()`) at native 10m scale, filters server-side for usable non-null regional probability data, and selects the newest usable observation (`.first()`).
    - Zero temporal averaging, median, mode, or temporal compositing across multiple observations.
    - Captures server-side errors into structured `EarthEngineError` result envelopes without leaking exceptions.
  - Created pure normalization and root orchestration module [`app/environment/dynamic_world_pipeline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/dynamic_world_pipeline.py):
    - `normalize_raw_dynamic_world_record`: 1:1 probability preservation without rounding, scaling, clipping, or arbitrary thresholds.
    - `derive_dominant_land_cover`: Argmax calculation with deterministic canonical GEE index order tie-breaking (`water` > `trees` > `grass` > `flooded_vegetation` > `crops` > `shrub_and_scrub` > `built` > `bare` > `snow_and_ice`).
    - `analyze_dynamic_world_land_cover`: Orchestrates spatial validation, Tier 1 retrieval, Tier 2 normalization, dynamic publication data lag computation, and root payload composition.
  - Updated public API exports in [`app/environment/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/__init__.py).
  - Created 5 deterministic offline JSON fixtures in `tests/fixtures/dynamic_world/` and loader in `tests/fixtures/dynamic_world_fixtures.py`.
  - Created offline unit test suites in `tests/unit/test_dynamic_world_types.py` and `tests/unit/test_dynamic_world_pipeline.py` (39 unit tests passing; 877 full repository unit tests passing).
  - Created live Earth Engine integration test suite in `tests/integration/test_dynamic_world_integration.py` (3 live tests passing against `bharatsahayak-v2`).


- **Phase 3B — CHIRPS Regional Rainfall Backup Subsystem Implementation (🟢 COMPLETE & VERIFIED — `DEC-020` — 49 Unit Tests + 3 Live Integration Tests):**
  - Implemented strongly typed domain models in [`app/environment/chirps_types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_types.py):
    - `DailyRainfallObservation`: Physical daily precipitation observation with native mm/day unit, valid zero ($0.0\text{ mm}$), missing preservation (`None`), and negative artifact rejection.
    - `RainfallWindowStatistics`: Aggregated summary statistics (`total_precipitation_mm`, `mean_daily_precipitation_mm`, `max_daily_precipitation_mm`) over 7-day, 30-day, and 90-day envelopes with completeness tracking (`is_complete`, `days_available`, `days_requested`).
    - `CHIRPSRainfallAnalysis`: Authoritative root domain payload (`pipeline_version="3.1.0"`, dataset `UCSB-CHC/CHIRPS/V3/DAILY_SAT`, spatial resolution $5.566\text{ km}$), integrating `AnalysisRegionMetadata`, dynamic publication lag tracking (`latest_available_date`, `data_lag_days`), and universal status semantics (`success`, `no_data`, `error`).
  - Created Earth Engine CHIRPS adapter module [`app/environment/chirps.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps.py):
    - Queries `UCSB-CHC/CHIRPS/V3/DAILY_SAT` collection over parcel circular buffer (`create_analysis_region`) across $[E-89, E+1)$.
    - Selects `precipitation` band.
    - Implements Option A spatial reduction: unweighted zonal mean reduction (`ee.Reducer.mean()`) at native nominal scale $5566.0\text{ m}$ (coarse regional context boundary, no synthetic downscaling or continuous interpolation).
    - Captures server-side errors into structured `EarthEngineError` result envelopes without leaking exceptions.
  - Created pure mathematical window aggregation engine [`app/environment/chirps_aggregation.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_aggregation.py):
    - `aggregate_rainfall_window_statistics`: Inclusive 7d ($E-6$), 30d ($E-29$), and 90d ($E-89$) envelopes, order invariance, duplicate date rejection (`ValueError`), partial-window available-observation semantics (`is_complete=False`), empty-window handling (metrics `None`).
    - `compute_rainfall_window_suite`: Standardized 3-window tuple generator.
  - Created pure normalization and root orchestration module [`app/environment/chirps_pipeline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/chirps_pipeline.py):
    - `normalize_raw_chirps_record`: 1:1 unit preservation ($\text{mm/day}$), zero scaling/rounding/clamping, missing != 0.0, negative artifact rejection to `None`.
    - `analyze_chirps_rainfall`: Orchestrates spatial validation, Tier 1 retrieval, Tier 2 normalization, dynamic publication data lag computation, pure rainfall window aggregation, and root payload composition.
  - Updated public API exports in [`app/environment/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/__init__.py).
  - Created 5 deterministic offline JSON fixtures in `tests/fixtures/chirps/` and loader in `tests/fixtures/chirps_fixtures.py`.
  - Created offline unit test suites in `tests/unit/test_chirps_types.py`, `tests/unit/test_chirps_aggregation.py`, `tests/unit/test_chirps_pipeline.py` (49 unit tests passing; 838 full repository unit tests passing).
  - Created live Earth Engine integration test suite in `tests/integration/test_chirps_integration.py` (3 live tests passing against `bharatsahayak-v2`).


- **Phase 3A Step 3 — Earth Engine Collection Ingestion & Adapter Boundary (🟢 COMPLETE & SEALED — Commit `74fd372` — 29 Unit Tests + 3 Live Integration Tests):**
  - Created Earth Engine ERA5-Land adapter module [`app/environment/era5.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/era5.py):
    - Queries `ECMWF/ERA5_LAND/DAILY_AGGR` collection over parcel geometry (`create_analysis_region`) across $[E-89, E+1)$.
    - Selects 4 target bands: `temperature_2m`, `total_precipitation_sum`, `volumetric_soil_water_layer_1`, `runoff_sum`.
    - Implements Option A spatial reduction: unweighted zonal mean reduction (`ee.Reducer.mean()`) at nominal scale $11132\text{ m}$.
    - Captures server-side errors into structured `EarthEngineError` result envelopes without leaking exceptions.
  - Created pure normalization and root orchestration module [`app/environment/pipeline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/pipeline.py):
    - `normalize_raw_era5_record`: Converts Kelvin to Celsius ($T - 273.15$), meters to millimeters ($P \times 1000.0$, $R \times 1000.0$), preserves topsoil moisture fraction in $[0.0, 1.0]$, enforces strict missing != zero semantics, rejects negative precipitation/runoff artifacts without clamping.
    - `analyze_era5_land`: Orchestrates spatial validation, Tier 1 retrieval, Tier 2 normalization, dynamic publication data lag computation (`latest_available_date`, `data_lag_days`), Step 2 multi-window statistical aggregation (7d, 30d, 90d), and assembling authoritative `ERA5LandAnalysis` payload (`pipeline_version="3.0.0"`).
  - Updated public API exports in [`app/environment/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/__init__.py).
  - Added comprehensive offline test suite in [`tests/unit/test_environment_pipeline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/unit/test_environment_pipeline.py) (29 tests passing; 79 total environmental subsystem tests passing; 788 full repository unit tests passing).
  - Added live Earth Engine integration test suite in [`tests/integration/test_era5_land_integration.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/integration/test_era5_land_integration.py) (3 live tests passing against `bharatsahayak-v2`).

- **Phase 3A Step 2 — Pure Math & Window Aggregation Engine (🟢 COMPLETE — 19 Tests):**
  - Created pure mathematical window aggregation module [`app/environment/aggregation.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/aggregation.py) and public exports in [`app/environment/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/__init__.py).
  - Implemented `aggregate_window_statistics`:
    - Computes inclusive temporal windows: $\text{window\_start} = \text{window\_end} - (\text{window\_days} - 1)$ for 7-day ($E-6$), 30-day ($E-29$), and 90-day ($E-89$) envelopes.
    - Defensively validates input observations and rejects duplicate `observation_date` entries with `ValueError`.
    - Computes metric-level statistics (temperature mean/min/max, precipitation sum, soil water mean, runoff sum) over available non-null values while preserving distinct calendar availability (`days_available`).
    - Handles incomplete windows (computes from available observations) and empty windows (returns `days_available=0` with `None` metric values).
    - Preserves zero vs None distinction: observed 0.0 mm rainfall produces 0.0 mm total, while unavailable data produces `None`.
    - Guarantees order invariance: unordered or reversed inputs produce identical aggregation outputs.
  - Implemented `compute_environmental_window_suite`:
    - Standardized orchestrator generating the (recent 7d, recent 30d, recent 90d) tuple by delegating to `aggregate_window_statistics`.
  - Added comprehensive unit test suite in [`tests/unit/test_environment_aggregation.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/unit/test_environment_aggregation.py) with 19 tests passing (50 environmental tests passing total).
- **Phase 3A Step 1 — Domain Contracts & Deterministic Offline Fixtures (🟢 COMPLETE — 31 Tests):**
  - Created dedicated environment domain contract module [`app/environment/types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/types.py) and exports in [`app/environment/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/environment/__init__.py).
  - Implemented domain models:
    - `DailyEnvironmentalObservation`: Normalized daily meteorological & hydrological variables ($T_{^\circ\text{C}}$, $P_{\text{mm}}$, $\text{SW}_{\text{m}^3/\text{m}^3}$, $R_{\text{mm}}$) with explicit rejection of negative values ($\ge 0.0$) and preservation of missing fields as `None` ($\text{Missing} \ne 0.0$).
    - `EnvironmentalWindowStatistics`: 7-day, 30-day, and 90-day window aggregations with strict invariants (`days_available <= days_requested`, `is_complete == (days_available == days_requested)`, temperature bound checks).
    - `ERA5LandAnalysis`: Authoritative root domain model (`pipeline_version="3.0.0"`, dataset `ECMWF/ERA5_LAND/DAILY_AGGR`, spatial resolution $11.1\text{ km}$), integrating existing `AnalysisRegionMetadata`, `EarthEngineStatus`, and `EarthEngineError` without duplicate status enums.
  - Implemented 5 deterministic offline fixtures in `tests/fixtures/era5_land/` (`punjab_monsoon_90d.json`, `punjab_winter_dry_90d.json`, `lagged_partial_90d.json`, `negative_artifact_edge_case.json`, `no_data_empty.json`) and typed loader in `tests/fixtures/era5_fixtures.py`.
  - Implemented contract and fixture test suite in [`tests/unit/test_environment_types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/unit/test_environment_types.py) with 31 unit tests passing. Full test suite passing (740 tests passed, 0 failures).
- **Phase 3A ERA5-Land Reanalysis Architecture & Design Review (🟢 DESIGN SEALED / `DEC-018`):**
  - Conducted architectural, data-engineering, and scientific design review for incorporating meteorological and hydrological reanalysis context from Google Earth Engine.
  - Formulated and locked `DEC-018`:
    - Standardized on ECMWF ERA5-Land Daily Aggregated (`ECMWF/ERA5_LAND/DAILY_AGGR`, $\approx 11.1\text{ km}$ resolution).
    - Selected 4 core physical variables: `temperature_2m` ($K \to ^\circ\text{C}$), `total_precipitation_sum` ($m \to \text{mm}$), `volumetric_soil_water_layer_1` (0–7 cm topsoil moisture, $\text{m}^3/\text{m}^3$), and `runoff_sum` ($m \to \text{mm}$).
    - Established 3 retrospective observation windows: Recent 7-Day, 30-Day, and 90-Day envelopes.
    - Explicitly designed reanalysis publication lag tracking (`requested_end_date`, `latest_available_date`, `data_lag_days`).
    - Enforced data reliability invariants: missing precipitation/runoff is never zero ($\text{Missing} \ne 0.0\text{ mm}$); negative GEE packing artifacts are rejected rather than clamped.
    - Preserved strict non-agronomic boundary (pure physical measurements, no drought/heat stress/irrigation classifications in Phase 3A).
    - Designed 3-tier testing architecture utilizing deterministic offline JSON test fixtures.
  - Created canonical Phase 3 specification in `docs/phases/PHASE_03_ADDITIONAL_AGRICULTURAL_ENVIRONMENTAL_DATA.md`.

### 🟢 Completed — Phase 2: Historical Satellite Intelligence (Subphases 2A–2D Complete & Sealed — `ebba070`)
- **Phase 2A Architecture & Design Review (🟢 COMPLETE & APPROVED / `DEC-012`, `DEC-013`, `DEC-014`):**
  - Conducted comprehensive architecture, data-engineering, and scientific review for historical comparative satellite intelligence.
  - Formulated and locked `DEC-012`: 3-year rolling operational historical horizon ($Y-1, Y-2, Y-3$) with Day-of-Year centered temporal windowing ($\text{Reference DOY} \pm 15\text{ days}$). Explicitly documented that DOY matching normalizes astronomical/calendar seasonality without claiming identical crop growth stage.
  - Formulated and locked `DEC-013`: Selected Option C (Annual Matched-Window Regional Observations). Formally defined the primary statistical observation unit as one annual matched-window regional NDVI value per represented historical year ($[\text{val}_{Y-1}, \text{val}_{Y-2}, \dots]$). Selected Historical Median NDVI as the primary baseline, and established the anomaly metrics suite: Absolute Departure (primary), Gated Relative % Departure ($\text{baseline} \ge 0.15$), and Gated Z-Score ($N_{\text{annual}} \ge 2, Y \ge 2, \sigma_{\text{annual}} \ge 0.02$). Framed departures strictly as "MVP empirical spectral-departure bands" without asserting crop health or disease diagnoses.
  - Formulated and locked `DEC-014`: Established the strongly typed `HistoricalNdviAnalysis` domain contract with explicit observation units (`historical_annual_observation_count`, `distinct_years_count`, `raw_qualifying_scenes_count`) and sufficiency guardrails ($N_{\text{annual}} \ge 2 \land Y \ge 2$). Defined universal result states: `success`, `insufficient_history`, `no_data`, and `error`. Replaced synthetic confidence scores with transparent empirical evidence.
  - Established materialization budget target of maximum 3 client-side `.getInfo()` calls.
  - Created canonical Phase 2 architecture record in `docs/phases/PHASE_02_HISTORICAL_SATELLITE_INTELLIGENCE.md`.
- **Phase 2B Historical Temporal Window & Seasonality Strategy (🟢 COMPLETE & SEALED / `DEC-015`):**
  - Conducted master architectural design review and sealed the Calendar-Date-Anchored Seasonal Windowing strategy.
  - Formalized the 31-day inclusive calendar window ($T_h \pm 15\text{ days}$) across the 3 historical target years ($Y-1, Y-2, Y-3$).
  - Established the **Cross-Calendar-Year Window Ownership Invariant**: historical seasonal windows crossing January 1 or December 31 are strictly owned by their target historical anchor year $Y_h$. All qualifying scenes within the continuous window belong entirely to the annual baseline for $Y_h$ without calendar-year data partitioning.
  - Formalized simple leap-year calendar correctness as a calendar problem rather than a phenology problem (mapping February 29 to February 28 in common historical years).
  - Confirmed strict UTC calendar-date basis and defined Earth Engine half-open boundary contract `[start_date, end_date + 1 day)`.
  - Created canonical Phase 2B design record with 18-case edge verification matrix in `docs/phases/PHASE_02B_TEMPORAL_WINDOW_SEASONALITY.md`.
- **Phase 2C Historical Satellite Collection & Annual Composite Strategy (🟢 COMPLETE & SEALED / `DEC-016` — `ba1ec1c`):**
  - Implemented independent annual sub-pipelines in [`app/satellite/historical.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical.py) for the bounded 3-year historical horizon ($Y-1, Y-2, Y-3$) across Phase 2B 31-day seasonal windows.
  - Reused exact Phase 1 Cloud Score+ quality gates (`COPERNICUS/S2_SR_HARMONIZED` linked with Cloud Score+ `cs_cdf >= 0.60`, scene cloud $<20\%$, and parcel `min_usable_coverage >= 0.70`).
  - Applied temporal recency sorting (newest-first) selecting up to 3 usable scenes per historical year.
  - Implemented per-scene NDVI calculation followed by pixel-wise median NDVI compositing (`ee.ImageCollection.median()`) and zonal statistical reduction (`calculate_ndvi_statistics`).
  - Preserved Earth Engine masked-pixel semantics (excluding masked pixels from reductions, never filling with artificial zeros).
  - Created comprehensive unit test suite in `tests/unit/test_satellite_historical_composite.py`.
- **Phase 2D Multi-Year Baseline & Anomaly Engine (🟢 COMPLETE & SEALED / `DEC-017` — `ebba070`):**
  - **Step 1 — Domain Contracts (`bdb8d69`):** Implemented strongly typed Pydantic models in [`app/satellite/types.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/types.py): `HistoricalNdviBaseline`, `HistoricalSufficiencyEvidence`, `SpectralDepartureBand`, `NdviAnomalyEvidence`, `HistoricalAnalysisStatus`, and `HistoricalNdviAnalysis` with invariant validation.
  - **Step 2 — Pure Statistical Engine (`ccafc6f`):** Implemented deterministic pure-Python statistical calculation engine in [`app/satellite/baseline.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/baseline.py) with zero Earth Engine dependencies: valid annual observation extraction, historical baseline derivation (median primary, arithmetic mean, population standard deviation with ddof=0, min, max), data sufficiency evaluation ($N_{\text{annual}} \ge 2 \land Y \ge 2$), absolute departure ($\Delta\text{NDVI}$), gated relative percentage departure ($\text{baseline} \ge 0.15$), gated standardized z-score ($N \ge 2, Y \ge 2, \sigma \ge 0.02$), and empirical non-agronomic spectral departure classification.
  - **Step 3 — Root Integration & Composition (`ebba070`):** Implemented root domain composition function `build_historical_ndvi_analysis(...)` in [`app/satellite/historical_analysis.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/historical_analysis.py), joining Phase 1 current evidence with pre-materialized Phase 2C historical observations, enforcing current-error priority, and constructing `HistoricalNdviAnalysis` with `pipeline_version="2.0.0"`. Exported all contracts and entry points in [`app/satellite/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/__init__.py).
  - **Verification:** 18 integration tests passed in [`tests/unit/test_satellite_historical_baseline_integration.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/unit/test_satellite_historical_baseline_integration.py), 700 satellite subsystem tests passed, 709 full unit tests passed, 0 failures.

### 🟢 Completed — Phase 1: Earth Engine Foundation (Subphases 1A–1K Complete & Sealed — `60f8d90`)
- **Phase 1A Architecture & Integration Design (🟢 COMPLETE):**
  - Selected and documented Option C (Layered Tool Contract with Dedicated Earth Engine Module) as `DEC-004` in `docs/DECISION_LOG.md` and `docs/ARCHITECTURE.md`.
  - Defined detailed 1A–1K sub-roadmap in `docs/MASTER_ROADMAP.md` and `docs/phases/PHASE_01_EARTH_ENGINE_FOUNDATION.md`.
- **Phase 1B Local Environment & Verification (1B.1–1B.10 🟢 COMPLETE):**
  - **1B.1 Local Environment Inspection:** Inspected environment (`uv` 0.11.26, Python 3.13.14, `google-adk` 2.2.0, project constraint `>=3.11,<3.14`). Verified Earth Engine API was initially not installed.
  - **1B.2 Dependency Management Decision:** Recorded `DEC-005` selecting canonical `uv add earthengine-api` workflow for manifest/lockfile synchronization, reproducible resolution, and consistent project toolchain.
  - **1B.3 Add Earth Engine API:** Installed `earthengine-api` 1.7.43, updating `pyproject.toml` and `uv.lock`. Successfully verified local Python import (`import ee`).
  - **1B.4 Lockfile Verification:** Resolved dependency graph and confirmed clean `git diff --check` (Windows CRLF line-ending warnings only).
  - **1B.5 Authentication:** Completed interactive local Earth Engine developer authentication workflow (`DEC-006`) without recording or exposing any credentials, tokens, or credential contents.
  - **1B.6 Initialization:** Successfully initialized Earth Engine with project `bharatsahayak-v2` (`ee.Initialize(project='bharatsahayak-v2')`) and verified minimal query (`ee.Number(1).getInfo() -> 1`).
  - **1B.7 Sentinel-2 Connectivity & Query Bounding:** Executed bounded catalog test query on `COPERNICUS/S2_SR_HARMONIZED` using representative farmland test fixture near Ludhiana, Punjab (coordinate `[75.7196, 30.9157]`, Aug 2026, clouds < 20%) returning 1 image. Documented crucial engineering lesson: For BharatSahayak operational queries, apply spatial and temporal bounds before expensive Earth Engine evaluation wherever possible, reducing unnecessary server-side computation and quota usage.
  - **1B.8 Credential Safety Check:** Verified clean `git status`, `.gitignore` coverage (`.env`, `.venv`, `.adk`, `*.env`), zero repository credential files outside `.venv`, and zero tracked secrets via `git ls-files`.
  - **1B.9 Documentation:** Recorded verified Phase 1B facts across project changelog, roadmap, and phase records.
  - **1B.10 Git Checkpoint:** Checkpointed verified Phase 1B baseline (`13e5aa9`).
- **Phase 1C Earth Engine Connectivity & Result Contract (1C.1–1C.8 🟢 COMPLETE):**
  - **1C.1 Minimal Server Calculation:** Verified `ee.Number(42).getInfo() -> 42` against project `bharatsahayak-v2`.
  - **1C.2 Intentional Failure & Error Mapping:** Queried invalid asset `NON_EXISTENT/INVALID_ASSET_12345`; verified Earth Engine Python SDK translated the underlying API error into `ee.EEException`.
  - **1C.3 Zero-Data Verification:** Executed valid Sentinel-2 query with pre-deployment dates (`1990-01-01` to `1990-01-02`) returning `image_count=0` without exception, confirming distinct `NO_DATA` operational state.
  - **1C.4 / 1C.5 Architectural Boundary:** Defined structured result contract separating raw Earth Engine SDK exceptions from application-level contracts (`success`, `no_data`, `error`).
  - **1C.6 Pydantic Result Contract:** Created `app/satellite/__init__.py` and `app/satellite/types.py` defining `EarthEngineResult` (`status`, `dataset`, `image_count`, `data`, `error`), `EarthEngineError` (`type`, `message`), and `EarthEngineStatus` (`Literal["success", "no_data", "error"]`) with non-negative validation on `image_count`. Created `tests/unit/test_satellite_types.py` (6 unit tests passed).
  - **1C.7 Live Integration Testing:** Created `tests/integration/test_earth_engine_connectivity.py` validating 3 real Earth Engine behaviors against live APIs (3 integration tests passed, 0 skipped, 6 non-blocking framework warnings).
  - **1C.8 Documentation & Checkpoint:** Recorded Phase 1C verification facts across project documentation (`ff68be7`).
- **Phase 1D Geographic Region Definition (Subphases 1D.1–1D.3 🟢 COMPLETE):**
  - **1D.1 Geographic Analysis Region Strategy (`DEC-007`):** Formulated and documented `DEC-007` in `docs/DECISION_LOG.md`, establishing the decoupled two-stage geographic modeling strategy: `FarmerLocation` (stored as `latitude`, `longitude` via GPS, search, or map-tap without requiring manual coordinate typing or polygon drawing) $\rightarrow$ `Region Resolution` $\rightarrow$ `AnalysisRegion` (circular buffer with default 100 m radius for Sentinel-2 regional aggregation). Documented approximate area limitations (never exact cadastral boundary), internal non-configurability in MVP, reusability for multi-temporal historical analysis, and forward compatibility with future precise field polygon drawing (Phase 9).
  - **1D.2 Geographic Geometry Helper Implementation & Verification (`DEC-007`):** Created `app/satellite/geometry.py` implementing `create_analysis_region(latitude, longitude, radius_m=100.0) -> ee.Geometry` with validation for latitude [-90, 90], longitude [-180, 180], radius > 0, and rejection of invalid/non-finite types. Exported `create_analysis_region` and `DEFAULT_ANALYSIS_RADIUS_M` in `app/satellite/__init__.py`. Created and passed 35 unit tests in `tests/unit/test_satellite_geometry.py`. Confirmed client-side geometry proxy instantiation without server-side calls or `.getInfo()`.
  - **1D.3 Live Earth Engine Region Query & Verification (`DEC-007`):** Verified `create_analysis_region()` in live Earth Engine Sentinel-2 queries in `tests/integration/test_earth_engine_connectivity.py` (Ludhiana fixture `[75.7196, 30.9157]`, 100 m radius; Aug 2026 clouds < 20% returned `image_count=1`; pre-Sentinel-2 dates Jan 1990 returned `image_count=0`). All 5 live integration tests passed. Documented limitations (`d04a60f`).
- **Phase 1E Sentinel-2 Data Pipeline & Observation Quality (🟢 COMPLETE / DEC-008, DEC-010):**
  - **1E.1 Sentinel-2 Imagery Selection Pipeline (`DEC-008`):** Implemented `app/satellite/sentinel2.py` with `get_sentinel2_collection()`, `select_most_recent_sentinel2_image()`, `get_most_recent_sentinel2_image()`, and `resolve_date_range()`. Standardized on `COPERNICUS/S2_SR_HARMONIZED` with `AnalysisRegion` spatial bounding, configurable lookback (default 30 days), and scene cloud filtering (`CLOUDY_PIXEL_PERCENTAGE < 20%`). Sorted candidates descending (newest-first) and selected the most recent usable observation. Created `Sentinel2ImageMetadata` model and updated `EarthEngineResult` contracts.
  - **1E.2 Observation Quality via Cloud Score+ (`DEC-010`):** Implemented pixel-level quality filtering using Google Earth Engine Cloud Score+ S2_HARMONIZED V1 (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`) linked via `linkCollection(cs_plus, ["cs_cdf"])`. Applied `CLEAR_THRESHOLD = 0.60` (`cs_cdf >= 0.60`) quality masking (`mask_observation_quality()`) and calculated parcel-level usable coverage (`calculate_usable_coverage()`) inside the 100m circular `AnalysisRegion` using `ee.Reducer.mean()` on the binary mask. Enforced `MIN_USABLE_COVERAGE = 0.70`, selecting the newest qualifying observation and returning structured `status="no_data"` when coverage is insufficient. Extended `Sentinel2ImageMetadata` with `usable_coverage_percentage`, `clear_threshold`, and `quality_band`. Created `tests/unit/test_satellite_observation_quality.py` (20 tests passed; 190 total unit tests passed). Added 4 live integration tests in `tests/integration/test_earth_engine_connectivity.py` (`c8d1721`).
- **Phase 1F NDVI Calculation (🟢 COMPLETE / DEC-009):**
  - **1F.1 NDVI Band Mathematics & Module Implementation (`DEC-009`):** Implemented `app/satellite/ndvi.py` with `calculate_ndvi(image, region=None, nir_band="B8", red_band="B4", band_name="NDVI") -> ee.Image` and `compute_ndvi` alias. Applies normalized difference ($\text{NDVI} = \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4}}$) via native `image.normalizedDifference(["B8", "B4"]).rename("NDVI")`. Automatically clips raster extent to the `AnalysisRegion` (`ee.Geometry`) circular buffer. Preserves invalid/masked pixels without inventing zeros; avoids manual reflectance scaling; preserves active scene-level `<20%` cloud filter. Exported in `app/satellite/__init__.py`. Verified with 29 unit tests in `tests/unit/test_satellite_ndvi.py` and 3 live integration tests in `tests/integration/test_earth_engine_connectivity.py` (`64dc820`).
- **Phase 1G Regional NDVI Statistics (🟢 COMPLETE):**
  - **1G.1 Regional Reduction & Result Contract:** Implemented `calculate_ndvi_statistics(ndvi_image, region, scale=10.0, band_name="NDVI") -> EarthEngineResult` and `compute_ndvi_statistics` alias in `app/satellite/ndvi.py`. Implemented `NdviRegionalStatistics` (`mean`, `median`, `min`, `max`, `valid_pixel_count`) and `SatelliteRegionalStatistics` alias in `app/satellite/types.py` with strict Pydantic bounds $[-1.0, 1.0]$. Uses single combined server-side reducer (`ee.Reducer.mean().combine(median).combine(min).combine(max).combine(count)`). Verified live reducer dictionary keys. Preserved strict no-data semantics ($\text{NULL} \neq 0.0$) and remote error encapsulation. Exported in `app/satellite/__init__.py`. Verified with 13 unit tests in `tests/unit/test_satellite_ndvi_statistics.py` and 3 live integration tests in `tests/integration/test_earth_engine_connectivity.py` (`87903f0`).
- **Phase 1H Regional NDVI Orchestration Pipeline (🟢 COMPLETE / DEC-011):**
  - **1H.1 Architecture & Domain Contracts (`DEC-011`):** Formulated and locked `DEC-011` establishing the single-authoritative-observation lineage and layered typed payload: `RegionalNdviAnalysis` composed of `Sentinel2ImageMetadata`, `ObservationQualityEvidence`, `ObservationFreshness`, `AnalysisRegionMetadata`, and `NdviRegionalStatistics`.
  - **1H.2 Orchestration Pipeline Implementation:** Created `app/satellite/pipeline.py` implementing `analyze_regional_ndvi(...)`. Enforces synchronous input validation, single candidate collection pass, exactly one `collection.first()` selection, identical Cloud Score+ quality masking (`cs_cdf >= 0.60`), NDVI band math, zonal statistical reduction, mathematical invariant validation ($\text{min} - 10^{-6} \le \text{median}/\text{mean} \le \text{max} + 10^{-6}$), UTC calendar freshness derivation, and composite domain payload construction.
  - **1H.3 Comprehensive Verification:** Created 102 unit tests in `tests/unit/test_satellite_pipeline.py`, 11 type unit tests in `tests/unit/test_satellite_types.py`, and 4 live integration tests in `tests/integration/test_earth_engine_connectivity.py`. Full test suite: **382 passed** (359 unit + 23 live integration). Checkpointed in `4f79d2a`.
- **Phase 1I Integration Boundary Verification (🟢 COMPLETE):**
  - Conducted full read-only architectural audit of layer decoupling, unidirectional dependency flow ($\text{Agent} \rightarrow \text{MCP} \rightarrow \text{Satellite} \rightarrow \text{EE}$), strict Earth Engine object encapsulation (`ee.Image`/`ee.Geometry` never cross MCP), and serialization rules (`result.model_dump(mode="json")`).
  - Defined future `get_regional_satellite_analysis` tool signature as DESIGN ONLY (implementation deferred to Phase 6).
  - Documented unresolved location privacy and coordinate telemetry policy. Zero code modifications performed.
- **Phase 1J Final Documentation Consolidation (🟢 COMPLETE):**
  - Created canonical, comprehensive Phase 1 foundation record in `docs/phases/PHASE_01_EARTH_ENGINE_FOUNDATION.md` documenting milestones 1A through 1J, architectural invariants, verified test counts, and deferred roadmaps.
- **Phase 1K Verification & Final Git Checkpoint (🟢 COMPLETE):**
  - Checkpointed verified, audited Phase 1 foundation documentation with clean working tree (`60f8d90`).
- **Strict Scope Boundaries Maintained:**
  - FastMCP tool registration remains deferred to Phase 6.
  - Gemini prompt reasoning, multi-temporal time-series, historical baseline anomaly detection, NDWI, Dynamic World LULC, and UI map components remain deferred to subsequent phases.

### 🟡 Planned Phases
- **Phase 3 (Environmental Data Sources):** Pluggable provider architecture for live meteorological forecasts and regional soil databases.
- **Phase 4 (Data Fusion):** Normalization and fusion of satellite NDVI, weather indicators, and farmer profile context.
- **Phase 5 (Gemini Agricultural Reasoning):** Enhanced prompt engineering for Gemini 2.5 Flash interpreting satellite vigor and localized agronomic advisories.
- **Phase 6 (MCP / Agent Integration):** Upgrading MCP server tools from static catalog lookups to live satellite and weather service backends.
- **Phase 7 (End-to-End Farmer Workflow):** Map-based farm onboarding, location resolution, and expanded multilingual conversation flows.
- **Phase 8 (Testing & Evaluation):** India-specific multi-turn agricultural evaluation dataset and comprehensive reliability test suites.
- **Phase 9 (UI / UX):** Interactive map interface, NDVI health heatmaps, and structured farmer advisory cards.
- **Phase 10 (Deployment):** Vertex AI Reasoning Engine / Cloud Run provisioning and OpenTelemetry monitoring in GCP project `bharatsahayak-v2`.
- **Phase 11 (Final Submission):** End-to-end video walkthrough, documentation polishing, and hackathon submission.

---

## [0.2.0] — Phase 0: Project Foundation & Baseline Audit

### 🟢 Added
- **Permanent Documentation System:**
  - `docs/MASTER_ROADMAP.md` — High-level 11-phase progressive roadmap.
  - `docs/ARCHITECTURE.md` — Complete audit and system architecture specification documenting current implementation vs. planned satellite flow.
  - `docs/DECISION_LOG.md` — Permanent decision records (`DEC-001`, `DEC-002`, `DEC-003`) and foundational principles.
  - `docs/FUTURE_BACKLOG.md` — Structured catalog of deferred satellite, weather, UI, and intelligence features with decoupling rules.
  - `docs/CHANGELOG.md` — Chronological release and milestone tracking.
  - `docs/phases/PHASE_00_PROJECT_FOUNDATION.md` — Comprehensive Phase 0 execution and audit record.

### 🟢 Changed / Documented
- Audited repository baseline (`origin/bharatsahayak-v2` at commit `e0fcc29`).
- Formally recorded that current MCP tools use static catalog/rule data and are scheduled for live satellite/API upgrades in Phase 6.
- Established the core architectural principle: *"Ask the farmer for the easiest human-understandable input and derive technical geographic information from it where possible."*

---

## [0.1.0] — Current V2 Baseline (Inherited from `e0fcc29`)

### 🟢 Implemented Functionality
- **Multi-Agent Workflow Graph:**
  - Built on Google ADK 2.0 with directed graph transitions between `START`, `security_checkpoint`, `load_farmer_profile`, `orchestrator`, `hitl_checkpoint`, and `format_final_output`.
  - Four specialized advisors: `farming_advisor`, `weather_advisor`, `gov_schemes_advisor`, and `crop_disease_advisor` using Gemini 2.5 Flash.
- **Security Checkpoint & Guardrails:**
  - Regex PII redaction for Indian Aadhaar numbers, 10-digit mobile numbers, and email addresses.
  - Prompt injection keyword detection and sensitive financial credentials (bank PINs, passwords) blocking.
  - Structured audit logging to session state and `sys.stderr`.
- **Stateful Farmer Profile & Memory:**
  - Extractor for Indian states and major cities (English and Devanagari).
  - Crop entity extraction for common Indian staples and cash crops.
  - Farm acreage regex parser.
  - Dynamic language detection supporting English and Hindi.
- **Human-in-the-Loop (HITL) Season Interception:**
  - `@node(rerun_on_resume=True)` checkpoint that pauses on missing sowing season (`Kharif`, `Rabi`, `Zaid`) via `RequestInput(interrupt_id="more_info")` with multilingual Hindi/English clarification prompts.
  - Resumes execution seamlessly from user response without state loss.
- **Local Model Context Protocol (MCP) Server:**
  - FastMCP server (`app/mcp_server.py`) running over `stdio`.
  - Exposes `get_weather_advisory`, `get_crop_disease_info`, `search_government_schemes`, and `calculate_farming_profitability` (using static rules and catalog lookups for Punjab, Karnataka, and fallbacks).
- **Test Suite:**
  - Unit tests for intelligence, location extraction, and dictionary parsing (`tests/unit/test_intelligence.py`).
  - Integration tests for multi-turn conversations, HITL resumes, and security warnings (`tests/integration/test_agent.py`).
  - Agent Runtime app integration tests (`tests/integration/test_agent_runtime_app.py`).
- **Cloud Infrastructure Scaffolding:**
  - Terraform configurations for Vertex AI Reasoning Engine, GCS telemetry bucket, BigQuery completions view, and IAM roles (`deployment/terraform/single-project/`).
