# BharatSahayak V2 — Future Backlog & Deferred Enhancements

> **Structured catalog of deliberately deferred features, architectural guardrails, and future roadmap work.**  
> *Baseline Branch: `bharatsahayak-v2` | Project ID: `bharatsahayak-v2`*

---

## 🧭 Backlog Overview

To maintain laser focus on building a robust, grounded, and verified MVP for BharatSahayak V2, complex or non-critical features have been deliberately scoped into subsequent phases or post-MVP exploration. This backlog defines each item, why it was deferred, its dependencies, and how to maintain decoupled architectural boundaries.

> [!NOTE]
> **Earth Engine Integration State:**
> - **Current State:** The Earth Engine integration architecture has been designed (`DEC-004`), but **no application integration has yet been implemented**.
> - **Future Implementation:** A dedicated Earth Engine module/service will be constructed behind the MCP capability interface (Option C).
> - **Likely Future Areas Affected:** `app/` directory (geospatial/satellite logic), MCP implementation (`mcp_server.py`), `tests/` (unit and integration tests), and project configuration/dependency files (`pyproject.toml`).

---

## 🛰️ 1. Satellite & Remote Sensing Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Future Areas Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Historical NDVI Baselines & Anomaly Detection** | 🟢 COMPLETE (Phase 2 / `DEC-012`–`DEC-017`) | High | Resolved in Phase 2D: 3-year rolling baseline ($Y-1, Y-2, Y-3$), DOY $\pm 15$ days seasonal matching, Option C annual regional composite observations, pure-Python statistical engine (`ebba070`). | Phase 1 (EE foundation) | `app/satellite/` modules | Anomaly evidence remains empirical spectral data; zero agronomic diagnosis in satellite layer. |
| **Option C Earth Engine Collection Architecture** | 🟢 COMPLETE (Phase 2C / `DEC-016`) | High | Resolved in Phase 2C: independent annual sub-pipelines, Phase 1 quality parity, temporal recency selection (up to 3 usable scenes), and pixel-wise median NDVI compositing. | Phase 2A/2B | `app/satellite/` historical pipeline | Independent annual sub-pipelines selected for 3-year MVP; zero synthetic scene interpolation. |
| **Leap-Year DOY Alignment & Calendar Handling** | 🟢 COMPLETE (Phase 2B / `DEC-015`) | High | Resolved in Phase 2B: pure Python calendar-date-anchored windowing, simple Feb 29 $\to$ Feb 28 clamping, and cross-year target-year ownership. | Phase 2A | `app/satellite/` date utilities | Pure Python date arithmetic; ensure leap-year edge cases do not crash historical query windows. |
| **Per-Pixel Observation Depth Rasters** | 🔴 IDEA | Low | Generating per-pixel observation count rasters deferred in `DEC-016` to maintain lightweight Earth Engine compute graph. | Phase 2C | `app/satellite/` compositing | `valid_pixel_count` captures unmasked spatial pixels in zonal reduction; depth rasters deferred to future analysis. |
| **NDVI Multi-Temporal Time Series** | 🟡 PLANNED (Post-MVP) | Medium | Avoids heavy temporal aggregation latency during real-time chat turns (`DEC-002`). | Phase 1 (EE foundation) | `app/satellite/` modules, MCP implementation | Must return optional time-series array without changing core statistical response keys (`mean`, `max`, etc.). |
| **Dynamic World Land Cover (LULC)** | 🟢 COMPLETE (Phase 3C / `DEC-021`) | High | Resolved in Phase 3C: `GOOGLE/DYNAMICWORLD/V1` 10m Sentinel-2 L1C derived 9-class probability distribution, 30-day window, newest usable observation selection, Option A zonal mean reduction (`7a8371c`). | Phase 1 | `app/environment/dynamic_world.py`, `app/environment/dynamic_world_pipeline.py` | Land-cover context only; zero crop variety, yield, stress, or irrigation claims. |
| **NDWI (Water / Moisture Index)** | 🟡 PLANNED (Post-MVP) | Medium | Focused on multi-source environmental context (ERA5-Land soil moisture, CHIRPS rainfall) before expanding optical spectral band math. | Phase 1 | `app/satellite/` modules, MCP implementation | Compute as a companion index to NDVI; share same geometry and cloud mask pipeline. |
| **Additional Indicators (EVI, SAVI, NDRE)** | 🔴 IDEA | Low | Standard NDVI is universally understood and sufficient for smallholder MVP. | Phase 2 | `app/satellite/` modules | Keep index calculation functions modular and independent. |

---

## 🌦️ 2. Agricultural & Environmental Data Backlog

