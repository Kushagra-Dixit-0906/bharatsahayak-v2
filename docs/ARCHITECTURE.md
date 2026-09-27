# BharatSahayak V2 — System Architecture & Design

> **Current architectural baseline, operational mechanics, guardrails, and planned evolution.**  
> *Baseline Branch: `bharatsahayak-v2` | Commit: `e0fcc29`*

---

## 🏛️ System Overview

BharatSahayak V2 is an AI-powered rural agricultural companion designed to empower Indian smallholder farmers. The system is engineered on **Google ADK 2.0 (Agent Development Kit)**, powered by **Gemini 2.5 Flash**, and coupled to local and cloud execution tools via the **Model Context Protocol (MCP)**.

### Architectural Maturity Legend

| Status | Meaning |
| :--- | :--- |
| 🟢 **CURRENT / IMPLEMENTED** | Actively operational and verified in current codebase. |
| 🟡 **PLANNED** | Architecturally specified and scheduled for near-term implementation. |
| 🔴 **FUTURE IDEA** | Long-term enhancement in backlog. |

---

## 🔄 Current Execution Flow (`🟢 CURRENT / IMPLEMENTED`)

The current runtime follows a deterministic-to-agentic directed workflow graph managed by ADK:

```mermaid
graph TD
    subgraph ClientLayer ["1. Client & Ingestion Layer"]
        Farmer["👨‍🌾 Farmer / User Query"]
    end

    subgraph SecurityLayer ["2. Guardrails & Safety Layer"]
        SecNode["🛡️ Security Checkpoint Node\n(Regex PII Scrubbing + Injection Detection)"]
    end

    subgraph ContextLayer ["3. State & Context Layer"]
        ProfileNode["👤 Load Farmer Profile Node\n(Language, Location, Crops, Farm Size, Season)"]
    end

    subgraph AgentLayer ["4. Multi-Agent Reasoning Layer"]
        Orchestrator["🧠 Central Orchestrator (LlmAgent)"]
        FA["🌱 Farming Advisor"]
        WA["🌦️ Weather Advisor"]
        GA["🏛️ Government Schemes Advisor"]
        DA["🦠 Crop Disease Advisor"]
    end

    subgraph ToolLayer ["5. Tools & Data Layer (FastMCP over stdio)"]
        MCPServer["🔌 Local MCP Server\n(Static Rules & Catalog Lookup)"]
    end

    subgraph HITLLayer ["6. Interaction & Verification Layer"]
        HITLNode["🤝 HITL Checkpoint Node\n(RequestInput interrupt for missing Season)"]
    end

    subgraph OutputLayer ["7. Output & Delivery Layer"]
        FormatOut["💬 Format Final Output Node\n(Stream Model Content)"]
    end

    Farmer --> SecNode
    SecNode -- Threat / Malicious Input Blocked --> FormatOut
    SecNode -- Safe / Scrubbed Input --> ProfileNode
    ProfileNode --> Orchestrator

    Orchestrator --> FA
    Orchestrator --> WA
    Orchestrator --> GA
    Orchestrator --> DA

    FA -. McpToolset .-> MCPServer
    WA -. McpToolset .-> MCPServer
    GA -. McpToolset .-> MCPServer
    DA -. McpToolset .-> MCPServer

    FA --> HITLNode
    WA --> HITLNode
    GA --> HITLNode
    DA --> HITLNode
    Orchestrator --> HITLNode

    HITLNode -- Missing Season --> PauseReq["⏸️ RequestInput Pause"]
    PauseReq -. Farmer Provides Season .-> HITLNode
    HITLNode -- Resumed with Data --> Orchestrator
    HITLNode -- Response Complete --> FormatOut
    FormatOut --> Farmer
```

---

## 🧩 Architectural Components Breakdown

### 1. Framework & Model Engine (`🟢 CURRENT / IMPLEMENTED`)
- **Google ADK 2.0:** Uses ADK's `Workflow`, `START`, and `node` primitives for graph construction, `LlmAgent` for agent definitions, `AgentTool` for delegation hierarchy, and `Runner` with `InMemorySessionService` for stateful sessions.
- **Gemini Model:** Standardized on `gemini-2.5-flash` configured via [app/config.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/config.py). Temperature, system instructions, and structured schemas enforce crisp formatting.

### 2. Guardrails & Security Checkpoint (`🟢 CURRENT / IMPLEMENTED`)
The `security_checkpoint` node in [app/agent.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/agent.py) executes prior to any LLM invocation:
- **PII Redaction:**
  - **Aadhaar Numbers:** 12-digit Indian national identity numbers (formatted `XXXX XXXX XXXX` or `XXXXXXXXXXXX`) are scrubbed and replaced with `[AADHAAR_REDACTED]`.
  - **Phone Numbers:** 10-digit Indian mobile numbers starting with 6-9 are replaced with `[PHONE_REDACTED]`.
  - **Email Addresses:** Standard email formats replaced with `[EMAIL_REDACTED]`.
