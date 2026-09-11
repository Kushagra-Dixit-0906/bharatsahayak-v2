# BharatSahayak V2 — Project Changelog

> **Chronological record of architectural changes, feature implementations, and documentation milestones.**  
> *Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).*

---

## [Unreleased] — Planned Phases 1 through 11

### 🟡 In Progress — Phase 1: Earth Engine Foundation (Subphase 1A)
- **Phase 1 Sub-Roadmap Established:** Defined detailed 1A–1K subphases in `docs/MASTER_ROADMAP.md` covering local environment, connectivity test, geometry definition, Sentinel-2 pipeline, NDVI calculation, regional statistics, reliability, boundary verification, and documentation.
- **Earth Engine Integration Boundary Documented (`DEC-004`):** Selected Option C (Layered Tool Contract with Dedicated Earth Engine Module) in `docs/DECISION_LOG.md` and `docs/ARCHITECTURE.md`.
- **Phase 1 Record Created:** Authored `docs/phases/PHASE_01_EARTH_ENGINE_FOUNDATION.md` detailing Before Snapshot, 1A design, and resume status.
- **Deferred Backlog Refined:** Updated `docs/FUTURE_BACKLOG.md` with decoupled integration areas and satellite enhancements.
- **Scope Boundary Maintained:** No Earth Engine application code implemented, no dependencies added, no authentication changes made.

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