> [!IMPORTANT]
> **Core Architectural Principle:** *"Data sufficiency takes priority over dataset accumulation."*  
> The environmental data foundation is now complete and frozen for the first BharatSahayak prototype across Sentinel-2 NDVI, historical NDVI anomaly, ERA5-Land reanalysis, CHIRPS precipitation, and Dynamic World land cover. Further environmental datasets are deferred until a demonstrated agricultural reasoning gap requires them.

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 3D — Additional Environmental Signal (MODIS MOD16A2 Evapotranspiration Candidate)** | 🔴 DEFERRED | Low | **Scope Decision:** Environmental foundation is already sufficient across 5 complementary streams (NDVI, historical anomaly, ERA5-Land, CHIRPS, Dynamic World). Adding MODIS MOD16A2 (8-day, 500m global ET/PET) would increase complexity, test surface, EE dependencies, and failure modes without a demonstrated reasoning gap. | Phase 3A, 3B, 3C | `app/environment/` | Future candidate only; evaluate strictly if moisture-stress reasoning demonstrates a concrete information gap. |
| **Soil Properties & Nutrients (pH, N-P-K, OC)** | 🟡 PLANNED (Post-MVP) | Medium | Soil database integration requires spatial polygon lookup against SoilGrids / ICAR datasets; deferred to keep MVP foundation focused. | Phase 1 | `app/data_sources/soil.py` | Wrap behind `SoilDataProvider` interface; return fallback default estimates if coordinate lookup misses. |
| **Live High-Resolution Weather (Open-Meteo)** | 🟢 COMPLETE (Phase 9) | High | Resolved in Phase 9: public Open-Meteo REST API integration with 36 Indian state/district centroids and bilingual WMO weather mapping (`app/weather_service.py`). | Phase 1 | `app/weather_service.py` | Implement robust caching (TTL 1 hour) and offline fallbacks to prevent chat halts on API timeouts. |
| **Rainfall & Monsoon Forecast Alerts** | 🟡 PLANNED (Post-MVP) | High | Requires real-time 7-day precipitation probability and extreme weather warnings. | Live weather API | `app/weather_service.py`, `app/agent.py` | Weather alert objects must be standardized across all forecast providers. |
| **Live Mandi Prices & Market Intelligence** | 🔴 IDEA | Medium | e-NAM / Agmarknet API scraping/integration requires state-wise commodity mapping. | Phase 3 | `app/data_sources/market.py` | Keep market prices advisory-only; do not gate profitability calculators on real-time price scrapes. |
| **Government Schemes Catalog Expansion** | 🟡 PLANNED (Post-MVP) | Medium | Current scheme database covers PM-KISAN, PMFBY, and select Punjab/Karnataka programs. | Phase 6 | `app/data_sources/schemes.py` | Expand state JSON catalogs independently of agent reasoning code. |

---

## 🧠 3. Intelligence & Data Fusion Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Multi-Source Data Fusion Engine** | 🟢 COMPLETE (Phase 4 / `DEC-022`) | High | Resolved in Phase 4: `fuse_agricultural_environmental_evidence` assembling Sentinel-2, ERA5-Land, CHIRPS, and Dynamic World into `AgriculturalEnvironmentalEvidence` (`pipeline_version="4.0.0"`). | Phase 2, Phase 3 | `app/fusion/` | Produces an immutable, typed evidence envelope consumed by deterministic assessment. |
| **Regenerative & Climate-Resilient Advisories** | 🟡 PLANNED (Post-MVP) | Medium | Advanced prompt engineering to recommend natural farming, mulching, and low-water crops. | Phase 4 | `app/agent.py` | Incorporate into specialized `farming_advisor` prompt without changing output schemas. |
| **Confidence & Uncertainty Handling** | 🟢 COMPLETE (Phase 5 / `DEC-023`) | High | Resolved in Phase 5B/5C: `AssessmentSufficiency` and structured limitation reporting communicate cloud cover and observation latency transparently. | Phase 2, Phase 4 | `app/assessment/` | Pass `sufficiency` and `data_lag_days` in assessment envelope to self-explain uncertainty. |

---

## 🔌 4. Agent & MCP Architecture Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Live MCP Tool Backends** | 🟢 COMPLETE (Phase 6 / FastMCP) | High | FastMCP server (`app/mcp_server.py`) connects orchestrator directly to `get_environmental_assessment` pipeline over stdio. | Phase 2, Phase 3 | `app/mcp_server.py` | Preserve tool signature compatibility (`name`, `args`, `return`) to avoid breaking existing agents. |
| **Data Provenance & Source Metadata** | 🟢 COMPLETE (Phase 4/5) | Medium | Lineage metadata (`observation_id`, `observation_date`, `dataset`) preserved across all satellite and reanalysis payloads. | Phase 6 | `app/fusion/types.py`, `app/assessment/types.py` | Return source metadata in assessment output envelopes. |
| **Tool Response Caching & Rate Limiting** | 🟡 PLANNED (Post-MVP) | High | Prevents redundant Earth Engine / weather calls when a farmer asks multiple questions about the same plot. | Phase 6 | `app/mcp_server.py`, `app/cache.py` | Cache key based on `(lat, lon, date, tool_name)` with appropriate TTLs. |
| **Circuit Breaker & Fallback Resilience** | 🟢 COMPLETE (Phase 5C) | High | Deterministic offline fallback engine provides complete responses in English and Hindi if Gemini API fails or times out. | Phase 6 | `app/assessment/gemini_service.py` | Tools return structured degradation messages rather than unhandled Python exceptions. |

