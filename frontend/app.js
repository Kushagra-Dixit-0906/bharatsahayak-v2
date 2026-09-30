/**
 * BharatSahayak — Phase 9 Farmer UI
 * ====================================
 * Presentation-layer only.  All agricultural intelligence lives
 * in the sealed Phase 8 backend (app/).
 *
 * KEY DESIGN PRINCIPLE:
 *   ADK events are internal implementation details.
 *   The farmer sees exactly ONE assistant message per request turn.
 *   HITL interrupts become interactive UI cards, not raw text.
 */

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

/** All API calls go through relative paths to target the same origin. */
const API_BASE = "/api";

/** Environmental query detection keywords (EN + HI). */
const ENV_KEYWORDS = [
  "farm environment", "satellite", "environmental", "soil moisture",
  "ndvi", "vegetation", "crop conditions", "analyze my farm",
  "earth engine", "chirps", "rainfall analysis", "era5",
  "sentinel", "land cover", "farm analysis", "climate analysis",
  "खेत पर्यावरण", "मिट्टी", "उपग्रह", "वर्षा", "पर्यावरण", "मिट्टी की नमी",
];

/** Government-scheme query detection keywords (EN + HI). */
const SCHEME_KEYWORDS = [
  "government scheme", "subsidy", "pm-kisan", "pmfby", "yojana",
  "government help", "government aid", "government program",
  "सरकारी योजना", "सब्सिडी", "योजना", "सरकारी मदद", "अनुदान",
];

/** All 28 Indian States and 8 Union Territories. */
const INDIAN_STATES = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh",
  "Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka",
  "Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram",
  "Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana",
  "Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
  "Andaman & Nicobar Islands","Chandigarh",
  "Dadra & Nagar Haveli and Daman & Diu","Delhi (NCT)",
  "Jammu & Kashmir","Ladakh","Lakshadweep","Puducherry",
];

// ═══════════════════════════════════════════════════════════════
// I18N — UI strings only.  Backend responses are not rewritten.
// ═══════════════════════════════════════════════════════════════

