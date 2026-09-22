# BharatSahayak V2 — Architectural Decision Log (ADR)

> **Permanent record of architectural, data engineering, and product design decisions.**  
> *Baseline Branch: `bharatsahayak-v2` | Project ID: `bharatsahayak-v2`*

---

## 📖 Guiding Architectural Principles

1. **Human-Centric Abstraction:**
   > *"Ask the farmer for the easiest human-understandable input and derive technical geographic information from it where possible."*  
   > Never expose raw GIS complexities (EPSG projections, latitude/longitude float coordinates, multi-band raster matrices) to end-users.
2. **Lean Statistical Distillation Before LLM Injection:**
   > Convert heavy spatial raster tensors into standardized, interpretable summary statistics (mean, median, min, max, percentiles) and qualitative health categories before feeding context to Gemini.
3. **Pluggable & Decoupled Data Providers:**
   > Satellite imagery, meteorological services, and soil data sources must be implemented behind clean provider interfaces so new datasets can be introduced without disrupting existing agent tools or workflows.
4. **Safety & Privacy First:**
   > All farmer interactions must pass through deterministic privacy filters (scrubbing PII like Aadhaar, mobile numbers, and bank details) before hitting external APIs or cloud models.

---

## 📜 Decision Records

### DEC-001: Start Satellite Intelligence with Copernicus Sentinel-2 + NDVI Before Dynamic World

- **Decision ID:** `DEC-001`
- **Date / Context:** Phase 0 Baseline Establishment (BharatSahayak V2 Initiation)
- **Decision:** Begin satellite intelligence implementation with Copernicus Sentinel-2 Level-2A (Bottom of Atmosphere / Surface Reflectance) imagery to compute the Normalized Difference Vegetation Index (NDVI), rather than making Dynamic World Land Use/Land Cover (LULC) the primary or initial dependency.
- **Options Considered:**
  1. *Option A:* Immediate integration of Dynamic World (10m near-real-time LULC) alongside Sentinel-2, Landsat, and MODIS simultaneously.
  2. *Option B (Chosen):* Sentinel-2 Level-2A surface reflectance with standard NDVI computation as the foundational satellite layer; treat Dynamic World, NDWI, and other collections as pluggable future additions.
  3. *Option C:* Use pre-computed MODIS 250m NDVI products.
- **Chosen Option:** Option B — Sentinel-2 MSI Surface Reflectance + NDVI.
- **Why Chosen:**
  - Sentinel-2 provides 10m spatial resolution across visible (Red / B4) and Near-Infrared (NIR / B8) bands, which is essential for smallholder Indian farm plots (often 0.5 to 3 acres). MODIS (250m resolution) is far too coarse for individual smallholder fields.
  - NDVI is the global standard, proven, and scientifically unambiguous index for measuring photosynthetic activity, vegetation vigor, and crop density.
  - Dynamic World is highly effective for land-cover classification (e.g. distinguishing crops vs built-up vs trees), but does not directly quantify intra-field crop health or vegetative stress in the way calibrated NDVI does.
- **Advantages:**
  - High spatial fidelity (10m per pixel) suitable for small farms.
  - Straightforward mathematical formula ($\frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$) supported natively in Earth Engine with cloud masking (`QA60` / SCL).
  - Fast execution with predictable compute latency in Earth Engine reducers.
- **Disadvantages:**
  - Cloud cover during peak monsoon season (Kharif) requires robust cloud-masking and temporal compositing.
  - Does not provide instant land-use classification metadata out-of-the-box (requires separate mask or manual user confirmation of farm boundaries).
