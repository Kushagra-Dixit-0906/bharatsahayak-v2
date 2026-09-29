# Phase 0 — Project Foundation & Architecture Baseline

> **Phase 0 Execution Record, Baseline Architecture Audit, and Decision Summary for BharatSahayak V2.**  
> *Status: 🟢 COMPLETED | Date: September 2026*

---

## 🎯 Objective

Establish an unshakeable ground-truth foundation for BharatSahayak V2 by:
1. Conducting an exhaustive audit of the existing codebase, application architecture, test suite, and deployment scaffolding.
2. Identifying all gaps, static mock limitations, and documentation-versus-code inconsistencies.
3. Formulating and recording foundational architectural decisions (`DEC-001`, `DEC-002`, `DEC-003`).
4. Establishing a permanent, structured documentation standard under `docs/` (`MASTER_ROADMAP.md`, `ARCHITECTURE.md`, `DECISION_LOG.md`, `FUTURE_BACKLOG.md`, `CHANGELOG.md`, and `phases/`).
5. Setting clear system boundaries and defining the exact upgrade paths for satellite intelligence, multi-source data fusion, live MCP tools, and farmer-centric UI.

---

## 📍 Starting State

- **Repository:** `bharatsahayak`
- **Git Branch:** `bharatsahayak-v2`
- **Baseline Commit (HEAD):** `e0fcc29`
- **GCP Project ID:** `bharatsahayak-v2`
- **Working Tree State:** Clean
- **Frameworks & Models:** Google ADK 2.2.0, Gemini 2.5 Flash, FastMCP over stdio, Python 3.11–3.13 (`uv`).
- **Earth Engine Context:** Earth Engine registration and API setup are already completed externally for project `bharatsahayak-v2`.

### Initial Inventory
- **Agents:** Central `orchestrator` with 4 domain advisors (`farming_advisor`, `weather_advisor`, `gov_schemes_advisor`, `crop_disease_advisor`).
- **Tooling:** `FastMCP` local server in [app/mcp_server.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/mcp_server.py) connecting over `stdio`.
- **Safety / Guardrails:** In-graph `security_checkpoint` for regex PII redaction and prompt injection blocking.
- **State & HITL:** `FarmerProfile` in ADK state, with missing-season interception yielding `RequestInput`.
- **Tests:** Unit tests in `tests/unit/`, integration tests with mocked Gemini streams in `tests/integration/`, generic evaluation config in `tests/eval/`.
- **Deployment:** Unprovisioned Terraform configuration in `deployment/terraform/single-project/`.

---

## 🔍 Audit Findings

### 1. Application Architecture & Implementation Reality
- The core ADK multi-agent workflow is clean, modular, and functional. Graph transitions (`START` $\rightarrow$ `security_checkpoint` $\rightarrow$ `load_farmer_profile` $\rightarrow$ `orchestrator` $\rightarrow$ `hitl_checkpoint` $\rightarrow$ `format_final_output`) are well-defined.
- The `load_farmer_profile` node successfully parses location, crop, farm size, and language, maintaining memory across turns.
- The `hitl_checkpoint` node reliably intercepts crop recommendation requests missing a farming season, prompts the user via `RequestInput`, and resumes with `retry_with_info`.

### 2. Static / Mock Limitations of Current MCP Layer
- **Finding:** [app/mcp_server.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/mcp_server.py) exposes 4 agricultural tools, but all 4 return **hardcoded rules and static catalog strings** tailored strictly for Punjab, Karnataka, Wheat, Rice, and Cotton.
- **Impact:** While the agent-tool integration contract is sound, the data is not live or dynamic. Queries for other states or crops receive generic fallback text. Upgrading these tools to live satellite, meteorological, and database services is required in Phase 6.

### 3. Documentation Inconsistencies vs. Actual Code
- **Missing File in README Tree:** `README.md` lists `app/main.py` in its project structure tree, but this file does not exist (the entrypoints are `app/agent.py` and `app/agent_runtime_app.py`).
- **Multilingual Scope Discrepancy:** Documentation claims support for regional languages including Hindi, Kannada, Telugu, etc. In actual code, rule-based extractors (`detect_language`, `extract_location`, `extract_crops`, `extract_season`) only implement logic for English and Hindi (Devanagari script). Other scripts default to English processing.
- **HITL Scope Discrepancy:** Documentation states HITL triggers whenever location, land size, or season are missing. In actual code, deterministic interception specifically targets `is_crop_recommendation_request(query) and is_season_missing(query)`. Other missing details rely solely on LLM self-flagging (`needs_more_info`).
- **Unused Package References:** `pyproject.toml` references `known-first-party = ["app", "frontend"]` and build targets `packages = ["app", "frontend"]`, but there is no `frontend/` directory in the current repository.

### 4. Evaluation Dataset Domain Mismatch
- **Finding:** [tests/eval/datasets/basic-dataset.json](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/tests/eval/datasets/basic-dataset.json) contains default boilerplate evaluation cases (e.g., asking about San Francisco weather).
- **Impact:** Running `agents-cli eval generate` does not test agricultural domain accuracy, Hindi translation fidelity, or HITL resumption. A domain-specific dataset must be constructed in Phase 8.

### 5. Deployment Scaffolding Status
- **Finding:** `deployment_metadata.json` confirms `"remote_agent_runtime_id": "None"`. Terraform files are configured with placeholder values (`project_id = "your-gcp-project-id"`).
- **Impact:** The application is purely local at this stage; cloud deployment is scaffolding only and has not been provisioned.

---

## ⚖️ Decisions Made