const I18N = {
  en: {
    empty_greeting:   "Namaste! 🙏",
    empty_subtext:    "How can I help you with farming today?",
    input_placeholder:"Ask anything about your farm…",
    qa_crop_title:    "Crop Advice",
    qa_crop_desc:     "Recommendations for your region",
    qa_weather_title: "Weather",
    qa_weather_desc:  "Forecasts & farming advisories",
    qa_schemes_title: "Government Schemes",
    qa_schemes_desc:  "Subsidies & eligibility",
    qa_disease_title: "Crop Problem",
    qa_disease_desc:  "Disease & pest advisory",
    qa_env_title:     "Farm Environment",
    qa_env_desc:      "Satellite analysis of your farm",

    loc_title:        "📍 Farm location needed",
    loc_desc:         "To analyze the environmental conditions around your farm, I need your farm's location.",
    use_gps:          "📍 Use my current location",
    or:               "or enter manually",
    coord_label:      "Farm coordinates",
    coord_hint:       "e.g. 26.8462, 80.9490",
    coord_example:    "Paste coordinates from Google Maps, e.g. 26.8462, 80.9490",
    continue_btn:     "Continue",
    gps_locating:     "Locating…",
    gps_found:        "✅ Location found:",
    gps_denied:       "Location access denied. Please enter coordinates below.",
    gps_error:        "Could not access GPS. Please enter coordinates below.",
    coord_invalid:    "Please enter valid coordinates (e.g. 26.8462, 80.9490. Lat: −90 to 90, Lon: −180 to 180).",

    schemes_followup: "Would you also like to see schemes specific to your state/UT?",
    schemes_yes:      "Yes, show me state schemes",
    schemes_no:       "No thanks",
    state_label:      "Select your state / union territory",
    state_prompt:     "— Choose a state or UT —",
    schemes_no_resp:  "No problem! Feel free to ask me anything else about your farm. 🌾",

    hitl_send:        "Send",
    season_prompt:    "Choose a season:",
    kharif:           "Kharif",
    rabi:             "Rabi",
    zaid:             "Zaid",

    evidence_show:    "🔍 Why? / Evidence & Data Freshness",
    evidence_hide:    "Hide details",

    loading_status:   "🌾 BharatSahayak is checking your request...",
    err_network:      "Network error — please check your connection and try again.",
    err_server:       "Something went wrong. Please try again in a moment.",
    err_init:         "Could not connect to BharatSahayak. Is the server running?",
  },

  hi: {
    empty_greeting:   "नमस्ते! 🙏",
    empty_subtext:    "आज मैं आपकी खेती में कैसे मदद कर सकता हूँ?",
    input_placeholder:"अपने खेत के बारे में कुछ भी पूछें…",
    qa_crop_title:    "फसल सलाह",
    qa_crop_desc:     "आपके क्षेत्र के लिए अनुशंसाएं",
    qa_weather_title: "मौसम",
    qa_weather_desc:  "पूर्वानुमान और कृषि सलाह",
    qa_schemes_title: "सरकारी योजनाएं",
    qa_schemes_desc:  "सब्सिडी और पात्रता",
    qa_disease_title: "फसल समस्या",
    qa_disease_desc:  "रोग और कीट सलाह",
    qa_env_title:     "खेत पर्यावरण",
    qa_env_desc:      "आपके खेत का उपग्रह विश्लेषण",

    loc_title:        "📍 खेत का स्थान आवश्यक है",
    loc_desc:         "आपके खेत की पर्यावरणीय स्थिति का विश्लेषण करने के लिए, मुझे आपके खेत का स्थान चाहिए।",
    use_gps:          "📍 मेरी वर्तमान स्थिति उपयोग करें",
    or:               "या मैन्युअल रूप से दर्ज करें",
    coord_label:      "खेत के निर्देशांक (Coordinates)",
    coord_hint:       "जैसे 26.8462, 80.9490",
    coord_example:    "Google Maps से निर्देशांक पेस्ट करें, जैसे 26.8462, 80.9490",
    continue_btn:     "जारी रखें",
    gps_locating:     "स्थान खोजा जा रहा है…",
    gps_found:        "✅ स्थान मिला:",
    gps_denied:       "स्थान की अनुमति नहीं मिली। कृपया नीचे निर्देशांक दर्ज करें।",
    gps_error:        "GPS नहीं मिल सका। कृपया नीचे निर्देशांक दर्ज करें।",
    coord_invalid:    "कृपया सही निर्देशांक दर्ज करें (जैसे 26.8462, 80.9490। अक्षांश: −90 से 90, देशांतर: −180 से 180)।",

    schemes_followup: "क्या आप अपने राज्य/केंद्रशासित प्रदेश की विशेष योजनाएं भी देखना चाहेंगे?",
    schemes_yes:      "हाँ, राज्य योजनाएं दिखाएं",
    schemes_no:       "नहीं, धन्यवाद",
    state_label:      "अपना राज्य / केंद्रशासित प्रदेश चुनें",
    state_prompt:     "— राज्य या केंद्रशासित प्रदेश चुनें —",
    schemes_no_resp:  "कोई बात नहीं! खेती के बारे में कुछ और पूछें। 🌾",

    hitl_send:        "भेजें",
    season_prompt:    "मौसम चुनें:",
    kharif:           "खरीफ",
    rabi:             "रबी",
    zaid:             "ज़ायद",

    evidence_show:    "🔍 क्यों? / साक्ष्य और डेटा ताजगी",
    evidence_hide:    "विवरण छुपाएं",

    loading_status:   "🌾 BharatSahayak जानकारी देख रहा है...",
    err_network:      "नेटवर्क त्रुटि — कृपया अपना कनेक्शन जांचें और पुनः प्रयास करें।",
    err_server:       "कुछ गड़बड़ हो गई। कृपया एक पल बाद पुनः प्रयास करें।",
    err_init:         "BharatSahayak से कनेक्ट नहीं हो सका। क्या सर्वर चल रहा है?",
  },
};

// ═══════════════════════════════════════════════════════════════
// APPLICATION STATE
// ═══════════════════════════════════════════════════════════════

const S = {
  lang:             "en",   // current UI language
  sessionId:        null,
  userId:           null,
  lat:              null,   // verified farm coordinates
  lon:              null,
  pendingEnvMsg:    null,   // env query held while awaiting coordinates
  lastWasSchemes:   false,  // whether to append schemes follow-up
  lastSchemesState: null,   // tracks selected state for response labelling
  hasMessages:      false,
  isLoading:        false,
};

// ═══════════════════════════════════════════════════════════════
// TRANSLATION HELPER
// ═══════════════════════════════════════════════════════════════

const t = (key) => (I18N[S.lang] || I18N.en)[key] || key;

// ═══════════════════════════════════════════════════════════════
// QUERY CLASSIFIERS
// ═══════════════════════════════════════════════════════════════

function isEnvQuery(text)     { const l = text.toLowerCase(); return ENV_KEYWORDS.some(k => l.includes(k)); }
function isSchemesQuery(text) { const l = text.toLowerCase(); return SCHEME_KEYWORDS.some(k => l.includes(k)); }

// ═══════════════════════════════════════════════════════════════
// API LAYER
// ═══════════════════════════════════════════════════════════════

async function apiSession() {
  const r = await fetch(`${API_BASE}/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language: S.lang }),
  });
  if (!r.ok) throw new Error("session_failed");
  return r.json();
}

async function apiRun(message) {
  const r = await fetch(`${API_BASE}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: S.sessionId,
      user_id: S.userId,
      message,
    }),
  });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || "run_failed"); }
  return r.json();
}