- **Complexity:** Moderate (standard Earth Engine image collection filtering and reducer operations).
- **Reliability / Data-Quality Implications:** High data quality; Level-2A provides atmospherically corrected surface reflectance.
- **Cost / Quota Implications:** Earth Engine compute units (EECUs) are well within free/standard research quotas for zonal point/polygon reductions.
- **Hackathon Value:** Demonstrates strong technical mastery of Earth Observation (EO) data and real-world AI agent integration.
- **Interview / Engineering Value:** Demonstrates disciplined MVP scoping, domain-appropriate resolution selection (10m vs 250m), and avoiding premature over-engineering.
- **Deferred Alternatives:** Dynamic World LULC, NDWI (Normalized Difference Water Index), EVI, and Landsat thermal bands deferred to Phase 3 / Future Backlog.
- **Future Upgrade Impact:** Satellite data layer will be designed with a `SatelliteDataProvider` interface so Dynamic World can be added cleanly as an optional enrichment layer in Phase 3/4.

---

### DEC-002: Use Regional NDVI Summary Statistics Initially (Mean, Median, Min, Max); Defer Time Series & Anomaly Baselines

- **Decision ID:** `DEC-002`
- **Date / Context:** Phase 0 Baseline Establishment (Earth Engine & Multi-Agent Interface Design)
- **Decision:** Extract and feed regional summary statistics—specifically **mean**, **median**, **min**, and **max** NDVI—for the farmer's land parcel to the LLM agent. Deliberately defer historical multi-year NDVI time-series charting, historical baseline modeling, and temporal anomaly detection to future iterations.
- **Options Considered:**
  1. *Option A:* Build a complete 3-year historical NDVI time-series engine with seasonal baseline deviation and automated anomaly alerting in the initial release.
  2. *Option B (Chosen):* Compute instantaneous zonal statistics (mean, median, min, max, and cloud score) for the most recent valid satellite composite over the farm area; defer multi-temporal trend analysis.
  3. *Option C:* Stream raw pixel raster grids or geotiff images directly to Gemini Multimodal.
- **Chosen Option:** Option B — Zonal summary statistics (mean, median, min, max).
- **Why Chosen:**
  - Keeps token context concise, deterministic, and highly structured for Gemini 2.5 Flash reasoning.
  - Mean/Median indicates overall crop health and vigor; Min/Max highlights intra-field variability (e.g. identifying localized pest infestation or waterlogging spots where min is significantly lower than median).
  - Historical multi-year time-series analysis requires extensive temporal image compositing, seasonal alignment algorithms, and complex caching to avoid Earth Engine query timeouts during real-time chat sessions.
- **Advantages:**
  - Sub-second to 2-second Earth Engine reduction latency.
  - Clean, structured JSON output easily ingested by Pydantic tool models and LLM system prompts.
  - Provides immediate, high-value insights (overall vigor + intra-plot uniformity).
- **Disadvantages:**
  - Does not yet tell the farmer if today's NDVI is higher or lower than the same week last year.
- **Complexity:** Low to Moderate.
- **Reliability / Data-Quality Implications:** Very high; zonal reducers aggregate out single-pixel sensor noise.
- **Cost / Quota Implications:** Extremely low payload size and minimal Earth Engine processing overhead.
- **Hackathon Value:** Delivers a reliable, snappy, and grounded agent demo without risking live demo timeouts caused by heavy time-series aggregations.
- **Interview / Engineering Value:** Shows clear understanding of latency budgets in real-time conversational agent architectures.
- **Deferred Alternatives:** Multi-year temporal graphs, seasonal moving averages, and automated z-score anomaly detection deferred to `FUTURE_BACKLOG.md`.
- **Future Upgrade Impact:** The statistical dictionary schema will include an optional `temporal_comparison` block, enabling seamless future addition without breaking tool schemas.

---

### DEC-003: Implement Map-Based Farm Location with Search & Geolocation Assistance; Never Force Manual Coordinates

- **Decision ID:** `DEC-003`
- **Date / Context:** Phase 0 Baseline Establishment (Farmer UX & Geographic Grounding)
- **Decision:** Design the farmer-facing location mechanism around an interactive map interface with:
  1. Browser GPS "Use My Current Location" button.
  2. Village / Town / District / PIN code text search.
  3. Visual map pin-drop and boundary adjustment.
  Explicitly prohibit any UX requirement forcing farmers to manually find, format, or type latitude/longitude coordinates.