- **Prompt Injection Defense:** Intercepts manipulation phrases (`ignore previous instructions`, `system prompt`, `jailbreak`, `override instructions`, etc.) and immediately halts graph routing to `format_final_output` with a security alert.
- **Financial & Harmful Content Filters:** Blocks requests attempting to extract bank PINs, passwords, or instructions for malicious soil sabotage/poisoning.
- **Audit Logging:** Structured audit events with timestamps (Asia/Kolkata timezone), severity levels, and scrub details are appended to `ctx.state["audit_log"]` and logged to `sys.stderr`.

### 3. State & Profile Management (`🟢 CURRENT / IMPLEMENTED`)
The `load_farmer_profile` node parses incoming queries to maintain session state across conversational turns:
- **`FarmerProfile` Schema:**
  - `language`: Detected dynamically per turn ("English" or "Hindi" via Devanagari Unicode `\u0900-\u097f` evaluation).
  - `location`: Extracted via mapped Indian state and major city dictionaries.
  - `crops`: Multilingual English/Hindi crop dictionary extractor.
  - `farm_size`: Regex extraction for acreage (e.g., `2.5 acres`, `5 एकड़`).
  - `season`: Sowing season classification (`Kharif`, `Rabi`, `Zaid`).
- **Prompt Injection into Context:** The profile is serialized and prepended to the orchestrator prompt on every turn to ensure complete conversational recall.

### 4. Multi-Agent Delegation (`🟢 CURRENT / IMPLEMENTED`)
- **Central Orchestrator Agent:** The routing hub that decides which advisor agent should handle the farmer's request. Uses structured output schema `OrchestratorOutput` (`response`, `needs_more_info`, `info_request_message`).
- **Farming Advisor:** Generates region- and season-specific crop recommendations using a structured visual layout (emojis, estimated investment, profit, difficulty, schemes, next steps).
- **Weather Advisor:** Provides irrigation advice, fertilizer timing (e.g. urea application), and disease risk warnings.
- **Government Schemes Advisor:** Outlines central/state schemes (PM-KISAN, PMFBY, state subsidies), required documentation, and application steps.
- **Crop Disease Advisor:** Diagnoses crop fungal/bacterial diseases from symptom descriptions, detailing organic treatments, chemical controls, and prevention measures.

### 5. Human-in-the-Loop (HITL) Resumption (`🟢 CURRENT / IMPLEMENTED`)
- Implemented via `@node(rerun_on_resume=True)` in `_hitl_checkpoint_impl`.
- If a crop recommendation query lacks a defined farming season (`Kharif`, `Rabi`, or `Zaid`), the node yields a `RequestInput(interrupt_id="more_info")` with a localized prompt (in English or Hindi).
- When the farmer responds, the execution resumes statefully from `ctx.resume_inputs["more_info"]`, updates the profile, and yields `route="retry_with_info"` to re-run the orchestrator without losing existing context (such as land size or location).

### 6. MCP Data Layer (`🟢 CURRENT / IMPLEMENTED` with Known Limitations)
- **FastMCP Server:** Implemented in [app/mcp_server.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/mcp_server.py), running over `stdio` via `uv run app/mcp_server.py`.
- **Tools Exposed:**
  1. `get_weather_advisory(location, crop)`
  2. `get_crop_disease_info(crop, symptoms)`
  3. `search_government_schemes(state, crop)`
  4. `calculate_farming_profitability(crop, acreage, expected_yield_per_acre)`
- ⚠️ **CURRENT LIMITATION & UPGRADE AREA:**
  > [!IMPORTANT]
  > The current MCP server returns **static, rule-based catalog responses and hardcoded conditional lookups** for selected Indian states (Punjab, Karnataka) and crops (wheat, rice, cotton).  
  > It does **NOT** yet connect to live meteorological APIs, dynamic satellite feeds, or live government database endpoints. Connecting live data sources is a major milestone of upcoming phases.

### 7. Telemetry & Observability (`🟢 CURRENT / IMPLEMENTED`)
- **OpenTelemetry & GenAI Instrumentation:** [app/app_utils/telemetry.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/app_utils/telemetry.py) configures OpenTelemetry GenAI semantic conventions, optional message-content capture mode (`NO_CONTENT` metadata-only or full), and Google Cloud Storage upload hooks.
- **Feedback Collection:** [app/agent_runtime_app.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/agent_runtime_app.py) provides `register_feedback` operation logging structured satisfaction scores to Cloud Logging.