async function apiResume(interruptId, result) {
  const lang = detectInputLanguage(result);
  if (lang) {
    setLang(lang);
  }
  const r = await fetch(`${API_BASE}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: S.sessionId,
      user_id: S.userId,
      resume: { interrupt_id: interruptId, result },
    }),
  });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || "resume_failed"); }
  return r.json();
}

// ═══════════════════════════════════════════════════════════════
// ADK EVENT ADAPTER  ← the critical abstraction layer
// ═══════════════════════════════════════════════════════════════

/**
 * parseAdkEventStream
 * --------------------
 * Reduces the raw ADK event array (8–20+ events per turn) into exactly
 * ONE presentation-layer object the UI can render.
 *
 * Priority:
 *   1. HITL RequestInput  → { type:"hitl",     interruptId, message }
 *   2. Canonical terminal → { type:"response",  text }
 *      Prefers bharatsahayak_workflow author (format_final_output node).
 *      Falls back to last model-role content event with non-empty text.
 *      Last resort: last non-internal scalar output string.
 *   3. Error              → { type:"error",     text }
 *
 * Never exposes:
 *   - intermediate orchestrator JSON payloads
 *   - node IDs / agent names / tool names
 *   - raw ADK events
 *   - duplicate responses
 */
function parseAdkEventStream(events) {
  if (!Array.isArray(events)) {
    return { type: "error", text: t("err_server") };
  }
  if (events.length === 0) {
    return { type: "response", text: t("err_server") };
  }

  // ── 1. HITL detection (scan forward) ──────────────────────────
  for (const ev of events) {
    const parts = ev?.content?.parts || [];
    for (const p of parts) {
      if (p.functionCall && p.functionCall.name === "adk_request_input") {
        return {
          type:        "hitl",
          interruptId: p.functionCall.id || "more_info",
          message:     p.functionCall.args?.message || "",
        };
      }
    }
  }

  // ── 2. Prefer bharatsahayak_workflow model-content (canonical) ─
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev?.author !== "bharatsahayak_workflow") continue;
    if (ev?.content?.role !== "model") continue;
    const text = extractText(ev.content.parts);
    if (text) return { type: "response", text };
  }

  // ── 3. Fall back: last model-role content with any non-empty text ─
  for (let i = events.length - 1; i >= 0; i--) {
    const ev = events[i];
    if (ev?.content?.role !== "model") continue;
    const text = extractText(ev.content.parts);
    if (!text) continue;
    // Skip raw internal JSON payloads (intermediate orchestrator turns)
    if (text.trimStart().startsWith("{")) continue;
    return { type: "response", text };
  }

  // ── 4. Last resort: scalar output string ──────────────────────
  for (let i = events.length - 1; i >= 0; i--) {
    const out = events[i]?.output;
    if (typeof out !== "string" || !out.trim()) continue;
    if (out.startsWith("Farmer Profile:")) continue;   // internal prompt
    if (out.trimStart().startsWith("{")) continue;     // raw JSON
    return { type: "response", text: out };
  }

  return { type: "error", text: t("err_server") };
}

/** Extract and join text parts; return empty string if none. */
function extractText(parts) {
  if (!Array.isArray(parts)) return "";
  return parts
    .filter(p => typeof p.text === "string" && p.text.trim())
    .map(p => p.text)
    .join("") || "";
}

// ═══════════════════════════════════════════════════════════════
// DOM HELPERS
// ═══════════════════════════════════════════════════════════════

const $  = (id) => document.getElementById(id);
const qs = (sel, root = document) => root.querySelector(sel);

function scrollBottom() {
  const ca = $("chat-area");
  if (ca) requestAnimationFrame(() => { ca.scrollTop = ca.scrollHeight; });
}

function setLoading(on) {
  S.isLoading = on;
  const btn   = $("send-btn");
  const input = $("msg-input");
  if (on) {
    showTyping();
    if (btn)   btn.disabled   = true;
    if (input) input.disabled = true;
  } else {
    hideTyping();
    if (input) input.disabled = false;
    updateSendBtn();
  }
}

function updateSendBtn() {
  const btn   = $("send-btn");
  const input = $("msg-input");
  if (btn) btn.disabled = !input?.value.trim() || S.isLoading;
}

function syncEmptyState() {
  const empty = $("empty-state");
  const qa    = $("quick-actions");
  if (!empty || !qa) return;
  if (S.hasMessages) {
    empty.style.display = "none";
    qa.classList.add("hidden");
  } else {
    empty.style.display = "";
    qa.classList.remove("hidden");
  }
}

// ═══════════════════════════════════════════════════════════════
// TYPING INDICATOR
// ═══════════════════════════════════════════════════════════════

function showTyping() {
  if ($("typing-indicator")) return;
  const msgs = $("messages");
  if (!msgs) return;
  const el = document.createElement("div");
  el.id = "typing-indicator";
  el.className = "typing-indicator";
  el.setAttribute("aria-label", "Loading");
  el.innerHTML = `
    <span class="typing-status">${esc(t("loading_status"))}</span>
    <span class="typing-dots"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span>
  `;
  msgs.appendChild(el);
  scrollBottom();
}

function hideTyping() {
  $("typing-indicator")?.remove();
}

// ═══════════════════════════════════════════════════════════════
// TEXT UTILITIES
// ═══════════════════════════════════════════════════════════════

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/**
 * Enhanced lightweight markdown / structured text renderer.
 * Formats headings, bullet lists, bold/italic, and clean spacing
 * while preserving backend content and exact data values.
 */
function renderMd(text) {
  if (!text) return "";
  const lines = text.split("\n");
  const htmlLines = [];
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      if (inList) {
        htmlLines.push("</ul>");
        inList = false;
      }
      htmlLines.push('<div class="section-break"></div>');
      continue;
    }

    // Escape raw HTML characters first
    let escaped = esc(trimmed);
    // Replace **bold** with <strong>bold</strong>
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // Replace *italic* with <em>italic</em>
    escaped = escaped.replace(/(^|[^*])\*([^*]+)\*([^*]|$)/g, "$1<em>$2</em>$3");

    // Headings: ###, ##, #
    if (trimmed.startsWith("### ")) {
      if (inList) { htmlLines.push("</ul>"); inList = false; }
      htmlLines.push(`<h3>${escaped.replace(/^###\s+/, "")}</h3>`);
      continue;
    }
    if (trimmed.startsWith("## ")) {
      if (inList) { htmlLines.push("</ul>"); inList = false; }
      htmlLines.push(`<h2>${escaped.replace(/^##\s+/, "")}</h2>`);
      continue;
    }
    if (trimmed.startsWith("# ")) {
      if (inList) { htmlLines.push("</ul>"); inList = false; }
      htmlLines.push(`<h2>${escaped.replace(/^#\s+/, "")}</h2>`);
      continue;
    }

    // Bullet lists: •, -, *, 1., 2. etc
    const bulletMatch = escaped.match(/^([•\-\*]|\d+\.)\s+(.+)$/);
    if (bulletMatch) {
      if (!inList) {
        htmlLines.push("<ul>");
        inList = true;
      }
      htmlLines.push(`<li>${bulletMatch[2]}</li>`);
      continue;
    }

    // Regular text line
    if (inList) {
      htmlLines.push("</ul>");
      inList = false;
    }
    htmlLines.push(`<p>${escaped}</p>`);
  }

  if (inList) {
    htmlLines.push("</ul>");
  }

  return htmlLines.join("");
}

/**
 * Split the backend response into a primary section and an optional
 * evidence section.  Evidence starts at "Limitations & Data Freshness:".
 */
function splitEvidence(text) {
  const markers = ["Limitations & Data Freshness:", "सीमाएं व डेटा ताजगी:"];
  for (const m of markers) {
    const idx = text.indexOf(m);
    if (idx !== -1) {
      return { primary: text.slice(0, idx).trim(), evidence: text.slice(idx).trim() };
    }
  }
  return { primary: text, evidence: null };
}

// ═══════════════════════════════════════════════════════════════
// CHAT BUBBLE RENDERERS
// ═══════════════════════════════════════════════════════════════

function addUserBubble(text) {
  const msgs = $("messages");
  if (!msgs) return;
  S.hasMessages = true;
  syncEmptyState();
  const d = document.createElement("div");
  d.className = "msg user";
  d.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  msgs.appendChild(d);
  scrollBottom();
}

function addAssistantBubble(text) {
  const msgs = $("messages");
  if (!msgs) return;
  S.hasMessages = true;
  syncEmptyState();

  const { primary, evidence } = splitEvidence(text);
  const evId = "ev-" + Date.now();

  let inner = `<div class="bubble">${renderMd(primary)}</div>`;

  if (evidence) {
    inner += `
      <div class="evidence-wrapper">
        <button class="evidence-toggle" aria-expanded="false"
                aria-controls="${evId}"
                onclick="toggleEvidence(this,'${evId}')">
          <span class="ev-label">${esc(t("evidence_show"))}</span>
          <svg class="ev-arrow" width="12" height="8" viewBox="0 0 12 8"
               fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <polyline points="1 1 6 7 11 1"/>
          </svg>
        </button>
        <div id="${evId}" class="evidence-body" hidden>${esc(evidence)}</div>
      </div>`;
  }

  const d = document.createElement("div");
  d.className = "msg assistant";
  d.innerHTML = inner;
  msgs.appendChild(d);
  scrollBottom();
}

function addErrorBubble(text) {
  const msgs = $("messages");
  if (!msgs) return;
  S.hasMessages = true;
  syncEmptyState();
  const d = document.createElement("div");
  d.className = "msg error";
  d.innerHTML = `<div class="bubble">⚠️ ${esc(text)}</div>`;
  msgs.appendChild(d);
  scrollBottom();
}

window.toggleEvidence = function(btn, id) {
  const body = $(id);
  if (!body) return;
  const open = btn.getAttribute("aria-expanded") === "true";
  btn.setAttribute("aria-expanded", !open);
  body.hidden = open;
  qs(".ev-label", btn).textContent = open ? t("evidence_show") : t("evidence_hide");
};

// ═══════════════════════════════════════════════════════════════
// LOCATION CARD
// ═══════════════════════════════════════════════════════════════

function addLocationCard() {
  if ($("location-card")) return;  // already showing
  const msgs = $("messages");
  if (!msgs) return;
  S.hasMessages = true;
  syncEmptyState();

  const card = document.createElement("div");
  card.id = "location-card";
  card.className = "card";
  card.setAttribute("role", "region");
  card.setAttribute("aria-label", "Farm location input");

  card.innerHTML = `
    <div class="card-title">${esc(t("loc_title"))}</div>
    <div class="card-desc">${esc(t("loc_desc"))}</div>

    <button id="gps-btn" class="btn-primary btn-large" style="margin-bottom:10px"
            onclick="onGpsClick()" type="button">
      ${esc(t("use_gps"))}
    </button>

    <div id="coord-status" class="coord-status"></div>

    <div class="card-divider">${esc(t("or"))}</div>

    <div class="coord-field-single">
      <label for="coord-input">${esc(t("coord_label"))}</label>
      <input id="coord-input" type="text"
             placeholder="${esc(t("coord_hint"))}"
             aria-describedby="coord-desc" />
      <div id="coord-desc" class="field-hint">${esc(t("coord_example"))}</div>
    </div>

    <button class="btn-primary btn-large" style="margin-top:6px"
            onclick="onManualCoords()" type="button">
      ${esc(t("continue_btn"))}
    </button>
  `;

  msgs.appendChild(card);
  scrollBottom();
}

function showCoordStatus(type, msg) {
  const el = $("coord-status");
  if (!el) return;
  el.className = `coord-status ${type} show`;
  el.textContent = msg;
}

/** Parses Google Maps style coordinates: "26.8462, 80.9490", "26.8462,80.9490", "-26.8, 80.9" */
function parseCoordinates(text) {
  if (!text || typeof text !== "string") return null;
  const s = text.trim();
  const m = s.match(/^(?:lat(?:itude)?\s*[:=]?\s*)?([+-]?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(?:lon(?:gitude)?\s*[:=]?\s*)?([+-]?\d{1,3}(?:\.\d+)?)$/i);
  if (!m) return null;
  const lat = parseFloat(m[1]);
  const lon = parseFloat(m[2]);
  if (isNaN(lat) || isNaN(lon)) return null;
  if (lat < -90.0 || lat > 90.0 || lon < -180.0 || lon > 180.0) return null;
  return { lat, lon };
}

window.onGpsClick = function () {
  if (!navigator.geolocation) { showCoordStatus("error", t("gps_error")); return; }

  const btn = $("gps-btn");
  if (btn) { btn.disabled = true; btn.textContent = t("gps_locating"); }
  showCoordStatus("info", t("gps_locating"));

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = +pos.coords.latitude.toFixed(6);
      const lon = +pos.coords.longitude.toFixed(6);
      if (btn) { btn.disabled = false; btn.textContent = t("use_gps"); }

      const ci = $("coord-input");
      if (ci) ci.value = `${lat}, ${lon}`;

      showCoordStatus("success", `${t("gps_found")} ${lat}, ${lon}`);
      // Brief pause so the user sees the confirmation, then auto-submit
      setTimeout(() => submitCoords(lat, lon), 700);
    },
    (err) => {
      if (btn) { btn.disabled = false; btn.textContent = t("use_gps"); }
      showCoordStatus("error", err.code === 1 ? t("gps_denied") : t("gps_error"));
      $("coord-input")?.focus();
    },
    { timeout: 15_000, maximumAge: 60_000 }
  );
};