- **Options Considered:**
  1. *Option A:* Command-line / chat prompt asking the farmer: "Please enter your latitude and longitude."
  2. *Option B (Chosen):* Human-friendly map UI + reverse-geocoded place search that extracts coordinates under the hood.
  3. *Option C:* Pure state/district level dropdowns without spatial coordinate resolution.
- **Chosen Option:** Option B — Interactive Map + Place Search + Geolocation Assistance.
- **Why Chosen:**
  - Rural Indian farmers understand their village, panchayat, landmarks, and farm boundaries, but rarely know their geographic latitude and longitude coordinates in decimal degrees.
  - Dropdowns at state/district level (Option C) lack sufficient spatial resolution for 10m Sentinel-2 field analysis.
  - Asking for manual coordinates (Option A) creates immense friction and causes user drop-off.
- **Advantages:**
  - Frictionless onboarding: one tap to detect location when standing on the field.
  - Accurate spatial point/bounding polygon generation for Earth Engine querying.
  - Accessible to users across literacy levels through visual map recognition.
- **Disadvantages:**
  - Requires integrating map components (e.g. Leaflet / Mapbox / Google Maps API) and geocoding services in the UI phase.
- **Complexity:** Moderate.
- **Reliability / Data-Quality Implications:** Significantly increases location accuracy compared to pure text matching.
- **Cost / Quota Implications:** Minimal standard geocoding API usage; open-source OpenStreetMap / Nominatim or Google Maps Platform geocoding.
- **Hackathon Value:** Major differentiator in usability and visual impact during product demos.
- **Interview / Engineering Value:** Embodies user-first engineering principles and empathetic accessibility design for rural demographics.
- **Deferred Alternatives:** In Phase 0/1 testing, a mock/fallback coordinate resolver will allow test harness simulation while full map UI is built in Phase 9.
- **Future Upgrade Impact:** Enables future cadastral map overlay, KML/GeoJSON upload, and precise polygon drawing in Phase 9.

---

### DEC-004: Decouple Earth Engine Computation into a Dedicated Module Behind the MCP Capability Interface

- **Decision ID:** `DEC-004`
- **Date / Context:** Phase 1A Architecture & Integration Design (Earth Engine Integration Planning)
- **Decision:** Expose the satellite capability through the Model Context Protocol (MCP) tool contract, while delegating all Earth Engine initialization, image querying, cloud masking, band math, and zonal reduction to a dedicated Earth Engine module/service (Option C).
- **Options Considered:**
  1. *Option A (Monolithic MCP):* Embed all Earth Engine API initialization, geometry parsing, Sentinel-2 image collection filtering, NDVI math, and reducer logic directly inside `app/mcp_server.py`.
  2. *Option B (Standalone Satellite Service):* Build a completely independent satellite microservice without any MCP tool bindings, requiring agent orchestration to manage external HTTP endpoints.
  3. *Option C (Chosen — Layered Tool Contract + Dedicated Engine):* MCP exposes high-level capability tools (e.g. `get_farm_satellite_intelligence`), while a dedicated Earth Engine module performs domain-specific geospatial and Earth Engine computations.
- **Chosen Option:** Option C — Layered Tool Contract with Dedicated Earth Engine Module.
- **Architectural Flow:**
  ```text
  Farmer-Friendly Location (Search / Pin-drop / GPS)
          ↓
  Latitude / Longitude Coordinates
          ↓
  MCP Capability Interface (Tool Contract / Parameter Validation)
          ↓
  Dedicated Earth Engine Module / Service
          ↓
  Copernicus Sentinel-2 Collection (Harmonized Level-2A)
          ↓
  Cloud Masking (QA60 / SCL Filtering)
          ↓
  NDVI Calculation ((B8 - B4) / (B8 + B4))
          ↓
  Regional Statistics Reducer (Mean, Median, Min, Max)
          ↓
  Structured JSON Output Envelope
  ```
