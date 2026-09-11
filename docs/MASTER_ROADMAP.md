# BharatSahayak V2 — Master Project Roadmap

> **Master roadmap and progressive implementation plan for BharatSahayak V2.**  
> *Last Updated: Phase 0 Foundation*  
> *Baseline Branch: `bharatsahayak-v2` | Commit: `e0fcc29` | GCP Project ID: `bharatsahayak-v2`*

---

## 🧭 Roadmap Overview & Status Legend

| Status Icon | Meaning | Definition |
| :--- | :--- | :--- |
| 🟢 **IMPLEMENTED** | Active & Implemented | Fully written, tested, and operational in current repository baseline. |
| 🟡 **PLANNED** | Scheduled Work | Approved architectural phase scheduled for implementation in upcoming phases. |
| 🔴 **IDEA** | Future Exploration | Conceptual enhancement deferred to post-MVP / future backlog. |

---

## 🗺️ Phases Summary

```mermaid
graph TD
    P0["Phase 0: Project Understanding & Documentation 🟢"] --> P1["Phase 1: Earth Engine Foundation 🟡"]
    P1 --> P2["Phase 2: Satellite Intelligence (Sentinel-2 + NDVI) 🟡"]
    P2 --> P3["Phase 3: Additional Agri & Environmental Data 🟡"]
    P3 --> P4["Phase 4: Multi-Source Data Fusion 🟡"]
    P4 --> P5["Phase 5: Gemini Agricultural Reasoning 🟡"]
    P5 --> P6["Phase 6: MCP & Agent Integration 🟡"]
    P6 --> P7["Phase 7: End-to-End Farmer Workflow 🟡"]
    P7 --> P8["Phase 8: Testing, Reliability & Security 🟡"]
    P8 --> P9["Phase 9: UI / UX & Map Experience 🟡"]
    P9 --> P10["Phase 10: Cloud Deployment & Telemetry 🟡"]
    P10 --> P11["Phase 11: Demo, Documentation & Submission 🟡"]
```

---

## 📋 Phase Breakdown

### Phase 0: Project Understanding & Documentation
- **Status:** 🟢 **IMPLEMENTED**
- **Purpose:** Conduct deep architecture and code audit, establish ground-truth project baseline, align decisions, and create permanent documentation structure.
- **Major Work:**
  - Audit existing ADK workflow, MCP server, unit/integration tests, and Terraform scaffolding.
  - Document all architectural components and identify gaps/inconsistencies between docs and code.
  - Formulate core architectural decisions (`DEC-001`, `DEC-002`, `DEC-003`).
  - Establish `docs/` repository standard (`MASTER_ROADMAP.md`, `ARCHITECTURE.md`, `DECISION_LOG.md`, `FUTURE_BACKLOG.md`, `CHANGELOG.md`, and `phases/`).
- **Dependencies:** None.
- **Future Upgrades:** Maintain documentation updates at the completion of each subsequent phase.

---

### Phase 1: Earth Engine Foundation
- **Status:** 🟡 **IN PROGRESS**
- **Purpose:** Establish the technical foundation for using Google Earth Engine to extract the first satellite-derived agricultural signal (Sentinel-2 + NDVI regional statistics).
- **Sub-Roadmap:**
  - **1A — Earth Engine Architecture & Integration Design (🟡 IN PROGRESS / Active):**
    - Understand Earth Engine's role in the multi-agent system.
    - Understand authentication model (service account vs developer ADC).
    - Understand project/quota model for GCP project `bharatsahayak-v2`.
    - Compare integration boundaries (Options A, B, C) and select decoupled module architecture (`DEC-004`).
    - Record architectural decisions and boundary specifications.
  - **1B — Local Earth Engine Environment (🟡 PLANNED):**
    - Add `earthengine-api` dependency to project management.
    - Configure local developer environment.
    - Authenticate developer environment against Earth Engine API.
    - Verify GCP project association (`bharatsahayak-v2`).
  - **1C — Earth Engine Connectivity Test (🟡 PLANNED):**
    - Initialize Earth Engine client.
    - Run minimal API query to verify connectivity.
    - Verify Copernicus Sentinel-2 MSI collection availability.
    - Verify Earth Engine result deserialization and error handling.
  - **1D — Geographic Region Definition (🟡 PLANNED):**
    - Decide point $\rightarrow$ analysis region strategy (bounding box vs point buffer).
    - Define initial farm/region geometry helpers.
    - Validate latitude/longitude coordinate bounds (India spatial bounds).
    - Test region geometry querying against Earth Engine.
  - **1E — Sentinel-2 Data Pipeline (🟡 PLANNED):**
    - Select Copernicus Sentinel-2 Level-2A (Surface Reflectance) collection.
    - Implement spatial location filtering.
    - Implement temporal date filtering (recent seasonal window).
    - Implement image selection and cloud masking (`QA60` / SCL band filtering).
    - Validate retrieved imagery metadata and scene quality.
  - **1F — NDVI Calculation (🟡 PLANNED):**
    - Identify Red (B4) and Near-Infrared (B8) spectral bands.
    - Implement normalized difference calculation: $\text{NDVI} = \frac{\text{B8} - \text{B4}}{\text{B8} + \text{B4}}$.
    - Generate single-band NDVI image in Earth Engine.
    - Validate theoretical value range ($-1.0$ to $+1.0$).
  - **1G — Regional NDVI Statistics (🟡 PLANNED):**
    - Implement Earth Engine zonal reducers across farm region:
      - **mean** NDVI (overall vegetative health).
      - **median** NDVI (robust central tendency).
      - **minimum** NDVI (localized stress / non-vegetated spots).
      - **maximum** NDVI (peak vegetative vigor).
    - Format output as a structured, serializable JSON dictionary.
  - **1H — Reliability & Data Quality (🟡 PLANNED):**
    - Handle invalid/out-of-bounds coordinates gracefully.
    - Handle scenarios with no cloud-free imagery available.
    - Handle excessive cloud cover flagging and user warnings.
    - Handle empty spatial regions or zero-pixel reductions.
    - Handle API timeouts, quota limits, and network errors.
    - Validate returned statistics against physical sanity constraints.
  - **1I — Integration Boundary Verification (🟡 PLANNED):**
    - Verify Earth Engine calculation module works independently of MCP/ADK.
    - Ensure MCP interface remains a clean capability wrapper.
    - Avoid unnecessary coupling between Earth Engine code and LLM agent prompts.
    - Preserve pluggability for future satellite datasets (Dynamic World, NDWI).
  - **1J — Phase Documentation (🟡 PLANNED):**
    - Record Before vs After implementation state.
    - Document actual code changes, test results, and verified outputs.
    - Update decision logs and record deferred work.
    - Update Future Upgrade Impact matrix and Resume Status.
  - **1K — Git Checkpoint (🟡 PLANNED):**
    - Run full verification test suite.
    - Commit verified Phase 1 implementation with clean working tree.