window.onManualCoords = function () {
  const coordEl = $("coord-input");
  const parsed = parseCoordinates(coordEl?.value);

  if (!parsed) {
    showCoordStatus("error", t("coord_invalid"));
    coordEl?.classList.add("input-error");
    return;
  }
  coordEl?.classList.remove("input-error");
  submitCoords(parsed.lat, parsed.lon);
};

async function submitCoords(lat, lon) {
  $("location-card")?.remove();
  S.lat = lat; S.lon = lon;

  const query = S.pendingEnvMsg || `Analyze the farm environment at coordinates ${lat}, ${lon}`;
  S.pendingEnvMsg = null;

  addUserBubble(`${query}  (📍 ${lat}, ${lon})`);
  await doRun(`${query}  My farm coordinates are: ${lat}, ${lon}.`, false);
}

// ═══════════════════════════════════════════════════════════════
// HITL CARD
// ═══════════════════════════════════════════════════════════════

function addHitlCard(interruptId, message) {
  const msgs = $("messages");
  if (!msgs) return;
  S.hasMessages = true;
  syncEmptyState();

  // Detect season-type HITL from message text
  const isSeason = /kharif|rabi|zaid|खरीफ|रबी|ज़ायद/i.test(message);

  const card = document.createElement("div");
  card.className = "card hitl-card";
  card.id = "hitl-card";
  card.setAttribute("role", "region");
  card.setAttribute("aria-label", "Additional information required");

  if (isSeason) {
    card.innerHTML = `
      <div class="card-title">🌾 ${esc(message)}</div>
      <div class="season-btns">
        <button class="season-btn" type="button"
                onclick="onHitlSubmit('${interruptId}','Kharif')">${esc(t("kharif"))}</button>
        <button class="season-btn" type="button"
                onclick="onHitlSubmit('${interruptId}','Rabi')">${esc(t("rabi"))}</button>
        <button class="season-btn" type="button"
                onclick="onHitlSubmit('${interruptId}','Zaid')">${esc(t("zaid"))}</button>
      </div>`;
  } else {
    card.innerHTML = `
      <div class="card-title">💬 ${esc(message)}</div>
      <input class="hitl-input" id="hitl-text" type="text"
             placeholder="${esc(t("input_placeholder"))}" />
      <button class="btn-primary btn-large" type="button"
              onclick="onHitlTextSubmit('${interruptId}')">
        ${esc(t("hitl_send"))}
      </button>`;
  }

  msgs.appendChild(card);
  scrollBottom();
}

