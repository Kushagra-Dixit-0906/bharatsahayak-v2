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
| **NDVI Multi-Temporal Time Series** | 🟡 PLANNED (Phase 2+) | Medium | Avoids heavy temporal aggregation latency during real-time chat turns (`DEC-002`). | Phase 1 (EE foundation) | `app/` satellite modules, MCP implementation | Must return optional time-series array without changing core statistical response keys (`mean`, `max`, etc.). |
| **Historical NDVI Baselines & Anomaly Detection** | 🔴 IDEA | Medium | Requires 3+ years of seasonal imagery alignment and z-score anomaly modeling. | NDVI time series | `app/` analytics modules, `app/agent.py` | Anomaly flags must be passed as supplementary metadata, not hard requirements for agent advice. |
| **Dynamic World Land Cover (LULC)** | 🟡 PLANNED (Phase 3) | Medium | Sentinel-2 NDVI chosen as primary vegetation metric (`DEC-001`). | Phase 1 | `app/` satellite modules, MCP implementation | Implement as a pluggable `LulcProvider`; do not tightly couple crop recommendation to LULC classification. |
| **NDWI (Water / Moisture Index)** | 🟡 PLANNED (Phase 3) | High | Focused first on vegetation greenness index before expanding spectral band math. | Phase 1 | `app/` satellite modules, MCP implementation | Compute as a companion index to NDVI; share same geometry and cloud mask pipeline. |
| **Additional Indicators (EVI, SAVI, NDRE)** | 🔴 IDEA | Low | Standard NDVI is universally understood and sufficient for smallholder MVP. | Phase 2 | `app/` satellite modules | Keep index calculation functions modular and independent. |

---

## 🌦️ 2. Agricultural & Environmental Data Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Soil Properties & Nutrients (pH, N-P-K, OC)** | 🟡 PLANNED (Phase 3) | High | Soil database integration requires spatial polygon lookup against SoilGrids / ICAR datasets. | Phase 1 | `app/data_sources/soil.py` | Wrap behind `SoilDataProvider` interface; return fallback default estimates if coordinate lookup misses. |
| **Live High-Resolution Weather (IMD / Open-Meteo)** | 🟡 PLANNED (Phase 3) | High | MCP server currently uses static catalog rules; live weather integration is a dedicated milestone. | Phase 1 | `app/data_sources/weather.py`, `app/mcp_server.py` | Implement robust caching (TTL 1 hour) and offline fallbacks to prevent chat halts on API timeouts. |
| **Rainfall & Monsoon Forecast Alerts** | 🟡 PLANNED (Phase 3) | High | Requires real-time 7-day precipitation probability and extreme weather warnings. | Live weather API | `app/data_sources/weather.py`, `app/agent.py` | Weather alert objects must be standardized across all forecast providers. |
| **Live Mandi Prices & Market Intelligence** | 🔴 IDEA | Medium | e-NAM / Agmarknet API scraping/integration requires state-wise commodity mapping. | Phase 3 | `app/data_sources/market.py` | Keep market prices advisory-only; do not gate profitability calculators on real-time price scrapes. |
| **Government Schemes Catalog Expansion** | 🟡 PLANNED (Phase 6) | Medium | Current scheme database covers PM-KISAN, PMFBY, and select Punjab/Karnataka programs. | Phase 6 | `app/data_sources/schemes.py` | Expand state JSON catalogs independently of agent reasoning code. |

---

## 🧠 3. Intelligence & Data Fusion Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Multi-Source Data Fusion Engine** | 🟡 PLANNED (Phase 4) | High | Requires satellite statistics, live weather, and soil data to exist before fusing. | Phase 2, Phase 3 | `app/fusion/engine.py` | Produces a clean, normalized `FarmContext` dictionary consumed by agent prompts. |
| **Regenerative & Climate-Resilient Advisories** | 🟡 PLANNED (Phase 5) | Medium | Advanced prompt engineering to recommend natural farming, mulching, and low-water crops. | Phase 4 | `app/agent.py` | Incorporate into specialized `farming_advisor` prompt without changing output schemas. |
| **Confidence & Uncertainty Handling** | 🟡 PLANNED (Phase 5) | High | Satellite data may have partial cloud cover; agent must communicate confidence score honestly. | Phase 2, Phase 4 | `app/agent.py`, `app/mcp_server.py` | Pass `cloud_cover_percentage` and `data_confidence` in tool payload to let Gemini self-explain uncertainty. |

---

