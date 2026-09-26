# Phase 2B — Historical Temporal Window & Seasonality Strategy
## Master Architectural Design Review & Specification

> **Status:** 🟢 APPROVED & SEALED (Phase 2B Complete & Sealed)  
> **Base Sealed Checkpoint:** `2e5f930 — docs: seal Phase 2A historical satellite architecture`  
> **Target Subphase:** Phase 2B — Temporal Window & Seasonality Strategy  
> **Implementation Code:** ZERO (Design & Specification Only)  

---

## 1. Executive Conclusion

This architectural design review establishes the formal temporal windowing and seasonality strategy for Phase 2 of BharatSahayak V2.

### Key Architectural Findings & Recommendations:
1. **Conceptual Basis vs. Implementation Mechanism:**  
   - **Day of Year (DOY)** provides the *conceptual foundation* for astronomical and seasonal comparability across multi-year agricultural cycles.
   - **Calendar-Date-Anchored Seasonal Windowing (Option B)** provides the *concrete implementation mechanism* for the MVP: the historical search window for each target year ($Y-1, Y-2, Y-3$) is constructed by anchoring the current observation's calendar date $(M_0, D_0)$ into each target historical year $Y_h$, and generating an exact $\pm 15$-day window $[T_h - 15\text{ days}, T_h + 15\text{ days}]$ (31 calendar days inclusive).
2. **Cross-Calendar-Year Window Ownership Rule:**  
   A historical seasonal window is **strictly owned by its target historical anchor year $Y_h$**. When a window crosses a calendar-year boundary (e.g., Dec 21 to Jan 20 for anchor Jan 5, $Y_h$), all qualifying satellite acquisitions within that continuous 31-day window—including acquisitions with timestamps in the adjacent calendar year—belong entirely to the seasonal baseline for anchor year $Y_h$. This is a *seasonal matching window*, not a strict calendar-year data partition.
3. **Leap-Year Handling Principle:**  
   **"Leap-year handling is a calendar correctness problem, not a crop-phenology correction problem."**  
   The operational 30-day temporal window ($\text{DOY} \pm 15$, 31 days inclusive) easily absorbs the $\approx 1$-day calendar displacement around February/March. Complex phenology normalization, curve fitting, and fractional-year interpolation are unnecessary and rejected for the MVP. Leap-year handling is strictly confined to standard calendar date validity (mapping February 29 to February 28 in common historical years).
4. **Year-Boundary Wrapping (Continuous Date Spans):**  
   When the reference observation occurs in early January ($D_0 \le 15$) or late December ($D_0 \ge 351$), the $\pm 15$-day window naturally crosses the calendar year boundary. Because calendar-date-anchored matching expresses temporal bounds as continuous ISO date strings (`YYYY-MM-DD`), Earth Engine filters these spans natively with a single `ee.Filter.date(start, end)` without requiring modulo arithmetic, disjoint day-of-year filtering, or artificial boundary clamping.
5. **UTC Date Basis:**  
   Sentinel-2 overpasses over India occur at approximately 10:30–11:00 AM IST (05:00–05:30 AM UTC), falling cleanly within the daytime UTC window. All observation timestamps, reference dates, and historical windows are strictly evaluated using **UTC calendar dates**, preserving the Phase 1 architectural contract.
6. **Earth Engine Representation:**  
   Each target historical year receives an explicit, deterministic continuous ISO date range $[S_h, E_h + 1\text{ day})$ matching Earth Engine's $[start, exclusive\_end)$ filter semantics.

---

## 2. Problem Definition

### 2.1 The Core Phase 2B Challenge
Phase 2A locked the historical baseline architecture to:
- **Historical Horizon:** Exactly 3 preceding calendar years ($Y-1, Y-2, Y-3$).
- **Temporal Window:** $\text{Reference DOY} \pm 15\text{ days}$ (30-day total seasonal window).
- **Historical Sampling:** Option C (Annual Matched-Window Regional Observations).

Phase 2B must define the exact, deterministic transformation:
```text
Current Authoritative Observation (UTC Timestamp)
                     ↓
        Reference Calendar Date (Y_0, M_0, D_0)
                     ↓
     Conceptual Reference Day of Year (DOY_0)
                     ↓
    Target Historical Years: Y_1 = Y_0 - 1
                             Y_2 = Y_0 - 2
                             Y_3 = Y_0 - 3
                     ↓
  Calendar-Date-Anchored Historical Ranges [Start, End]
                     ↓
       Earth Engine Temporal Filter Specification
```