window.onHitlSubmit = async function (interruptId, result) {
  $("hitl-card")?.remove();
  addUserBubble(result);
  setLoading(true);
  try {
    const events = await apiResume(interruptId, result);
    handleParsed(parseAdkEventStream(events), "");
  } catch (e) {
    addErrorBubble(t(isNetworkError(e) ? "err_network" : "err_server"));
  } finally {
    setLoading(false);
  }
};

window.onHitlTextSubmit = function (interruptId) {
  const val = $("hitl-text")?.value.trim();
  if (val) window.onHitlSubmit(interruptId, val);
};

// ═══════════════════════════════════════════════════════════════
// GOVERNMENT SCHEMES FOLLOW-UP CARD
// ═══════════════════════════════════════════════════════════════

function addSchemesFollowup() {
  if ($("schemes-card")) return;
  const msgs = $("messages");
  if (!msgs) return;

  const card = document.createElement("div");
  card.className = "card";
  card.id = "schemes-card";
  card.innerHTML = `
    <div class="card-title">🏛️ ${esc(t("schemes_followup"))}</div>
    <div class="choice-btns">
      <button class="btn-primary" type="button" onclick="onSchemesYes()">
        ${esc(t("schemes_yes"))}
      </button>
      <button class="btn-outline" type="button" onclick="onSchemesNo()">
        ${esc(t("schemes_no"))}
      </button>
    </div>`;
  msgs.appendChild(card);
  scrollBottom();
}

