# BharatSahayak V2 — Project Changelog

> **Chronological record of architectural changes, feature implementations, and documentation milestones.**  
> *Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).*

---

## [Unreleased] — Planned Phases 1 through 11

### 🟡 In Progress — Phase 1: Earth Engine Foundation (Subphases 1A, 1B, 1C, 1D, 1E, 1F Complete; 1G Next)
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
  - **1B.10 Git Checkpoint:** Checkpointed verified Phase 1B baseline.
- **Phase 1C Earth Engine Connectivity & Result Contract (1C.1–1C.8 🟢 COMPLETE):**
  - **1C.1 Minimal Server Calculation:** Verified `ee.Number(42).getInfo() -> 42` against project `bharatsahayak-v2`.
  - **1C.2 Intentional Failure & Error Mapping:** Queried invalid asset `NON_EXISTENT/INVALID_ASSET_12345`; verified Earth Engine Python SDK translated the underlying API error into `ee.EEException`.
  - **1C.3 Zero-Data Verification:** Executed valid Sentinel-2 query with pre-deployment dates (`1990-01-01` to `1990-01-02`) returning `image_count=0` without exception, confirming distinct `NO_DATA` operational state.
  - **1C.4 / 1C.5 Architectural Boundary:** Defined structured result contract separating raw Earth Engine SDK exceptions from application-level contracts (`success`, `no_data`, `error`).
  - **1C.6 Pydantic Result Contract:** Created `app/satellite/__init__.py` and `app/satellite/types.py` defining `EarthEngineResult` (`status`, `dataset`, `image_count`, `data`, `error`), `EarthEngineError` (`type`, `message`), and `EarthEngineStatus` (`Literal["success", "no_data", "error"]`) with non-negative validation on `image_count`. Created `tests/unit/test_satellite_types.py` (6 unit tests passed).
  - **1C.7 Live Integration Testing:** Created `tests/integration/test_earth_engine_connectivity.py` validating 3 real Earth Engine behaviors against live APIs (3 integration tests passed, 0 skipped, 6 non-blocking framework warnings).
  - **1C.8 Documentation & Checkpoint:** Recorded Phase 1C verification facts across project documentation.
- **Phase 1D Geographic Region Definition (Subphases 1D.1–1D.3 🟢 COMPLETE):**
  - **1D.1 Geographic Analysis Region Strategy (`DEC-007`):** Formulated and documented `DEC-007` in `docs/DECISION_LOG.md`, establishing the decoupled two-stage geographic modeling strategy: `FarmerLocation` (stored as `latitude`, `longitude` via GPS, search, or map-tap without requiring manual coordinate typing or polygon drawing) $\rightarrow$ `Region Resolution` $\rightarrow$ `AnalysisRegion` (circular buffer with default 100 m radius for Sentinel-2 regional aggregation). Documented approximate area limitations (never exact cadastral boundary), internal non-configurability in MVP, reusability for multi-temporal historical analysis, and forward compatibility with future precise field polygon drawing (Phase 9).
  - **1D.2 Geographic Geometry Helper Implementation & Verification (`DEC-007`):** Created `app/satellite/geometry.py` implementing `create_analysis_region(latitude, longitude, radius_m=100.0) -> ee.Geometry` with validation for latitude [-90, 90], longitude [-180, 180], radius > 0, and rejection of invalid/non-finite types. Exported `create_analysis_region` and `DEFAULT_ANALYSIS_RADIUS_M` in `app/satellite/__init__.py`. Created and passed 35 unit tests in `tests/unit/test_satellite_geometry.py`. Confirmed client-side geometry proxy instantiation without server-side calls or `.getInfo()`.
  - **1D.3 Live Earth Engine Region Query & Verification (`DEC-007`):** Verified `create_analysis_region()` in live Earth Engine Sentinel-2 queries in `tests/integration/test_earth_engine_connectivity.py` (Ludhiana fixture `[75.7196, 30.9157]`, 100 m radius; Aug 2026 clouds < 20% returned `image_count=1`; pre-Sentinel-2 dates Jan 1990 returned `image_count=0`). All 5 live integration tests passed. Documented limitations (100 m circular region is an approximate local satellite observation area, not an exact farm boundary, and may sample neighboring plots, roads, trees, water, or structures; polygon/cadastral/adaptive region support remains future work).