### 8. Cloud Deployment Infrastructure (`🟢 SCAFFOLDING ONLY`)
- Terraform templates in [deployment/terraform/single-project/](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/deployment/terraform/single-project/) define:
  - `google_vertex_ai_reasoning_engine` resource.
  - Telemetry GCS bucket and BigQuery completions SQL view.
  - Service accounts and IAM permissions.
- **Current Status:** Scaffolding complete; infrastructure has **not** yet been provisioned to GCP (`remote_agent_runtime_id: None`).

---

## 🛰️ Earth Engine Satellite Intelligence Flow (`🟢 PHASE 1 & PHASE 2 COMPLETE | 🟡 MCP CONNECTION SCHEDULED (Phase 6)`)

> [!IMPORTANT]
> **Current Implementation Status:**
> - **Phase 1 Instantaneous Satellite Engine (`app/satellite/`):** 🟢 **COMPLETE & SEALED (`60f8d90`)**. Standalone deterministic satellite computation engine providing `analyze_regional_ndvi(...)`, single authoritative observation selection, Cloud Score+ quality masking, NDVI computation, and regional zonal reductions (`382 tests passing`).
> - **Phase 2 Historical Intelligence & Anomaly Detection:** 🟢 **COMPLETE & SEALED (`DEC-012`–`DEC-017`, `ebba070`)**. Extends the satellite engine with 3-year rolling baselines ($Y-1, Y-2, Y-3$), calendar-date-anchored seasonal windowing ($T_h \pm 15\text{ days}$), target-year window ownership, Option C annual matched-window regional composite observations, pure-Python statistical baseline derivation (median, mean, population std dev ddof=0, sufficiency), empirical spectral departure anomaly quantification, and root payload integration (`700 satellite tests passing`).
> - **FastMCP Server & Agent Connection:** 🟡 **SCHEDULED FOR PHASE 6**. The active MCP server ([app/mcp_server.py](file:///d:/Documents/Desktop/adk-workspace/bharatsahayak/app/mcp_server.py)) currently retains its initial static/catalog tools until Phase 6 implements the live `get_regional_satellite_analysis` tool adapter.

### Multi-Year Historical Satellite Intelligence Architecture (`Phase 2D / DEC-017`)

Phase 2 enforces a strict three-tier module separation between remote Earth Engine data materialization, local pure-Python mathematics, and root domain payload composition:

```mermaid
graph TD
    subgraph Phase1 ["Phase 1: Instantaneous Observation (pipeline.py)"]
        P1["analyze_regional_ndvi(...)"] --> Cur["RegionalNdviAnalysis\n(Current Observation Y)"]
    end

    subgraph Phase2C ["Phase 2C: Multi-Year Historical Materialization (historical.py)"]
        Cur -. Reference Date .-> P2C["analyze_historical_years(...)"]
        P2C --> H1["Y-1: AnnualHistoricalNdviObservation"]
        P2C --> H2["Y-2: AnnualHistoricalNdviObservation"]
        P2C --> H3["Y-3: AnnualHistoricalNdviObservation"]
        H1 & H2 & H3 --> HList["list[AnnualHistoricalNdviObservation]"]
    end

    subgraph Phase2DMath ["Phase 2D: Pure Statistical Engine (baseline.py)"]
        Cur & HList --> Math["calculate_historical_ndvi_statistics(...)"]
        Math --> Base["HistoricalNdviBaseline\n(Median, Mean, StdDev ddof=0, Min, Max)"]
        Math --> Suff["HistoricalSufficiencyEvidence\n(N >= 2, Y >= 2)"]
        Math --> Anom["NdviAnomalyEvidence\n(Absolute Δ, Gated %, Gated Z-Score, Departure Band)"]
    end

    subgraph Phase2DIntegration ["Phase 2D: Root Domain Composition (historical_analysis.py)"]
        Cur & HList & Base & Suff & Anom --> Root["build_historical_ndvi_analysis(...)"]
        Root --> Out["HistoricalNdviAnalysis\n(pipeline_version='2.0.0')"]
    end
```

### Architectural Principles & Boundaries for Earth Engine Integration
1. **Human-Centric Abstraction (`DEC-003`):** Farmers are never asked to enter raw coordinates or technical spatial projections. The frontend resolves human inputs (village name, PIN code, map tap) to spatial coordinates.
2. **Layered Integration Boundary (`DEC-004`):** The MCP server provides the capability tool contract, while Earth Engine initialization, image filtering, observation quality validation (`DEC-010`), band mathematics (`DEC-009`), and reducer operations live in an isolated module.
3. **Lean Statistical Aggregation First (`DEC-002`):** Compute robust zonal statistics (**mean**, **median**, **min**, **max**) for the farm area rather than transmitting heavy raster image arrays to LLMs.
4. **Pure Local Mathematics Boundary (`DEC-017`):** Earth Engine is strictly limited to remote pixel filtering, masking, compositing, and zonal reductions (`historical.py`). All multi-year statistical distributions, dispersion metrics, sufficiency evaluations, metric gating, and departure classifications execute as deterministic, pure-Python logic without Earth Engine dependencies (`baseline.py`, `historical_analysis.py`).
5. **Pluggable Data Source Architecture:** The Earth Engine client implements a decoupled provider interface so that future datasets (Dynamic World LULC, NDWI moisture, soil grids) can be plugged in without refactoring the core multi-agent workflow.

---

## 🌦️ Agricultural & Environmental Context Architecture (`🟢 PHASE 3A & 3B COMPLETE & VERIFIED / DEC-018, DEC-019, DEC-020`)

Phase 3 introduces physical meteorological, hydrological, and land-cover context layers to explain the physical drivers behind satellite vegetation signals:

```mermaid
graph TD
    subgraph EarthEngineCatalog ["Google Earth Engine Catalog"]
        ERA["ECMWF/ERA5_LAND/DAILY_AGGR\n(Daily Reanalysis, ~11.1 km)"]
        CHIRPS["UCSB-CHC/CHIRPS/V3/DAILY_SAT\n(Satellite Precipitation, ~5.566 km)"]
    end

    subgraph DataExtraction ["1. Remote Extraction Layer (ee.Reducer.mean)"]
        ERA --> QueryERA["90-Day Range Query [E-89, E+1)\n(scale=11132m)"]
        CHIRPS --> QueryCHIRPS["90-Day Range Query [E-89, E+1)\n(scale=5566m)"]
    end

    subgraph ValidationEngine ["2. Pure Math & Validation Engine (0 EE Calls)"]
        QueryERA --> NormERA["ERA5 Normalization & Validation\n(K -> °C, m -> mm, SW [0, 1])"]
        QueryCHIRPS --> NormCHIRPS["CHIRPS Normalization & Validation\n(1:1 mm/day, Reject < 0.0)"]
        NormERA --> WinERA["ERA5 Window Aggregator\n(7d, 30d, 90d Envelopes)"]
        NormCHIRPS --> WinCHIRPS["CHIRPS Rainfall Window Aggregator\n(7d, 30d, 90d Total/Mean/Max)"]
    end

    subgraph DomainAssembly ["3. Root Domain Payload Composition (0 EE Calls)"]
        WinERA --> OutERA["ERA5LandAnalysis\n(pipeline_version='3.0.0')"]
        WinCHIRPS --> OutCHIRPS["CHIRPSRainfallAnalysis\n(pipeline_version='3.1.0')"]
    end
```

### Key Architectural Tenets for Phase 3:
1. **Subsystem Independence:** ERA5-Land (Phase 3A) and CHIRPS (Phase 3B) are strictly independent subsystems with dedicated domain contracts (`ERA5LandAnalysis` vs `CHIRPSRainfallAnalysis`). Cross-source comparison and fusion are strictly deferred to Phase 4.
2. **Separation of Measurement from Agronomic Interpretation:** Phase 3 produces pure physical observations (temperature in $^\circ\text{C}$, precipitation in $\text{mm}$, soil water in $\text{m}^3/\text{m}^3$, runoff in $\text{mm}$). Drought, heat stress, and irrigation classifications are strictly deferred to Phase 4 (Fusion) and Phase 5 (Reasoning).
3. **Explicit Reanalysis & Satellite Data Lag:** Datasets exhibit publication latency. Domain contracts track `requested_end_date`, `latest_available_date`, and `data_lag_days` dynamically rather than hardcoding static constants or misrepresenting observations as real-time forecasts.
4. **Coarse Regional Context Non-Claim:** Standardized at $\approx 11.1\text{ km}$ (ERA5-Land) and $\approx 5.566\text{ km}$ (CHIRPS), environmental outputs represent coarse regional context and are never claimed as field-scale (100m) parcel measurements. Zero synthetic downscaling, continuous interpolation, or unverified sub-pixel weighting claims are prohibited.
5. **Missing Data & Artifact Invariants:** Missing precipitation is never converted to $0.0\text{ mm}$; negative values ($< 0.0$) from GEE data-packing artifacts are rejected as invalid (never silently clamped to 0.0).
6. **Partial-Window Available-Observation Semantics:** For incomplete windows (`is_complete=False`), metric totals and averages represent observed totals/means over available non-null observations, NOT complete-window totals or zero-filled averages. Prohibits imputation or interpolation for missing dates.