### 2.2 System Design Requirements
The temporal window generator must satisfy five architectural invariants:
1. **Determinism:** Given an identical observation timestamp, produce identical historical search ranges on every invocation.
2. **Calendar Correctness:** Never generate invalid calendar dates (e.g., `2023-02-29`, `2024-00-00`, or DOY $< 1$ / $> 366$).
3. **Year-Boundary Robustness:** Correctly span the New Year for late December and early January observations.
4. **Phase 1 Compatibility:** Direct interoperability with `RegionalNdviAnalysis`, `Sentinel2ImageMetadata`, and `resolve_date_range`.
5. **Zero Over-Engineering:** Minimum implementation complexity, maximum unit testability, and zero unneeded ML/astronomical overhead.

---

## 3. Existing Phase 1 Date & Freshness Assumptions

An audit of the Phase 1 codebase (`app/satellite/`) confirms the following established conventions:

### 3.1 Metadata & Timestamp Representation
- **Acquisition Timestamp:** Stored as `Sentinel2ImageMetadata.acquisition_date` in standard ISO-8601 UTC format (`YYYY-MM-DDTHH:MM:SS+00:00`).
- **Earth Engine Milliseconds:** Stored as `Sentinel2ImageMetadata.system_time_start` (Unix epoch milliseconds, UTC).
- **Date Parser:** `_parse_date()` in `app/satellite/sentinel2.py` parses ISO strings, `datetime.date`, and `datetime.datetime` objects directly into Python `datetime.date` instances (stripping sub-day time components).

### 3.2 Date Range & Freshness Semantics
- **Lookback Window:** `resolve_date_range()` in `app/satellite/sentinel2.py` defaults to `lookback_days=30` relative to a resolved `end_date` (defaulting to `datetime.now(timezone.utc).date()`).
- **Observation Freshness:** `ObservationFreshness.observation_age_days` is computed in `app/satellite/pipeline.py` via pure calendar date subtraction:
  $$\text{observation\_age\_days} = (\text{reference\_date} - \text{acquisition\_date}).\text{days}$$
- **Earth Engine Date Filtering:** `ee.ImageCollection.filterDate(start_str, end_str)` is applied using ISO date strings (`YYYY-MM-DD`). In Earth Engine, `filterDate(start, end)` is a **half-open interval**:
  $$[\text{start\_timestamp}, \text{end\_timestamp})$$
  Where `start` is inclusive (midnight 00:00:00 UTC) and `end` is exclusive (midnight 00:00:00 UTC).

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1 AUDIT CONCLUSION:                                                               │
│ The existing implementation is strictly anchored to UTC calendar dates (YYYY-MM-DD).   │
│ There is zero ambiguity regarding timezone or calendar basis.                           │
│ Phase 2B MUST maintain strict UTC calendar-date compatibility.                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Day-of-Year (DOY) Definition & Conceptual Role

### 4.1 Formal Mathematical Definition
The Day of Year ($\text{DOY}$, or ordinal day $D$) represents the sequence number of a day within a given calendar year:
- **Common (Non-Leap) Year:** $D \in [1, 365]$
  - January 1 = $\text{DOY } 1$
  - February 28 = $\text{DOY } 59$
  - March 1 = $\text{DOY } 60$
  - December 31 = $\text{DOY } 365$
- **Leap Year:** $D \in [1, 366]$
  - January 1 = $\text{DOY } 1$
  - February 28 = $\text{DOY } 59$
  - February 29 = $\text{DOY } 60$
  - March 1 = $\text{DOY } 61$
  - December 31 = $\text{DOY } 366$

### 4.2 DOY as Conceptual Basis vs. Implementation Mechanism
It is vital to distinguish:
- **DOY as the Conceptual Basis:** DOY establishes astronomical and seasonal comparability across solar years (i.e. ensuring an observation in mid-monsoon is compared with mid-monsoon in preceding years).
- **Calendar-Date Arithmetic as the Implementation Mechanism:** In the MVP implementation, historical windows are generated via Python `datetime` and `timedelta` calendar arithmetic rather than server-side `ee.Filter.dayOfYear`. This prevents Earth Engine modulo and wrapping failure modes.

### 4.3 Derivation from Authoritative Observation
1. Given `acquisition_date` from `Sentinel2ImageMetadata` (e.g. `"2024-08-15T05:25:31+00:00"`).
2. Extract the UTC date component: `obs_date = datetime.date(2024, 8, 15)`.
3. Compute Reference Year: $Y_0 = \text{obs\_date.year} = 2024$.
4. Compute Reference DOY: $D_0 = \text{obs\_date.timetuple().tm\_yday} = 228$.

---

## 5. $\pm 15$-Day Window Semantics

### 5.1 Center and Span
- **Reference Center:** $D_0$
- **Temporal Half-Width:** $\Delta = 15\text{ days}$
- **Inclusive Range:** $[D_0 - 15, D_0 + 15]$