## 🔌 4. Agent & MCP Architecture Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Live MCP Tool Backends** | 🟡 PLANNED (Phase 6) | High | Replaces static mock data in `app/mcp_server.py` with live Earth Engine and weather providers. | Phase 2, Phase 3 | `app/mcp_server.py` | Preserve tool signature compatibility (`name`, `args`, `return`) to avoid breaking existing agents. |
| **Data Provenance & Source Metadata** | 🟡 PLANNED (Phase 6) | Medium | Enables the agent to cite exact data sources (e.g. "Copernicus Sentinel-2 pass on Sept 8"). | Phase 6 | `app/mcp_server.py`, `app/agent.py` | Return `source_citations` in MCP output envelopes. |
| **Tool Response Caching & Rate Limiting** | 🟡 PLANNED (Phase 6) | High | Prevents redundant Earth Engine / weather calls when a farmer asks multiple questions about the same plot. | Phase 6 | `app/mcp_server.py`, `app/cache.py` | Cache key based on `(lat, lon, date, tool_name)` with appropriate TTLs. |
| **Circuit Breaker & Fallback Resilience** | 🟡 PLANNED (Phase 6) | High | Ensures conversation continues gracefully even if an external API fails. | Phase 6 | `app/mcp_server.py` | Tools must return structured degradation messages rather than unhandled Python exceptions. |

---

## 👨‍🌾 5. Farmer Workflow & Interaction Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Map-Based Farm Location Onboarding** | 🟡 PLANNED (Phase 7/9) | High | User-facing map interface scheduled for UI phase (`DEC-003`). | Phase 1, Phase 9 | `app/agent.py`, `frontend/` | The agent must accept both text-resolved locations and spatial coordinate payloads. |
| **Voice Interaction (STT / TTS in Regional Indian Languages)** | 🔴 IDEA | Medium | Adds significant complexity (ASR/TTS audio pipelines, latency management). | Phase 7 | `frontend/audio/`, `app/speech/` | Keep audio transcription layer completely separate from ADK agent graph reasoning. |
| **Multilingual Expansion (Kannada, Telugu, Marathi, Tamil, etc.)** | 🟡 PLANNED (Phase 7) | High | Current regex extractors explicitly target English and Hindi Devanagari. | Phase 7 | `app/agent.py` | Extend regex dictionaries and test suites for Dravidian and Indo-Aryan scripts. |
| **Multimodal Crop Leaf Photo Upload** | 🔴 IDEA | Low | Visual disease diagnosis via camera requires multimodal image ingestion and validation pipeline. | Phase 7 | `app/agent.py`, `app/mcp_server.py` | Pass images to specialized vision tool or Gemini Multimodal input parts. |

---

## 💻 6. UI / UX Backlog

| Backlog Item | Status | Priority | Reason Deferred | Dependencies | Likely Files / Modules Affected | Architectural Decoupling Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Interactive Map Component (Leaflet / Mapbox / Google Maps)** | 🟡 PLANNED (Phase 9) | High | Dedicated frontend engineering phase. | Phase 7 | `frontend/components/Map.jsx` | Frontend sends standard JSON requests to ADK backend API. |
| **NDVI Health Heatmap Overlay** | 🟡 PLANNED (Phase 9) | Medium | Visual raster rendering of vegetation vigor over the farm map. | Phase 2, Phase 9 | `frontend/components/NdviLayer.jsx` | Stream Earth Engine tile URLs or GeoJSON polygons independently of text stream. |
| **Farmer Dashboard & Advisory Cards** | 🟡 PLANNED (Phase 9) | High | Visual structured cards for investment, profit, weather alerts, and schemes. | Phase 7, Phase 9 | `frontend/components/AdvisoryCard.jsx` | Parse structured model responses cleanly with fallback to raw markdown. |

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
| **India-Specific Agricultural Evaluation Dataset** | 🟡 PLANNED (Phase 8) | High | Replace scaffold `basic-dataset.json` (San Francisco weather) with comprehensive farming cases. | Phase 7 | `tests/eval/datasets/` | Create 20+ multi-turn test cases covering Hindi, English, HITL season flows, and adversarial attacks. |
| **Earth Engine Unit & Mock Integration Tests** | 🟡 PLANNED (Phase 8) | High | Validate Earth Engine calculation helpers without requiring live API network calls in CI/CD. | Phase 1, Phase 2 | `tests/unit/test_satellite.py` | Use mocked Earth Engine reducer responses in unit test suites. |
| **Security & PII Regression Benchmarks** | 🟡 PLANNED (Phase 8) | High | Prevent regressions in Aadhaar redaction, phone scrubbing, and prompt injection defense. | Phase 8 | `tests/integration/test_security.py` | Automated pytest suite asserting sanitization on every commit. |