- **Why Chosen:**
  - **Separation of Responsibilities:** The MCP layer is responsible for defining tool schemas, input validation, execution timing, and communication protocol (stdio/SSE). It should not be cluttered with low-level Earth Engine client details, band indexing, or reducer dictionary parsing.
  - **Independent Testability:** Earth Engine logic can be thoroughly unit-tested and mocked without running an active MCP stdio sub-process or spinning up an ADK agent runner.
  - **Preserved Future Pluggability:** Datasets like Dynamic World, NDWI, SoilGrids, and weather feeds can be added into the dedicated data layer without breaking or rewriting the MCP tool signatures.
  - **Cleaner Technical Story & Interview Value:** Clear separation of concerns between agent communication protocol (MCP), model reasoning (ADK/Gemini), and scientific compute (Earth Engine).
- **Disadvantages / Trade-offs:**
  - Introduces an additional module boundary and internal interface contract.
  - Slightly higher initial file/module scaffolding compared to writing inline functions in `mcp_server.py`.
- **Complexity:** Moderate.
- **Reliability / Data-Quality Implications:** High; isolating Earth Engine logic enables dedicated retry handlers, client caching, and mockable unit tests for edge cases (zero pixels, heavy cloud cover, out-of-bounds coordinates).
- **Cost / Quota Implications:** Low; Earth Engine compute is isolated to lean statistical reductions executed only when the tool is invoked.
- **Hackathon Value:** Demonstrates production-grade multi-agent software engineering rather than hacky script concatenation.
- **Interview / Engineering Value:** Highlights deep understanding of clean architecture, interface isolation, and test-driven design in AI-agent ecosystems.
- **Deferred Alternatives & Features:**
  - NDVI time-series trends (deferred to Phase 2+).
  - Historical baseline & anomaly detection (deferred to Backlog).
  - Dynamic World LULC, NDWI, and other spectral indices (deferred to Phase 3).
  - Soil & meteorological multi-source data fusion (deferred to Phase 4).
- **Future Upgrade Impact:** When adding future satellite datasets (e.g. Dynamic World in Phase 3), new methods can be added to the dedicated Earth Engine service without altering the agent-facing MCP contract.

---

### DEC-005: Earth Engine Python API Dependency Management via uv Workflow

- **Decision ID:** `DEC-005`
- **Date / Context:** Phase 1B Local Earth Engine Environment, after completion of Subphase 1B.1 Environment Inspection
- **Decision:** Manage and install the official Google Earth Engine Python client library (`earthengine-api`) using the project's standard `uv` package management workflow via `uv add earthengine-api`.

- **Current Environment Findings:**
  - Package Manager: `uv` v0.11.26
  - Active Python Runtime: Python 3.13.14
  - Core ADK Runtime: `google-adk` v2.2.0
  - Earth Engine API: Not installed
  - Git Working Tree: Clean at time of inspection
  - Project Python Version Constraint: `>=3.11,<3.14`
  - Existing Dependency Manifests: `pyproject.toml` and `uv.lock`

- **Options Considered:**
  1. **Option A - Ad-hoc pip install:** Run `pip install earthengine-api` directly in the environment.
  2. **Option B - Manual manifest editing:** Manually add `earthengine-api` to `pyproject.toml` and run `uv sync`.
  3. **Option C - Chosen - Canonical uv workflow:** Run `uv add earthengine-api` so the project dependency declaration and lockfile are resolved together.

- **Chosen Option:** Option C - `uv add earthengine-api`

- **Why Chosen:**
  - **Reproducibility:** Keeps `pyproject.toml` and `uv.lock` synchronized.
  - **Dependency Resolution:** Lets `uv` resolve compatibility with the project's Python version and existing dependencies.
  - **Consistent Toolchain:** Preserves the dependency-management workflow already used by BharatSahayak V2.
  - **Developer Experience:** Avoids manual lockfile maintenance.
  - **Deployment:** Provides a reproducible dependency graph for later cloud deployment.