### 5.2 Boundary Inclusivity & Day Count
- **Inclusive Calendar Count:**
  $$\text{Day Count} = (D_0 + 15) - (D_0 - 15) + 1 = 31\text{ calendar days}$$
- **Semantic Structure:**
  - $15$ days preceding the reference date.
  - $1$ reference day itself.
  - $15$ days following the reference date.
  - Total: **31 consecutive calendar days** (commonly referred to as a "30-day temporal matching window" or "$\pm 15$-day window").

### 5.3 Earth Engine Boundary Contract
Because Earth Engine's `ee.Filter.date(start, end)` includes `start` (00:00:00 UTC) and excludes `end` (00:00:00 UTC), translating an inclusive calendar range $[\text{start\_date}, \text{end\_date}]$ to Earth Engine requires:
$$\text{ee\_start} = \text{start\_date.strftime}("\%Y-\%m-\%d")$$
$$\text{ee\_end} = (\text{end\_date} + \text{timedelta}(\text{days}=1)).\text{strftime}("\%Y-\%m-\%d")$$
This ensures all satellite acquisitions on `end_date` up to 23:59:59 UTC are captured.

---

## 6. Leap-Year Analysis & Complexity Control

### 6.1 Architectural Principle
> [!IMPORTANT]
> **"Leap-year handling is a calendar correctness problem, not a crop-phenology correction problem."**

### 6.2 The Scale of Leap-Year Displacement
A leap year introduces February 29, shifting subsequent calendar dates by 1 DOY relative to a common year.
- Our operational matching window is **31 calendar days** ($\pm 15$ days).
- A 1-day calendar displacement represents:
  $$\frac{1\text{ day}}{31\text{ days}} \approx 3.2\% \text{ of the temporal window}$$
- In Indian agricultural regimes, the 5-day Sentinel-2 revisit cycle, orbital track overlaps (2–3 days), and natural intra-seasonal monsoon dynamics far exceed a 1-day calendar shift.
- Introducing growing-degree-day (GDD) normalization, phenological curve-fitting, or fractional-year interpolation to adjust for a 24-hour astronomical shift would:
  - Add excessive mathematical complexity.
  - Require unverified agronomic crop parameters.
  - Violate Phase 2 architectural isolation.

### 6.3 Leap-Year Engineering Rule
1. Leap-year handling exists solely to ensure valid calendar operations.
2. Standard Python `datetime.timedelta(days=15)` arithmetic natively handles leap years, month boundaries, and leap-to-common year mappings.
3. If the current observation occurs on February 29 in a leap year, its anchor in common historical years maps deterministically to **February 28** (the last day of February).

---

## 7. February 28 / February 29 / March 1 Handling Matrix

The table below defines the deterministic mapping across all leap and common year configurations:

| Case | Current Observation Date | Current Year Type | Target Historical Year Type | Anchor Date in Historical Year | Historical Search Window $[S_h, E_h]$ (Inclusive) | Calendar Day Count |
|---|---|---|---|---|---|---|
| **A** | Feb 28 | Leap ($Y_0=2024$) | Common ($Y_h=2023$) | Feb 28, 2023 | Feb 13, 2023 – Mar 15, 2023 | 31 days |
| **B** | Feb 29 | Leap ($Y_0=2024$) | Common ($Y_h=2023$) | **Feb 28, 2023** *(clamped)* | Feb 13, 2023 – Mar 15, 2023 | 31 days |
| **C** | Mar 01 | Leap ($Y_0=2024$) | Common ($Y_h=2023$) | Mar 01, 2023 | Feb 14, 2023 – Mar 16, 2023 | 31 days |
| **D** | Feb 28 | Common ($Y_0=2023$) | Common ($Y_h=2022$) | Feb 28, 2022 | Feb 13, 2022 – Mar 15, 2022 | 31 days |
| **E** | Mar 01 | Common ($Y_0=2023$) | Common ($Y_h=2022$) | Mar 01, 2022 | Feb 14, 2022 – Mar 16, 2022 | 31 days |
| **F** | Feb 28 | Common ($Y_0=2025$) | **Leap ($Y_h=2024$)** | Feb 28, 2024 | Feb 13, 2024 – Mar 14, 2024 | 31 days |
| **G** | Mar 01 | Common ($Y_0=2025$) | **Leap ($Y_h=2024$)** | Mar 01, 2024 | Feb 15, 2024 – Mar 16, 2024 | 31 days |
| **H** | Feb 29 | Leap ($Y_0=2024$) | **Leap ($Y_h=2020$)** | Feb 29, 2020 | Feb 14, 2020 – Mar 15, 2020 | 31 days |

### Invariant Validation:
- Every generated historical window contains **exactly 31 inclusive calendar days**.
- Every date is a valid Gregorian calendar date.
- Zero Python `ValueError: day is out of range for month` exceptions can occur.