window.onSchemesYes = function () {
  const card = $("schemes-card");
  if (!card) return;
  const opts = INDIAN_STATES
    .map(s => `<option value="${esc(s)}">${esc(s)}</option>`)
    .join("");
  card.innerHTML = `
    <div class="card-title">📍 ${esc(t("state_label"))}</div>
    <select class="state-select" id="state-sel" aria-label="${esc(t("state_label"))}">
      <option value="">${esc(t("state_prompt"))}</option>
      ${opts}
    </select>
    <button class="btn-primary btn-large" type="button" onclick="onStateSubmit()">
      ${esc(t("continue_btn"))}
    </button>`;
  scrollBottom();
};

window.onSchemesNo = async function () {
  $("schemes-card")?.remove();
  S.lastWasSchemes = false;
  addAssistantBubble(t("schemes_no_resp"));
};

window.onStateSubmit = async function () {
  const sel   = $("state-sel");
  const state = sel?.value;
  if (!state) return;
  $("schemes-card")?.remove();
  S.lastWasSchemes    = false;
  S.lastSchemesState  = state;   // remembered so handleParsed can label the response

  // Explicitly request only state-specific programs — do not repeat central schemes.
  const query =
    `Show me ONLY the state-specific agricultural schemes, subsidies, and support programs ` +
    `available in ${state}. Do not repeat the central government schemes (PM-KISAN, PMFBY, ` +
    `KCC, PMKSY, eNAM) that were already presented. Focus exclusively on programs run by ` +
    `the ${state} state government or union territory administration.`;

  addUserBubble(`📍 ${state} — state-specific schemes`);
  await doRun(query, false);
};

// ═══════════════════════════════════════════════════════════════
// CORE MESSAGE DISPATCH
// ═══════════════════════════════════════════════════════════════

/**
 * doRun — the single path through which every backend call flows.
 * @param {string}  text      — message to send to the backend
 * @param {boolean} addBubble — whether to add a user bubble first
 */