- **Dependencies:** Phase 0.
- **Future Upgrades:** Polygon boundary ingestion from geoJSON / KML files, multi-temporal time series, and anomaly baselines.

---

### Phase 2: Satellite Intelligence (Sentinel-2 + NDVI Regional Statistics)
- **Status:** 🟡 **PLANNED**
- **Purpose:** Implement real satellite data extraction using Copernicus Sentinel-2 surface reflectance imagery to compute regional vegetation indices.
- **Major Work:**
  - Query Copernicus Sentinel-2 MSI (Harmonized) collection with cloud-masking (`QA60` / SCL band filtering).
  - Calculate Normalized Difference Vegetation Index:
    $$\text{NDVI} = \frac{\text{B8 (NIR)} - \text{B4 (Red)}}{\text{B8 (NIR)} + \text{B4 (Red)}}$$
  - Compute regional statistical aggregations across the farm area: **mean**, **median**, **min**, and **max**.
  - Interpret vegetative health bands (vigor, crop density, potential stress zones).
- **Dependencies:** Phase 1.
- **Future Upgrades (`🔴 IDEA`):** Multi-temporal NDVI time series, historical baseline anomaly detection, NDWI (water index), EVI (Enhanced Vegetation Index), and Dynamic World LULC classification.

---

### Phase 3: Additional Agricultural & Environmental Data Sources
- **Status:** 🟡 **PLANNED**
- **Purpose:** Lay the foundation for external environmental and open agricultural datasets via a modular, pluggable provider architecture.
- **Major Work:**
  - Design pluggable provider interface for environmental data.
  - Integrate live meteorological feeds (precipitation forecast, temperature extremes, humidity, wind).
  - Prepare data structures for soil properties (pH, organic carbon, texture) and regional agro-climatic zones.
- **Dependencies:** Phase 0, Phase 1.
- **Future Upgrades (`🔴 IDEA`):** SoilGrids / ICAR soil profiles, ERA5-Land historical climate reanalysis, live mandi prices via Agmarknet / e-NAM APIs.

---

### Phase 4: Multi-Source Data Fusion
- **Status:** 🟡 **PLANNED**
- **Purpose:** Fuse satellite NDVI statistics, weather metrics, farmer profile state, and regional agronomic rules into a coherent contextual intelligence payload.
- **Major Work:**
  - Aggregate spatial NDVI statistics with local seasonal context and weather predictions.
  - Produce normalized "Farm Health & Environmental Context" JSON structures ready for LLM consumption.
  - Implement confidence scoring and missing-data fallback logic.
- **Dependencies:** Phase 2, Phase 3.
- **Future Upgrades (`🔴 IDEA`):** Automated stress anomaly tagging (e.g. flagging moisture stress vs pest damage based on NDVI + rainfall correlation).

---

### Phase 5: Gemini Agricultural Reasoning Engine
- **Status:** 🟡 **PLANNED**
- **Purpose:** Enhance Gemini 2.5 Flash prompt engineering and domain reasoning to synthesize fused satellite data into clear, empathetic, and actionable farming advice.
- **Major Work:**
  - Refactor system instructions for specialized advisors (`farming_advisor`, `weather_advisor`, `crop_disease_advisor`, `gov_schemes_advisor`) to consume fused satellite/weather context.
  - Instruct model on interpreting NDVI ranges in simple, jargon-free farmer language (English and Hindi).
  - Enforce actionable next steps: irrigation adjustments, targeted fertilizer dosing, and pest scouting.