---

## 8. Year-Boundary Analysis & Window Ownership

### 8.1 The Year-Crossing Scenario
When an observation occurs within 15 days of January 1 or December 31, the $\pm 15$-day window spans two different calendar years.

#### Scenario 1: Early January Observation (e.g., January 5)
- Reference Date: `2024-01-05` ($D_0 = 5$).
- Window Span: 15 days before Jan 5 is **December 21 of the preceding year**.
- For Historical Target Year $Y_h = 2023$:
  - Start Date: `2022-12-21`
  - End Date: `2023-01-20`
  - Window: Continuous 31-day span crossing from $Y_h-1$ into $Y_h$.

#### Scenario 2: Late December Observation (e.g., December 25)
- Reference Date: `2023-12-25` ($D_0 = 359$).
- Window Span: 15 days after Dec 25 is **January 9 of the succeeding year**.
- For Historical Target Year $Y_h = 2022$:
  - Start Date: `2022-12-10`
  - End Date: `2023-01-09`
  - Window: Continuous 31-day span crossing from $Y_h$ into $Y_h+1$.

### 8.2 Year-Boundary Case Analysis

| Reference Date | Target Historical Year ($Y_h$) | Start Date ($S_h$) | End Date ($E_h$) | Crosses Year Boundary? | Calendar Days |
|---|---|---|---|---|---|
| **Jan 01** | 2023 | 2022-12-17 | 2023-01-16 | YES (from $Y_h-1$) | 31 |
| **Jan 05** | 2023 | 2022-12-21 | 2023-01-20 | YES (from $Y_h-1$) | 31 |
| **Jan 15** | 2023 | 2022-12-31 | 2023-01-30 | YES (from $Y_h-1$) | 31 |
| **Jan 16** | 2023 | 2023-01-01 | 2023-01-31 | NO (strictly inside $Y_h$) | 31 |
| **Dec 16** | 2022 | 2022-12-01 | 2022-12-31 | NO (strictly inside $Y_h$) | 31 |
| **Dec 20** | 2022 | 2022-12-05 | 2023-01-04 | YES (into $Y_h+1$) | 31 |
| **Dec 25** | 2022 | 2022-12-10 | 2023-01-09 | YES (into $Y_h+1$) | 31 |
| **Dec 31** | 2022 | 2022-12-16 | 2023-01-15 | YES (into $Y_h+1$) | 31 |

### 8.3 Why Calendar-Date-Anchored Windows Eliminate Wrapping Complexity
If temporal matching is implemented using pure DOY integers in Earth Engine (`ee.Filter.dayOfYear`), a window like `Jan 5` requires:
$$\text{Filter } 1: \text{DOY } 355–365 \text{ in Year } Y_h-1$$
$$\text{Filter } 2: \text{DOY } 1–20 \text{ in Year } Y_h$$
$$\text{Combined Filter}: \text{ee.Filter.Or}(\dots)$$

In contrast, by resolving the window to **calendar dates in Python**:
$$\text{start} = \text{"2022-12-21"}, \quad \text{end} = \text{"2023-01-21"}$$
$$\text{Single Filter}: \text{ee.Filter.date}(\text{"2022-12-21"}, \text{"2023-01-21"})$$
Earth Engine's `filterDate` accepts any continuous date range across years seamlessly.

### 8.4 Cross-Calendar-Year Window Ownership Rule for Phase 2C
Phase 2A mandates Option C historical sampling: producing **one annual matched-window regional NDVI value per represented historical year**. To prevent architectural ambiguity when a temporal window crosses a calendar-year boundary, the following ownership rule is established:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ CROSS-CALENDAR-YEAR WINDOW OWNERSHIP INVARIANT:                                         │
│ 1. A historical search window is STRICTLY OWNED by its target historical anchor year    │
│    (Y_h), regardless of whether its date span crosses into Y_h-1 or Y_h+1.             │
│ 2. The window represents a continuous SEASONAL MATCHING WINDOW for that agricultural   │
│    season, NOT an arbitrary calendar-year data partition.                               │
│ 3. All qualifying satellite scenes acquired within [S_h, E_h] belong entirely to       │
│    the annual observation for historical year Y_h.                                      │
│ 4. Phase 2C MUST NOT partition or split scenes across calendar years when computing    │
│    the annual regional value for target year Y_h.                                       │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Why This Avoids Ambiguity for Phase 2C:
1. **Strict 1:1 Mapping:** Establishes an unambiguous 1:1 relationship between target historical year $Y_h$ and its seasonal search window $[S_h, E_h]$, ensuring exactly one composite/regional value is produced for $Y_h$.
2. **Zero Orphaned Scenes:** Prevents complex split-partition logic where early January scenes in $Y_h+1$ or late December scenes in $Y_h-1$ could be orphaned or misallocated.
3. **No Double-Counting:** Each annual window for $Y-1, Y-2, Y-3$ operates on a disjoint 3-year seasonal sequence, ensuring no satellite scene is counted in more than one annual historical baseline value.