- **Trade-offs:**
  - Developers need to use `uv` rather than raw `pip`.
  - The lockfile must be updated whenever dependencies change.
  - Dependency resolution may expose conflicts that require investigation before implementation can continue.

- **Cost / Quota Implications:**
  - Adding the Python client library itself does not consume Earth Engine computation quota.
  - Earth Engine computation quota becomes relevant when the application actually executes Earth Engine operations in later subphases.

- **Hackathon Value:**
  - Keeps the prototype reproducible and easier to demonstrate on another environment.
  - Establishes a clean foundation for the planned Earth Engine integration.

- **Interview / Engineering Value:**
  - Demonstrates deliberate dependency management.
  - Demonstrates reproducible environment management.
  - Demonstrates separation between local setup and application implementation.

- **Implementation Status:** 🟢 COMPLETE (Installed in Phase 1B)

---

### DEC-006: Local Earth Engine Developer Authentication Workflow

- **Decision ID:** `DEC-006`
- **Date / Context:** Phase 1B Local Earth Engine Environment (Subphase 1B.5 Developer Authentication)
- **Decision:** Use interactive Earth Engine authentication (`earthengine authenticate` / ADC workflow) for local BharatSahayak V2 development and verification.

- **Options Considered:**
  1. **Option A (Chosen):** Interactive local authentication through developer's Google Cloud ADC account.
  2. **Option B:** Service account key JSON file stored locally.
  3. **Option C:** Static mocked credentials without real Earth Engine evaluation.

- **Why Chosen:**
  - **Simplicity:** Appropriate for local development without introducing unnecessary service account keys or IAM complexity prematurely.
  - **Security:** Zero credential files or secrets stored inside the source repository.
  - **Compatibility:** Works seamlessly with `ee.Initialize(project='bharatsahayak-v2')`.

- **Security Rule:**
  - No passwords, access tokens, refresh tokens, or credential files are ever committed to Git or embedded in application code.

- **Trade-offs:**
  - Requires interactive web browser login for the local developer session.
  - Dedicated production service account authentication will be evaluated in Phase 10 for Cloud Run / Vertex AI deployment.

- **Future Upgrade Impact:**
  - When moving to Google Cloud deployment in Phase 10, production service account authentication and Workload Identity will be evaluated.

- **Implementation Status:** 🟢 COMPLETE (Executed and verified in Phase 1B.5)

---

### DEC-007: Geographic Analysis Region Strategy

- **Decision ID:** `DEC-007`
- **Date / Context:** Phase 1D Geographic Region Definition (Subphase 1D.1 Conceptual Analysis & Strategy Selection)

#### 📸 Before Snapshot
Prior to DEC-007, Phase 1 established live Earth Engine client initialization (`DEC-005`, `DEC-006`) and application-level result contracts (`Phase 1C`, `EarthEngineResult`). However, the transformation from a human-selected farm location to an Earth Engine spatial geometry remained undefined. The system lacked an explicit abstraction separating user-facing location inputs from backend satellite analysis geometries.

#### 📜 Decision
Adopt a decoupled two-stage geographic modeling strategy separating **`FarmerLocation`** (user input) from **`AnalysisRegion`** (satellite compute geometry) resolved via an intermediate **Region Resolution** abstraction:

```text
FarmerLocation (Point: Latitude, Longitude)
        ↓
Region Resolution (Resolver / Buffer Engine)
        ↓
AnalysisRegion (Geometry: Circular Buffer / Future Polygon)
```