---

## 👨‍🌾 5. Farmer Workflow & Interaction Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Map-Based Farm Location Onboarding** | 🟢 COMPLETE (Phase 9 / One-Tap Browser GPS) | High | Resolved in Phase 9: HTML5 geolocation button + decimal coordinate input with validation in web UI (`frontend/`). | Phase 1, Phase 9 | `frontend/`, `app/agent.py` | The agent accepts both text-resolved locations and spatial coordinate payloads. |
| **Voice Interaction (STT / TTS in Regional Indian Languages)** | 🔴 IDEA | Medium | Adds significant complexity (ASR/TTS audio pipelines, latency management). | Phase 7 | `frontend/audio/`, `app/speech/` | Keep audio transcription layer completely separate from ADK agent graph reasoning. |
| **Multilingual Expansion (Kannada, Telugu, Marathi, Tamil, etc.)** | 🟡 PLANNED (Post-MVP) | High | Current regex extractors and fallbacks explicitly target English and Hindi Devanagari. | Phase 7 | `app/agent.py` | Extend regex dictionaries and test suites for Dravidian and Indo-Aryan scripts. |
| **Multimodal Crop Leaf Photo Upload** | 🔴 IDEA | Low | Visual disease diagnosis via camera requires multimodal image ingestion and validation pipeline. | Phase 7 | `app/agent.py`, `app/mcp_server.py` | Pass images to specialized vision tool or Gemini Multimodal input parts. |

---

## 💻 6. UI / UX Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Interactive Polygon Boundary Drawing Component** | 🟡 PLANNED (Post-MVP) | High | Canvas/Leaflet polygon drawing component for drawing exact cadastral field boundaries. | Phase 9 | `frontend/components/Map.jsx` | Frontend sends standard JSON requests with coordinates to ADK backend API. |
| **NDVI Health Heatmap Overlay** | 🟡 PLANNED (Post-MVP) | Medium | Visual raster rendering of vegetation vigor over the farm map. | Phase 2, Phase 9 | `frontend/components/NdviLayer.jsx` | Stream Earth Engine tile URLs or GeoJSON polygons independently of text stream. |
| **Farmer Dashboard & Advisory Cards** | 🟢 COMPLETE (Phase 9) | High | Resolved in Phase 9: Markdown cards, HITL resumption cards, and structured quick action presets in web UI (`frontend/`). | Phase 7, Phase 9 | `frontend/` | Parse structured model responses cleanly with fallback to raw markdown. |
| **Offline Progressive Web App (PWA) Mode** | 🔴 IDEA | Low | Service worker caching and offline advisory storage for rural low-connectivity areas. | Phase 9 | `frontend/service-worker.js` | Cache recent advisories and static assets in browser storage. |

---

## ☁️ 7. Deployment & Infrastructure Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Vertex AI Agent Engine / Cloud Run Provisioning** | 🟡 PLANNED (Phase 10) | High | Local testing and validation must precede cloud deployment to avoid wasted cloud spend. | Phase 8, Phase 9 | `deployment/terraform/`, `deployment_metadata.json` | Maintain 100% parity between local `adk web app` execution and Cloud Run deployment. |
| **Production Secrets & Service Account Configuration** | 🟡 PLANNED (Phase 10) | High | Configure GCP Secret Manager for Gemini API keys and Earth Engine service credentials. | Phase 10 | `deployment/terraform/` | No plain text API keys in repositories or build artifacts. |
| **BigQuery Telemetry & Monitoring Dashboard** | 🟡 PLANNED (Phase 10) | Medium | Telemetry SQL views already created in `deployment/terraform/shared/completions.sql`. | Phase 10 | `deployment/terraform/shared/` | OpenTelemetry emission should remain non-blocking. |

---

## 🧪 8. Testing & Evaluation Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **India-Specific Agricultural Evaluation Dataset** | 🟡 PLANNED (Post-MVP) | High | Synthetic evaluation generation via `agents-cli eval dataset synthesize` and LLM-as-a-judge benchmarking. | Phase 7 | `tests/eval/datasets/` | Create 20+ multi-turn test cases covering Hindi, English, HITL season flows, and adversarial attacks. |
| **Earth Engine Unit & Mock Integration Tests** | 🟢 COMPLETE (Phase 1-4) | High | Mocked and offline JSON fixtures validate all Earth Engine data transformation pipelines without network calls. | Phase 1, Phase 2 | `tests/fixtures/`, `tests/unit/` | Use mocked Earth Engine reducer responses in unit test suites. |
| **Security & PII Regression Benchmarks** | 🟢 COMPLETE (Phase 8) | High | Resolved in Phase 8: 8 automated unit tests in `tests/unit/test_security_hardening.py` passing cleanly (100% green). | Phase 8 | `tests/unit/test_security_hardening.py` | Automated pytest suite asserting sanitization on every commit. |