- **Phase 1E Sentinel-2 Data Pipeline & Observation Quality (🟢 COMPLETE / DEC-008, DEC-010):**
  - **1E.1 Sentinel-2 Imagery Selection Pipeline (`DEC-008`):** Implemented `app/satellite/sentinel2.py` with `get_sentinel2_collection()`, `select_most_recent_sentinel2_image()`, `get_most_recent_sentinel2_image()`, and `resolve_date_range()`. Standardized on `COPERNICUS/S2_SR_HARMONIZED` with `AnalysisRegion` spatial bounding, configurable lookback (default 30 days), and scene cloud filtering (`CLOUDY_PIXEL_PERCENTAGE < 20%`). Sorted candidates descending (newest-first) and selected the most recent usable observation. Created `Sentinel2ImageMetadata` model and updated `EarthEngineResult` contracts.
  - **1E.2 Observation Quality via Cloud Score+ (`DEC-010`):** Implemented pixel-level quality filtering using Google Earth Engine Cloud Score+ S2_HARMONIZED V1 (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`) linked via `linkCollection(cs_plus, ["cs_cdf"])`. Applied `CLEAR_THRESHOLD = 0.60` (`cs_cdf >= 0.60`) quality masking (`mask_observation_quality()`) and calculated parcel-level usable coverage (`calculate_usable_coverage()`) inside the 100m circular `AnalysisRegion` using `ee.Reducer.mean()` on the binary mask. Enforced `MIN_USABLE_COVERAGE = 0.70`, selecting the newest qualifying observation and returning structured `status="no_data"` when coverage is insufficient. Extended `Sentinel2ImageMetadata` with `usable_coverage_percentage`, `clear_threshold`, and `quality_band`. Created `tests/unit/test_satellite_observation_quality.py` (20 tests passed; 190 total unit tests passed). Added 4 live integration tests in `tests/integration/test_earth_engine_connectivity.py` (16 total live EE tests passed in 40.34s; 219 total tests passed). Confirmed zero code changes required in `app/satellite/ndvi.py`.
- **Phase 1F NDVI Calculation (🟢 COMPLETE / DEC-009):**
  - **1F.1 NDVI Band Mathematics & Module Implementation (`DEC-009`):** Implemented `app/satellite/ndvi.py` with `calculate_ndvi(image, region=None, nir_band="B8", red_band="B4", band_name="NDVI") -> ee.Image` and `compute_ndvi` alias. Applies normalized difference ($\text{NDVI} = \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4}}$) via native `image.normalizedDifference(["B8", "B4"]).rename("NDVI")`. Automatically clips raster extent to the `AnalysisRegion` (`ee.Geometry`) circular buffer. Preserves invalid/masked pixels without inventing zeros; avoids manual reflectance scaling (cancels in normalized ratio); preserves active scene-level `<20%` cloud filter. Exported in `app/satellite/__init__.py`. Verified with 29 unit tests in `tests/unit/test_satellite_ndvi.py` and 3 live integration tests in `tests/integration/test_earth_engine_connectivity.py` (live Sentinel-2A scene from 2026-08-16 over Ludhiana fixture returned `ee.image.Image`, single band `["NDVI"]`, sampled valid values in $[-1.0, 1.0]$, pre-Sentinel-2 date range returned `no_data`, invalid band names raised `ee.EEException`). Full test suite: 146 passed. Documented limitations (reflectance index vs definitive agronomic diagnosis; approximate 100m observation circle).
- **Strict Scope Boundaries Maintained:**
  - `app/satellite/client.py` does **NOT** exist yet.
  - Regional NDVI summary statistics (1G), crop health classification thresholds, Dynamic World LULC, weather data fusion, crop health prediction, and farmer-facing UI workflows remain deferred to subsequent phases.

### 🟡 Planned Phases
- **Phase 1 (Earth Engine Foundation):** Local environment setup (1B), connectivity test (1C), geometry definition (1D), Sentinel-2 pipeline (1E), NDVI calculation (1F), regional statistics (1G), and reliability testing (1H).
- **Phase 2 (Satellite Intelligence):** Copernicus Sentinel-2 MSI surface reflectance querying, cloud masking, and NDVI regional summary statistics (mean, median, min, max).
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