1. **Farmer-Facing Location Input:**
   - The farmer specifies location via:
     - Browser/Device GPS ("Use My Current Location"), OR
     - Searching a village / panchayat / area on a map, OR
     - Interactively tapping / dropping a pin on a map.
   - **Strict Negative Constraints:**
     - Do **NOT** require the farmer to manually enter latitude and longitude coordinates in decimal degrees or DMS.
     - Do **NOT** require the farmer to draw a field boundary polygon in the MVP.
2. **Location Storage:**
   - Store the original farmer-selected location simply as:
     - `latitude` (float)
     - `longitude` (float)
3. **Initial Analysis Region Strategy:**
   - Automatically convert the selected point into a **circular analysis region**.
   - **Default Radius:** Fixed at **100 meters** (approx. 3.14 hectares / ~7.7 acres area).
   - This radius is an engineering choice for MVP satellite processing, **not** a claim that 100 m represents the farmer's exact farm boundary.
4. **Internal Non-Configurability:**
   - The 100 m radius is an internal system constant / default and must **NOT** be exposed to the farmer as a technical or user-configurable setting in the MVP.
5. **Decoupled Architectural Abstraction:**
   - `FarmerLocation` and `AnalysisRegion` are maintained as distinct concepts and data structures.
   - The `Region Resolution` layer is designed so future resolvers can swap or extend the region generator (e.g., 100 m buffer, cadastral boundary lookup, or user-drawn polygon) without altering the downstream satellite processing pipeline.
6. **Reusability for Historical & Multi-Temporal Analysis:**
   - The generated `AnalysisRegion` geometry must be deterministic and reusable across both current and historical satellite observations. This ensures that when multi-temporal analysis is introduced, historical trends and delta comparisons are evaluated over the exact same geographic footprint.

#### 💡 Rationale (Why Chosen)
- **Minimizes Farmer UX Complexity:** Rural Indian farmers can easily identify their village or drop a pin on their field, but forcing polygon boundary drawing on mobile screens creates severe friction, gesture errors, and drop-off.
- **Eliminates Geospatial Jargon:** Farmers are never exposed to bounding boxes, coordinate reference systems (CRS/EPSG), or polygon topology rules.
- **Sufficient Spatial Sample for Sentinel-2:** Sentinel-2 Level-2A surface reflectance has a 10m spatial resolution per pixel. A 100 m circular buffer provides an area of $\pi \times 100^2 \approx 31,416\text{ m}^2$, covering approximately 300+ raw 10m pixels, providing a bounded multi-pixel sample for regional satellite statistics rather than relying on a single pixel, while keeping the analysis region computationally manageable.
- **Preserves Future Precision without Redesign:** Decoupling `FarmerLocation` from `AnalysisRegion` ensures that when precise field polygon drawing is added in Phase 9, the satellite ingestion and zonal reducer modules require zero architectural rework.

#### ⚖️ Trade-offs
- **Fixed Radius vs. Actual Acreage:** A 100 m buffer represents a standard local spatial envelope; it does not automatically scale to match a farmer's stated acreage (e.g. 0.5 acre vs. 10 acres) in the initial MVP.
- **Boundary Inexactness:** A circle generated around a pin drop may sample land beyond the farmer's specific parcel boundary.
- **Two-Stage Data Modeling:** Requires maintaining distinct types and resolution steps (`FarmerLocation` -> `AnalysisRegion`) rather than passing raw coordinates directly to Earth Engine reducers.

#### ⚠️ Limitations
- **Approximate Local Area Only:** The 100 m circular buffer is strictly an approximate local satellite observation area.
- **Mixed Land Cover Elements:** The analysis circle may encompass neighboring plots, field bunds, farm roads, irrigation channels, adjacent trees, or rural structures.
- **Never an Exact Cadastral Boundary:** The analysis region must **NEVER** be described, labelled, or presented to the farmer as their exact legal, cadastral, or revenue parcel boundary.