---

## 9. Calendar-Date vs DOY Strategy Trade-offs

We evaluate three technical strategies for constructing the historical window:

### Option A: Pure Day-of-Year Matching (`ee.Filter.dayOfYear`)
- **Mechanism:** Compute reference DOY $D_0 \in [1, 366]$. Apply `ee.Filter.dayOfYear(D_0 - 15, D_0 + 15)` combined with `ee.Filter.calendarRange(Y_min, Y_max, 'year')`.
- **Trade-offs:**
  - *Simplicity:* Conceptually simple for mid-year dates.
  - *Year Boundaries:* **Extremely fragile**. When $D_0 < 15$ or $D_0 > 351$, `ee.Filter.dayOfYear` fails because Earth Engine does not accept negative DOY or DOY $> 366$. Requires complex server-side branching (`ee.Filter.Or`) and custom year pairing.
  - *Leap Years:* Shifts DOY alignment by 1 day after Feb 29 between leap and non-leap years.
  - *Earth Engine Compatibility:* Adds graph complexity when linking Cloud Score+ collections.
  - *Off-by-One Risk:* High, especially around Dec 31 / Jan 1 and leap days.

### Option B: Calendar-Date-Anchored Seasonal Windowing (Python Date Ranges) — RECOMMENDED
- **Mechanism:** Extract $(M_0, D_0)$ from the current observation. In Python, construct the anchor date in each historical year $Y_h$ (handling Feb 29), compute `[anchor - 15 days, anchor + 15 days]`, and format as ISO date strings.
- **Trade-offs:**
  - *Simplicity:* Extremely simple. 100% standard Python `datetime` and `timedelta`.
  - *Year Boundaries:* **Seamless**. Python `timedelta` handles year crossings natively (`2024-01-05 - 15 days` = `2023-12-21`).
  - *Leap Years:* Deterministic handling via simple clamping (`Feb 29 -> Feb 28` in common years).
  - *Earth Engine Compatibility:* Native. Passes clean ISO date strings to standard `ee.Filter.date()`.
  - *Testability:* 100% testable in pure Python unit tests with zero Earth Engine dependencies or network calls.
  - *Off-by-One Risk:* Zero. Python standard library guarantees date arithmetic invariants.

### Option C: Hybrid / Normalized Fractional Seasonal Position
- **Mechanism:** Compute fractional position in the year $\theta = \frac{D_0}{\text{Days in Year}}$. For each historical year $Y_h$, compute $D_h = \text{round}(\theta \times \text{Days in } Y_h)$ and generate windows based on fractional offsets.
- **Trade-offs:**
  - *Complexity:* Introduces additional mathematical and implementation complexity without sufficient empirical evidence that this added complexity provides meaningful benefit over the existing $\pm 15$-day calendar window.
  - *Year Boundaries:* Still requires wrap-around logic.
  - *Recommendation:* Deferred for the MVP.

### Trade-off Comparison Matrix

| Evaluation Dimension | Option A (Pure DOY) | Option B (Date-Anchored) | Option C (Fractional DOY) |
|---|---|---|---|
| **Conceptual Simplicity** | Moderate | **High** | Low |
| **Seasonal Consistency** | High | **High** | High |
| **Leap-Year Correctness** | Moderate (DOY shift) | **Deterministic** | Complex |
| **Year-Boundary Handling** | Fragile (requires server-side splits) | **Native & Continuous** | Complex |
| **Implementation Complexity** | High in Earth Engine | **Minimal in Python** | High |
| **Earth Engine Compatibility** | Moderate | **Native (`ee.Filter.date`)** | Moderate |
| **Unit Testability** | Requires EE mocks/stubs | **100% Pure Python** | Pure Python |
| **Off-by-One Error Risk** | High | **Zero** | Moderate |
| **Phase 2A Compatibility** | Compatible | **Fully Compatible** | Compatible |

**Conclusion:** **Option B (Calendar-Date-Anchored Seasonal Windowing)** is selected as the authoritative Phase 2B design.

---

## 10. UTC / Timestamp Semantics

### 10.1 Satellite Overpass & Local Time Analysis
Sentinel-2 operates in a Sun-synchronous orbit with a local equatorial crossing time of 10:30 AM (descending node). Over the Indian subcontinent ($UTC+05:30$):
- **Local Overpass Time:** Approximately 10:30 AM – 11:00 AM IST.
- **Equivalent UTC Time:** Approximately 05:00 AM – 05:30 AM UTC on the **same calendar day**.