### DEC-001: Start Satellite Intelligence with Sentinel-2 + NDVI Before Dynamic World
- **Decision:** Use Copernicus Sentinel-2 MSI Surface Reflectance (10m resolution) to calculate NDVI ($\frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$) as the primary vegetation health indicator.
- **Rationale:** 10m resolution is essential for Indian smallholder farm plots (0.5–3 acres). Dynamic World LULC, NDWI, and other indices will remain decoupled, pluggable data providers.

### DEC-002: Use Regional NDVI Summary Statistics Initially; Defer Time Series & Anomaly Baselines
- **Decision:** Extract zonal summary statistics (**mean**, **median**, **min**, **max**) for the farm area. Deliberately defer multi-year NDVI time-series graphing and automated anomaly baseline modeling.
- **Rationale:** Keeps context concise and token-efficient for Gemini 2.5 Flash reasoning while avoiding heavy multi-temporal Earth Engine latency during conversational turns.

### DEC-003: Implement Map-Based Farm Location with Search & Geolocation Assistance
- **Decision:** Build a farmer-facing map UI supporting GPS geolocation assistance, village/district search, and manual pin-drop. Never require farmers to manually know or enter raw latitude/longitude coordinates.
- **Architectural Principle:** *"Ask the farmer for the easiest human-understandable input and derive technical geographic information from it where possible."*

---

## 🚫 Current Boundaries (What BharatSahayak V2 Does NOT Yet Do)

To ensure clear operational truth, BharatSahayak V2 at Phase 0 does **NOT**:
1. ❌ Query live Google Earth Engine satellite imagery (scheduled for Phase 1–2).
2. ❌ Fetch live meteorological feeds from IMD or weather APIs (scheduled for Phase 3).
3. ❌ Perform automated multi-source data fusion (scheduled for Phase 4).
4. ❌ Provide live-connected MCP tools (currently static/catalog rules in `app/mcp_server.py`; scheduled for Phase 6).
5. ❌ Render an interactive map or visual web dashboard (scheduled for Phase 9).
6. ❌ Run deployed on Vertex AI Agent Engine in production (scaffolding only; scheduled for Phase 10).
7. ❌ Support voice STT/TTS or Dravidian script parsing (Kannada, Telugu) in deterministic extractors (scheduled for Phase 7 / Backlog).

---

## 🔮 Future Upgrade Impact

For every major deferred capability, this section documents the architectural considerations, dependencies, and files affected to ensure clean, non-breaking evolution in future phases:

| Feature / Upgrade Area | Current Implementation Boundary | Likely Future Module / File Affected | Dependencies | Architectural Considerations |
| :--- | :--- | :--- | :--- | :--- |
| **Earth Engine Connectivity & Auth** | No EE code in repository; credentials set up externally. | `app/satellite/client.py`, `app/config.py` | Phase 0 | Initialize EE using service account credentials from GCP project `bharatsahayak-v2`; implement point/buffer geometry utilities. |
| **Sentinel-2 NDVI Calculation** | No satellite calculation exists. | `app/satellite/ndvi.py`, `app/satellite/geometry.py` | Phase 1 | Apply Cloud Score+ observation quality masks (`DEC-010`); compute zonal reducers (mean, median, min, max); return standard JSON payload. |
| **Live Weather & Soil Providers** | Static strings in `app/mcp_server.py`. | `app/data_sources/weather.py`, `app/data_sources/soil.py` | Phase 1 | Implement `WeatherProvider` and `SoilProvider` abstract interfaces with 1-hour caching and graceful offline fallbacks. |
| **Multi-Source Data Fusion** | No fusion engine; agents receive profile string. | `app/fusion/engine.py` | Phase 2, Phase 3 | Aggregate spatial NDVI, weather alerts, and farm profile into a unified `FarmHealthContext` model. |
| **Live MCP Tool Backends** | `FastMCP` tools return hardcoded dictionaries. | `app/mcp_server.py` | Phase 2, Phase 3, Phase 5 | Preserve existing tool signatures (`get_weather_advisory`, `calculate_farming_profitability`, etc.) while delegating logic to live providers. |
| **Agent Prompt Optimization** | Prompts instruct advisors without satellite awareness. | `app/agent.py` | Phase 4, Phase 5 | Add system instructions for interpreting NDVI vigor ranges and vegetation stress without introducing jargon to the farmer. |
| **Map UI & Geocoding** | CLI/FastAPI text interface via `adk web app`. | `frontend/`, `app/agent_runtime_app.py` | Phase 7, Phase 9 | Build map component with village/district search; pass resolved `(lat, lon, acreage)` directly to backend API. |
| **Domain-Specific Evaluation** | Generic San Francisco weather eval cases in `tests/eval/`. | `tests/eval/datasets/indian_agri_dataset.json` | Phase 7 | Author 20+ multi-turn agricultural test cases in Hindi and English with expected tool calls and assertions. |
| **Production Cloud Deployment** | Unapplied Terraform templates in `deployment/terraform/`. | `deployment/terraform/single-project/vars/env.tfvars` | Phase 8, Phase 9 | Set `project_id = "bharatsahayak-v2"`, configure Vertex AI Reasoning Engine container, and verify GCS telemetry. |

---

## 🏁 Phase Status

- **Phase 0 Status:** 🟢 **COMPLETED**
- **Artifacts Created:**
  - `docs/MASTER_ROADMAP.md`
  - `docs/ARCHITECTURE.md`
  - `docs/DECISION_LOG.md`
  - `docs/FUTURE_BACKLOG.md`
  - `docs/CHANGELOG.md`
  - `docs/phases/PHASE_00_PROJECT_FOUNDATION.md`

---

## 📌 Suggested Git Checkpoint

> [!NOTE]
> No Git commits were executed automatically in adherence to Phase 0 constraints. When ready, commit using:

```bash
git add docs/
git commit -m "docs: establish v2 project roadmap and architecture records"
```