- **Dependencies:** Phase 4.
- **Future Upgrades (`🔴 IDEA`):** Regenerative agriculture advisory modules, organic alternative recommendations, and climate-resilience scoring.

---

### Phase 6: MCP Server & Agent Integration
- **Status:** 🟡 **PLANNED**
- **Purpose:** Upgrade Model Context Protocol (MCP) server from static mock/catalog responses to live, tool-backed satellite and agricultural execution services.
- **Major Work:**
  - Upgrade FastMCP server tools (`get_farm_satellite_intelligence`, `get_weather_advisory`, `search_government_schemes`, `calculate_farming_profitability`).
  - Implement strict Pydantic schemas, source provenance metadata, and execution timing.
  - Connect updated MCP tools to ADK `LlmAgent` instances via `McpToolset`.
- **Dependencies:** Phase 2, Phase 3, Phase 5.
- **Future Upgrades (`🔴 IDEA`):** Tool result caching layer, circuit breaker for remote API timeouts, and live scheme lookup via official ministry endpoints.

---

### Phase 7: End-to-End Farmer Workflow & Interaction Flows
- **Status:** 🟡 **PLANNED**
- **Purpose:** Deliver seamless multi-turn conversational flows, intuitive farm onboarding, and human-in-the-loop (HITL) clarifications.
- **Major Work:**
  - Map-based location resolution flow: translate human-understandable location inputs (village, district, pin drop) to coordinates.
  - Onboard farm profile (location, crop, acreage, season) with interactive clarification.
  - Ensure language switching (English ⇄ Hindi) persists dynamically across conversational turns.
  - Seamless HITL resumption for ambiguous or missing parameters without state loss.
- **Dependencies:** Phase 5, Phase 6.
- **Future Upgrades (`🔴 IDEA`):** Regional voice input/output (STT/TTS in Hindi, Kannada, Telugu), multimodal leaf photo upload for vision-based diagnosis.

---

### Phase 8: Testing, Reliability, Security & Evaluation
- **Status:** 🟡 **PLANNED**
- **Purpose:** Validate entire system reliability, mock external dependencies for automated pipelines, harden security checkpoints, and run domain-specific LLM evaluations.
- **Major Work:**
  - Expand unit tests for satellite calculations, geometry utilities, and state transitions.
  - Create robust integration tests covering multi-turn HITL flows and live/mocked MCP tools.
  - Replace generic eval dataset (`basic-dataset.json`) with India-specific agricultural evaluation dataset (English, Hindi, mixed vernacular, adversarial inputs).
  - Verify PII sanitization (Aadhaar, mobile, credentials) and prompt injection defenses.
- **Dependencies:** Phase 6, Phase 7.
- **Future Upgrades (`🔴 IDEA`):** Automated synthetic evaluation generation via `agents-cli eval dataset synthesize` and LLM-as-a-judge regression tracking.

---

### Phase 9: UI / UX & Map Experience
- **Status:** 🟡 **PLANNED**
- **Purpose:** Build a premium, farmer-centric web interface with interactive map selection, NDVI health heatmaps, and clean advisory cards.
- **Major Work:**
  - Interactive map component supporting location search, GPS geolocation assistance, and farm boundary selection.
  - Visual NDVI health indicators (color-coded vegetation density and vigor).
  - Conversational chat interface with streaming responses, audio/voice toggles, and multi-language switches.
- **Dependencies:** Phase 7.
- **Future Upgrades (`🔴 IDEA`):** Offline progressive web app (PWA) field mode with cached advisories.

---

### Phase 10: Cloud Deployment & Telemetry
- **Status:** 🟡 **PLANNED**
- **Purpose:** Deploy production services to Google Cloud Platform (Cloud Run / Vertex AI Agent Engine) with full OpenTelemetry monitoring.
- **Major Work:**
  - Finalize Terraform infrastructure in `deployment/terraform/single-project/` for GCP project `bharatsahayak-v2`.
  - Configure Vertex AI Reasoning Engine / Cloud Run service containers.
  - Verify Cloud Storage telemetry bucket, GenAI completion hooks, and Cloud Logging streams.
- **Dependencies:** Phase 8, Phase 9.
- **Future Upgrades (`🔴 IDEA`):** Automated CI/CD deployment via Cloud Build GitHub triggers.

---

### Phase 11: Demo, Documentation & Final Submission
- **Status:** 🟡 **PLANNED**
- **Purpose:** Package final submission materials, record polished end-to-end demo video, and publish complete project documentation.
- **Major Work:**
  - Produce comprehensive walkthrough video showcasing satellite analysis, HITL flow, multilingual Hindi advice, and security guardrails.
  - Update `README.md`, architecture diagrams, and submission writeups to reflect final implemented reality.
  - Audit codebase for documentation consistency, reproducibility, and clean setup instructions.
- **Dependencies:** All previous phases.
- **Future Upgrades:** Post-hackathon open-source community distribution.