Because Sentinel-2 overpasses India at 05:00 UTC, the observation timestamp falls in the middle of the UTC day. There is no risk of midnight boundary splitting between UTC and IST during daylight overpasses.

### 10.2 Strict UTC Standardization
- All date calculations, lookback ranges, and historical baseline matching will execute strictly on **UTC calendar dates**.
- No local timezone conversion is required or permitted in the core satellite layer, ensuring 100% consistency across global coordinate points.

---

## 11. Proposed MVP Temporal-Window Strategy

### 11.1 Algorithm Specification
```text
Algorithm: GenerateHistoricalSearchWindows
Input:
    obs_date: datetime.date (UTC date of current authoritative observation)
    history_years: int = 3 (Number of preceding years: Y-1, Y-2, Y-3)
    window_half_width: int = 15 (Days on either side of anchor)

Output:
    List[HistoricalSearchWindow] containing 3 deterministic search windows

Steps:
    1. Y_0 = obs_date.year, M_0 = obs_date.month, D_0 = obs_date.day
    2. Initialize windows = []
    3. For k in [1, 2, 3]:
        a. target_year = Y_0 - k
        b. If M_0 == 2 and D_0 == 29:
             If is_leap_year(target_year):
                 anchor_date = date(target_year, 2, 29)
             Else:
                 anchor_date = date(target_year, 2, 28)
           Else:
             anchor_date = date(target_year, M_0, D_0)
        c. start_date = anchor_date - timedelta(days=window_half_width)
        d. end_date = anchor_date + timedelta(days=window_half_width)
        e. ee_start_str = start_date.strftime("%Y-%m-%d")
        f. ee_end_str = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
        g. Append HistoricalSearchWindow(
               target_year=target_year,
               anchor_date=anchor_date,
               start_date=start_date,
               end_date=end_date,
               ee_filter_start=ee_start_str,
               ee_filter_end=ee_end_str,
               inclusive_day_count=31
           )
    4. Return windows
```

---

## 12. Earth Engine Temporal Representation

For server-side Earth Engine filtering, the temporal windows can be applied in two verified patterns:

### Pattern 1: Independent Annual Sub-Collection Filtering (Recommended for Option C)
Within each historical year $Y_h$, query the Sentinel-2 collection using that year's specific continuous date range:
```python
# Conceptual representation (for Phase 2C design, not implementation)
collection_Y1 = get_sentinel2_collection(
    region=region,
    start_date=window_Y1.ee_filter_start,
    end_date=window_Y1.ee_filter_end,
    ...
)
```

### Pattern 2: Multi-Window Disjoint Earth Engine Filter
If querying the catalog in a single compound filter:
```python
# Conceptual representation
compound_date_filter = ee.Filter.Or(
    ee.Filter.date(window_Y1.ee_filter_start, window_Y1.ee_filter_end),
    ee.Filter.date(window_Y2.ee_filter_start, window_Y2.ee_filter_end),
    ee.Filter.date(window_Y3.ee_filter_start, window_Y3.ee_filter_end),
)
```

Both patterns are fully supported by Earth Engine and avoid all `ee.Filter.dayOfYear` year-crossing failure modes.

---

## 13. Explicit Temporal-Window Contract

### 13.1 Conceptual Data Contracts (Types)
The temporal-window module will export pure, immutable Pydantic models:

```python
from datetime import date
from pydantic import BaseModel, Field

class HistoricalSearchWindow(BaseModel):
    """Deterministic date range for a single historical year's matched seasonal window.
    
    The window is strictly owned by target_year, even if the date range [start_date, end_date]
    crosses a calendar-year boundary into target_year - 1 or target_year + 1.
    """

    target_year: int = Field(description="The authoritative historical anchor year owning this seasonal window")
    anchor_date: date = Field(description="The seasonal anchor date within target_year")
    start_date: date = Field(description="Inclusive start date of the 31-day seasonal window")
    end_date: date = Field(description="Inclusive end date of the 31-day seasonal window")
    ee_filter_start: str = Field(description="Inclusive start date string YYYY-MM-DD for Earth Engine")
    ee_filter_end: str = Field(description="Exclusive end date string YYYY-MM-DD for Earth Engine")
    inclusive_day_count: int = Field(default=31, description="Total inclusive calendar days spanned")


class MultiYearHistoricalWindow(BaseModel):
    """Complete 3-year historical temporal matching specification."""

    reference_observation_date: date
    reference_year: int
    reference_doy: int
    window_half_width_days: int = 15
    historical_windows: list[HistoricalSearchWindow]
```

---

## 14. Edge-Case Test Matrix

The design must be validated against the comprehensive 18-case edge matrix:

| Test ID | Scenario | Current Obs Date ($T_0$) | Target Year ($Y_h$) | Expected Anchor ($T_h$) | Expected Start ($S_h$) | Expected End ($E_h$) | Expected EE Filter $[S_h, E_h+1)$ | Verified Characteristics |
|---|---|---|---|---|---|---|---|---|
| **TC-01** | Normal Mid-Year Date | `2024-08-15` | 2023 | `2023-08-15` | `2023-07-31` | `2023-08-30` | `2023-07-31` to `2023-08-31` | Standard mid-year month crossing |
| **TC-02** | Exact Jan 1 Boundary | `2024-01-01` | 2023 | `2023-01-01` | `2022-12-17` | `2023-01-16` | `2022-12-17` to `2023-01-17` | Year crossing owned by $Y_h=2023$ |
| **TC-03** | Early Jan (Jan 5) | `2024-01-05` | 2023 | `2023-01-05` | `2022-12-21` | `2023-01-20` | `2022-12-21` to `2023-01-21` | Deep year crossing owned by $Y_h=2023$ |
| **TC-04** | Mid Jan (Jan 15) | `2024-01-15` | 2023 | `2023-01-15` | `2022-12-31` | `2023-01-30` | `2022-12-31` to `2023-01-31` | Starts on Dec 31; owned by $Y_h=2023$ |
| **TC-05** | Late Dec (Dec 20) | `2023-12-20` | 2022 | `2022-12-20` | `2022-12-05` | `2023-01-04` | `2022-12-05` to `2023-01-05` | Year crossing owned by $Y_h=2022$ |
| **TC-06** | Late Dec (Dec 25) | `2023-12-25` | 2022 | `2022-12-25` | `2022-12-10` | `2023-01-09` | `2022-12-10` to `2023-01-10` | Deep year crossing owned by $Y_h=2022$ |
| **TC-07** | Exact Dec 31 Boundary | `2023-12-31` | 2022 | `2022-12-31` | `2022-12-16` | `2023-01-15` | `2022-12-16` to `2023-01-16` | Symmetrical crossing owned by $Y_h=2022$ |
| **TC-08** | Feb 28 in Leap Year | `2024-02-28` | 2023 | `2023-02-28` | `2023-02-13` | `2023-03-15` | `2023-02-13` to `2023-03-16` | Leap to common year mapping |
| **TC-09** | Feb 29 in Leap Year | `2024-02-29` | 2023 | `2023-02-28` | `2023-02-13` | `2023-03-15` | `2023-02-13` to `2023-03-16` | **Clamped Feb 29 to Feb 28** |
| **TC-10** | Mar 1 in Leap Year | `2024-03-01` | 2023 | `2023-03-01` | `2023-02-14` | `2023-03-16` | `2023-02-14` to `2023-03-17` | Post-leap day mapping |
| **TC-11** | Feb 28 in Common Year | `2023-02-28` | 2022 | `2022-02-28` | `2022-02-13` | `2022-03-15` | `2022-02-13` to `2022-03-16` | Common to common year |
| **TC-12** | Mar 1 in Common Year | `2023-03-01` | 2022 | `2022-03-01` | `2022-02-14` | `2022-03-16` | `2022-02-14` to `2022-03-17` | Common to common year |
| **TC-13** | Leap Obs $\to$ Non-Leap Hist | `2024-06-15` | 2023 | `2023-06-15` | `2023-05-31` | `2023-06-30` | `2023-05-31` to `2023-07-01` | Mid-year leap to common |
| **TC-14** | Non-Leap Obs $\to$ Leap Hist | `2025-06-15` | 2024 | `2024-06-15` | `2024-05-31` | `2024-06-30` | `2024-05-31` to `2024-07-01` | Common to leap historical year |
| **TC-15** | Exact Lower Boundary | `2024-08-15` | 2023 | `2023-08-15` | `2023-07-31` | `2023-08-30` | `2023-07-31` to `2023-08-31` | Start is exactly $(T_h - 15\text{d})$ |
| **TC-16** | Exact Upper Boundary | `2024-08-15` | 2023 | `2023-08-15` | `2023-07-31` | `2023-08-30` | `2023-07-31` to `2023-08-31` | End is exactly $(T_h + 15\text{d})$ |
| **TC-17** | Timestamp Near Midnight | `2024-08-15T23:59:59Z` | 2023 | `2023-08-15` | `2023-07-31` | `2023-08-30` | `2023-07-31` to `2023-08-31` | Correct UTC date truncation |
| **TC-18** | Mixed Multi-Year Horizon | `2025-02-20` | 2024, 2023, 2022 | Diverse | Diverse | Diverse | Diverse | 2024 is leap; 2023/2022 common |

---

## 15. Complexity-Control Rationale

The following mechanisms were evaluated and **explicitly rejected or deferred** to protect simplicity and architectural integrity:

1. **Phenological Curve Fitting / Dynamic Time Warping (DTW):**  
   *Rejected.* Adjusting dates to match vegetative peak curves requires multi-year dense time-series fitting that is prone to overfitting and unnecessary for a 30-day regional baseline.
2. **Growing Degree-Day (GDD) / Thermal Time Normalization:**  
   *Rejected.* Requires daily temperature gridded weather data and crop-specific base temperatures ($T_{\text{base}}$), violating satellite module isolation.
3. **Crop-Specific Days-After-Sowing (DAS) Alignment:**  
   *Rejected.* Sowing dates are farmer-specific management data not present in satellite metadata; handled in Phase 5 agent reasoning.
4. **Fractional-Year / Astronomical Continuous Coordinate Modeling:**  
   *Deferred.* Introduces additional mathematical and implementation complexity without sufficient empirical evidence that this added complexity provides meaningful benefit over the existing $\pm 15$-day calendar window.
5. **Leap-Year Day-Stretching Algorithms:**  
   *Rejected.* Expanding or compressing the 366-day leap year into 365 intervals introduces floating-point date artifacts.

---

## 16. Architectural Boundaries

- **In Scope for Phase 2B:**
  - Mathematical definition of DOY and $\pm 15$-day windowing.
  - Leap-year calendar handling and clamping.
  - Year-boundary date range resolution and window ownership rules.
  - Specification of Earth Engine date filter contracts.
- **Strictly Out of Scope for Phase 2B:**
  - Executing Earth Engine queries or aggregations (Phase 2C/2D).
  - Statistical baseline calculations (Phase 2C/2D).
  - Crop identification or crop health classification (Phase 5).
  - Weather/soil data integration (Phase 4).
  - LLM agent prompting, MCP tools, or UI displays (Phase 5/6/7).

---

## 17. Open Technical Questions for Phase 2C / 2D

The following implementation questions are noted for subsequent subphases:
1. **Server-Side Aggregation Mechanism (Phase 2C):**  
   Should annual regional NDVI values under Option C be computed via `ee.Join` / `ee.ImageCollection.map()` on Earth Engine server-side, or by evaluating annual sub-collections independently? *(To be investigated in Phase 2C).*
2. **Composite Reduction Method (Phase 2C):**  
   Within each historical year's 31-day window, will multiple qualifying scenes be reduced via a temporal median composite image before zonal statistics, or via an average across individual scene zonal means? *(To be formalized in Phase 2C).*

---

## 18. Sealed Phase 2B Decision (`DEC-015`)

```markdown
### DEC-015: Historical Temporal Window & Seasonality Strategy (Phase 2B)

- **Status:** 🟢 APPROVED & SEALED
- **Date:** 2026-09-27
- **Context:** Phase 2 requires comparing the current observation with a 3-year historical baseline matching the identical seasonal period (Reference DOY ±15 days). We must define a deterministic, leap-year-safe, year-boundary-safe window generation algorithm.
- **Decision:**
  1. Adopt **Option B: Calendar-Date-Anchored Seasonal Windowing** in pure Python.
  2. Day of Year (DOY) serves as the conceptual basis for seasonal comparability; calendar-date arithmetic serves as the concrete MVP implementation mechanism.
  3. The historical window for each target year (Y-1, Y-2, Y-3) is constructed by anchoring the observation's UTC month and day (M_0, D_0) to each target year, generating an exact 31-day inclusive calendar range [anchor - 15 days, anchor + 15 days].
  4. **Cross-Calendar-Year Window Ownership Rule:** A seasonal window is strictly owned by its target historical anchor year Y_h. All qualifying scenes acquired within the continuous window belong entirely to the annual baseline for Y_h, even if dates fall into Y_h-1 or Y_h+1. Phase 2C must preserve this ownership invariant.
  5. **Leap-Year Rule:** Treat leap years strictly as a calendar correctness problem. If the reference observation is February 29, clamp the anchor date to February 28 in common historical years. Do not implement complex phenological or fractional adjustments.
  6. **Year-Boundary Rule:** Windows crossing January 1 or December 31 naturally span across calendar years and are represented as continuous ISO date ranges passed directly to Earth Engine's `ee.Filter.date()`.
  7. **Earth Engine Boundary Contract:** Express Earth Engine filter boundaries as `[start_date, end_date + 1 day)` to guarantee full inclusion of the 31st calendar day.
- **Consequences:**
  - Deterministic, zero-dependency Python date windowing that is 100% unit-testable.
  - Zero risk of invalid calendar dates or Earth Engine day-of-year modulo failures.
  - Seamless support for all seasons, leap years, and year-boundary crossings.
  - Clean, unambiguous input contract for Phase 2C annual aggregation.
```

---