async function doRun(text, addBubble = true) {
  if (S.isLoading) return;
  if (addBubble) addUserBubble(text);
  setLoading(true);

  try {
    const events = await apiRun(text);
    handleParsed(parseAdkEventStream(events), text);
  } catch (e) {
    addErrorBubble(t(isNetworkError(e) ? "err_network" : "err_server"));
  } finally {
    setLoading(false);
  }
}

function isCentralSchemesQuery(text) {
  if (!isSchemesQuery(text)) return false;
  const l = text.toLowerCase();
  if (l.includes("state-specific") || l.includes("state schemes") || l.includes("state government") || l.includes("only the state")) return false;
  if (INDIAN_STATES.some(s => l.includes(s.toLowerCase()))) return false;
  return true;
}

/**
 * handleParsed — routes the presentation object to the correct UI component.
 */
function handleParsed(parsed, originalText) {
  if (parsed.type === "hitl") {
    addHitlCard(parsed.interruptId, parsed.message);

  } else if (parsed.type === "error") {
    addErrorBubble(parsed.text || t("err_server"));

  } else {
    // Normal assistant response — exactly ONE bubble.
    // If this is a state-specific response, prepend a clear location label
    // so it doesn't look like another generic central-scheme response.
    let displayText = parsed.text;
    const wasStateResponse = Boolean(S.lastSchemesState);
    if (S.lastSchemesState) {
      const stateLabel = `📍 ${S.lastSchemesState} — State-specific support\n\n`;
      // Only prepend if the backend didn't already include the label
      if (!displayText.includes("State-Specific") && !displayText.includes("📍")) {
        displayText = stateLabel + displayText;
      }
      S.lastSchemesState = null;
    }

    addAssistantBubble(displayText);

    // Append schemes follow-up card ONLY if this was a central-scheme query
    // and not a state-specific response or already in schemes flow
    if (isCentralSchemesQuery(originalText) && !wasStateResponse && !S.lastWasSchemes) {
      S.lastWasSchemes = true;
      setTimeout(addSchemesFollowup, 350);
    } else {
      S.lastWasSchemes = false;
    }
  }
}

function isNetworkError(e) {
  return e.message === "Failed to fetch"
      || e.message === "NetworkError when attempting to fetch resource."
      || e.message === "Load failed";
}

// ═══════════════════════════════════════════════════════════════
// QUICK ACTIONS
// ═══════════════════════════════════════════════════════════════

const QA_MSG = {
  crop:        () => S.lang === "hi"
    ? "मेरे क्षेत्र और मौसम के लिए सबसे अच्छी फसल की सिफारिश करें।"
    : "What crop should I grow for my region and current season?",
  weather:     () => S.lang === "hi"
    ? "मेरे खेत के लिए मौसम की जानकारी और कृषि सलाह दें।"
    : "Give me a weather advisory and farming tips for my area.",
  schemes:     () => S.lang === "hi"
    ? "किसानों के लिए उपलब्ध सरकारी योजनाएं और सब्सिडी बताएं।"
    : "Tell me about government schemes and subsidies available for farmers.",
  disease:     () => S.lang === "hi"
    ? "मेरी फसल में समस्या दिख रही है — बिना रासायनिक उपचार के सलाह दें।"
    : "My crops have a problem. Help me identify and manage it without chemicals.",
  environment: () => S.lang === "hi"
    ? "मेरे खेत की पर्यावरणीय स्थिति का विश्लेषण करें।"
    : "Analyze the environmental conditions around my farm.",
};

function setupQuickActions() {
  document.querySelectorAll(".qa-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      const msg = QA_MSG[action]?.();
      if (!msg) return;

      if (action === "environment" && S.lat === null) {
        S.pendingEnvMsg = msg;
        addUserBubble(msg);
        addLocationCard();
        return;
      }

      // Append verified coordinates to any environmental query
      const finalMsg = (action === "environment" && S.lat !== null)
        ? `${msg}  My farm coordinates are: ${S.lat}, ${S.lon}.`
        : msg;

      doRun(finalMsg);
    });
  });
}

function detectInputLanguage(text) {
  if (!text) return null;
  for (const char of text) {
    if (char >= "\u0900" && char <= "\u097f") {
      return "hi";
    }
  }
  const clean = text.trim().toLowerCase();
  const neutral = [
    "kharif", "rabi", "zaid", "yes", "no", "central", "state", "ok", "okay",
    "ha", "haan", "nahi", "nahi thanks", "up", "mp", "ap"
  ];
  if (neutral.includes(clean)) return null;
  if (INDIAN_STATES.some(s => s.toLowerCase() === clean)) return null;

  for (const char of text) {
    if ((char >= "a" && char <= "z") || (char >= "A" && char <= "Z")) {
      return "en";
    }
  }
  return null; // Numeric/symbols only -> preserve current language
}