#### 🔮 Future Upgrade Impact
- **Phase 9 Field Polygon Drawing:** Seamlessly introduce interactive polygon drawing tools or KML/GeoJSON boundary uploads in the frontend. The region resolver will simply emit a polygon-based `AnalysisRegion` into the unchanged satellite pipeline.
- **Cadastral & Land Record Integration:** In future phases, state land registry records (e.g., Bhulekh / Bhoomi) can be resolved to official plot boundaries via the same `Region Resolution` interface.
- **Adaptive Acreage-Scaled Buffering:** The resolver can optionally compute radius as a function of reported farm acreage ($r = \sqrt{\frac{\text{acres} \times 4046.86}{\pi}}$) if requested in future backlog enhancements.
- **Multi-Temporal Trend Comparison:** Consistent `AnalysisRegion` definitions allow multi-year NDVI trend comparisons across an identical spatial mask.

#### 📊 Current Status & Next Steps
- **Status:** 🟢 **IMPLEMENTED & LIVE VERIFIED (Subphases 1D.1–1D.3 Complete)**
- **Verified Implementation (Phase 1D.2):**
  - Created [`app/satellite/geometry.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/geometry.py) implementing `create_analysis_region(latitude, longitude, radius_m=100.0) -> ee.Geometry`.
  - Validates `latitude ∈ [-90, 90]`, `longitude ∈ [-180, 180]`, `radius_m > 0`, and rejects non-finite/invalid types (NaN, inf, strings, None, booleans).
  - Constructs `ee.Geometry.Point([longitude, latitude]).buffer(radius_m)` in `[longitude, latitude]` order.
  - Default radius constant: `DEFAULT_ANALYSIS_RADIUS_M = 100.0` meters.
  - Exported `create_analysis_region` and `DEFAULT_ANALYSIS_RADIUS_M` in [`app/satellite/__init__.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/satellite/__init__.py).
  - Created and passed 35 unit tests in [`tests/unit/test_satellite_geometry.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/unit/test_satellite_geometry.py) (covering valid Punjab coordinates, custom radius, boundary coordinates, and comprehensive invalid inputs).
  - Local non-network verification confirmed: returned type is `<class 'ee.geometry.Geometry'>`, `isinstance(region, ee.Geometry)` is `True`, geometry name is `"Geometry"`, default radius constant is `100.0`, and zero server-side `.getInfo()` or network calls were executed.
- **Live Earth Engine Verification (Phase 1D.3):**
  - Integrated `create_analysis_region()` into live Sentinel-2 collection queries in [`tests/integration/test_earth_engine_connectivity.py`](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/integration/test_earth_engine_connectivity.py).
  - Verified successful query (`[75.7196, 30.9157]`, 100 m radius, `COPERNICUS/S2_SR_HARMONIZED`, August 2026, clouds < 20%) returned `image_count=1` mapped cleanly to `EarthEngineResult(status="success")`.
  - Verified no-data query (pre-Sentinel-2 dates Jan 1990) returned `image_count=0` mapped cleanly to `EarthEngineResult(status="no_data")`.
  - Verified test suite: all 5 live integration tests passed.
- **Documented Limitations:**
  - The 100 m circular region is an approximate local satellite observation area, **not** an exact farm boundary.
  - It may include neighboring plots, field bunds, roads, trees, water/irrigation channels, or structures.
  - Polygon/cadastral/adaptive region support remains future work.
- **Strict Scope Boundary Preserved:**
  - DEC-007 is a **region-definition and geometry-construction helper only**.
  - No Sentinel-2 data extraction or cloud masking pipeline is implemented yet (Subphase 1E).
  - No NDVI band math or summary statistics are implemented yet (Subphases 1F & 1G).
  - No historical analysis or baseline models are implemented yet.
  - No MCP tool integration is implemented yet.
  - No `client.py` exists yet.
  - No farmer-facing UI or map component is implemented yet.
  - No field polygon drawing is implemented yet.
- **Next Step:** Subphase 1E — Sentinel-2 Data Pipeline (collection selection, spatial/temporal filtering, QA60/SCL cloud masking).