function setLang(lang) {
  S.lang = lang;
  document.documentElement.lang = lang;

  // Sync all data-lang buttons (welcome screen)
  document.querySelectorAll("[data-lang]").forEach(el => {
    el.classList.toggle("active", el.dataset.lang === lang);
    el.setAttribute("aria-pressed", el.dataset.lang === lang ? "true" : "false");
  });

  // Update data-i18n text nodes
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const k = el.dataset.i18n;
    if (I18N[lang]?.[k]) el.textContent = I18N[lang][k];
  });

  // Update input placeholder
  const inp = $("msg-input");
  if (inp) inp.placeholder = t("input_placeholder");

  // Update empty-state
  const gr = $("empty-greeting"); if (gr) gr.textContent = t("empty_greeting");
  const st = $("empty-subtext");  if (st) st.textContent = t("empty_subtext");
}

// ═══════════════════════════════════════════════════════════════
// INPUT HANDLING
// ═══════════════════════════════════════════════════════════════

async function handleSubmit() {
  const inp = $("msg-input");
  if (!inp) return;
  const text = inp.value.trim();
  if (!text || S.isLoading) return;

  // Auto-detect input language and sync UI
  const detectedLang = detectInputLanguage(text);
  if (detectedLang) {
    setLang(detectedLang);
  }

  inp.value = "";
  updateSendBtn();

  // Pre-flight: environmental query without coordinates → show location card
  if (isEnvQuery(text) && S.lat === null) {
    S.pendingEnvMsg = text;
    addUserBubble(text);
    addLocationCard();
    return;
  }

  // Append coordinates if we have them and query is environmental
  const finalText = (isEnvQuery(text) && S.lat !== null)
    ? `${text}  My farm coordinates are: ${S.lat}, ${S.lon}.`
    : text;

  await doRun(finalText);
}

// ═══════════════════════════════════════════════════════════════
// WELCOME MODAL
// ═══════════════════════════════════════════════════════════════

function setupWelcome() {
  const overlay  = $("welcome-overlay");
  const startBtn = $("welcome-start");
  const closeBtn = $("welcome-close");

  // Welcome-screen language buttons (these update S.lang before starting)
  document.querySelectorAll(".lang-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".lang-btn").forEach(b => {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");
      S.lang = btn.dataset.lang;   // store choice; applied on start
    });
  });

  function startApp() {
    if (overlay) overlay.hidden = true;
    const app = $("app");
    if (app) app.hidden = false;
    setLang(S.lang);
    $("msg-input")?.focus();
  }

  startBtn?.addEventListener("click", startApp);
  closeBtn?.addEventListener("click", startApp);
  overlay?.addEventListener("click", e => { if (e.target === overlay) startApp(); });
  overlay?.addEventListener("keydown", e => { if (e.key === "Escape") startApp(); });
}

// ═══════════════════════════════════════════════════════════════
// HOME / BACK
// ═══════════════════════════════════════════════════════════════

/**
 * goHome — resets the chat UI to a fresh state without a page reload.
 * Creates a new ADK session so context is truly fresh.
 * Preserves the user's selected language.
 */
async function goHome() {
  // Clear all messages and in-flight cards
  const msgs = $("messages");
  if (msgs) msgs.innerHTML = "";
  $("location-card")?.remove();
  $("schemes-card")?.remove();
  $("hitl-card")?.remove();
  $("typing-indicator")?.remove();

  // Reset state completely (keep ONLY selected language preference)
  S.hasMessages      = false;
  S.isLoading        = false;
  S.pendingEnvMsg    = null;
  S.lastWasSchemes   = false;
  S.lastSchemesState = null;
  S.lat              = null;
  S.lon              = null;

  // Restore input
  const inp = $("msg-input");
  if (inp) { inp.value = ""; inp.disabled = false; }
  updateSendBtn();

  // Show empty state + quick actions
  syncEmptyState();

  // Fresh ADK session so backend context is clean
  try {
    const sess  = await apiSession();
    S.sessionId = sess.session_id;
    S.userId    = sess.user_id;
  } catch (e) {
    console.error("goHome: session refresh failed", e);
  }

  inp?.focus();
}

// ═══════════════════════════════════════════════════════════════
// INITIALISATION
// ═══════════════════════════════════════════════════════════════

async function init() {
  // Create ADK session
  try {
    const sess     = await apiSession();
    S.sessionId    = sess.session_id;
    S.userId       = sess.user_id;
  } catch (e) {
    // Surface error when first message is sent rather than blocking startup
    console.error("Session init failed:", e);
  }

  // Welcome modal
  setupWelcome();

  // Quick actions
  setupQuickActions();

  // Header brand / logo → go home
  $("header-brand-btn")?.addEventListener("click", goHome);

  // Input & send button
  const inp  = $("msg-input");
  const send = $("send-btn");

  inp?.addEventListener("input", updateSendBtn);
  inp?.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  });
  send?.addEventListener("click", handleSubmit);

  // Initial empty-state render
  syncEmptyState();
}

document.addEventListener("DOMContentLoaded", init);
