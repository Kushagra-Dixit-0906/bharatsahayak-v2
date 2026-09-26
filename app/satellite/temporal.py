# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Historical temporal windowing and seasonality matching for satellite intelligence.

This module implements the calendar-date-anchored seasonal windowing strategy defined
in DEC-015 (Phase 2B — Temporal Window & Seasonality Strategy).

Architectural Responsibilities:
-------------------------------
1. Implements Calendar-Date-Anchored Seasonal Windowing in pure Python without Earth Engine
   API dependencies or network calls.
2. Derives historical target years (Y-1, Y-2, Y-3) from authoritative UTC reference dates.
3. Anchors calendar month and day (M_0, D_0) into target historical years with deterministic
   leap-year handling (mapping February 29 to February 28 in common historical years).
4. Generates inclusive ±15-day seasonal matching windows [anchor - 15d, anchor + 15d]
   (31 calendar days inclusive).
5. Enforces the Cross-Calendar-Year Window Ownership Invariant: seasonal windows crossing
   January 1 or December 31 remain strictly owned by their target historical anchor year Y_h.
6. Formats half-open date filter intervals [ee_filter_start, ee_filter_end) for Earth Engine
   where ee_filter_end = end_date + 1 calendar day.
7. Populates reference_doy as conceptual/provenance evidence without using DOY filtering.
"""

import calendar
from datetime import date, datetime, timedelta, timezone
import math
from typing import Union

from .types import HistoricalTemporalWindow

# Default temporal half-width in days for the seasonal matching window (DEC-012, DEC-015)
DEFAULT_WINDOW_HALF_DAYS: int = 15

# Default operational historical horizon in years (DEC-012, DEC-015)
DEFAULT_HISTORICAL_YEARS: int = 3


def parse_utc_date(date_val: Union[str, date, datetime]) -> date:
    """Parses a string, date, or datetime into an authoritative UTC calendar date.

    Args:
        date_val: An ISO date string ("YYYY-MM-DD" or ISO 8601), datetime, or date.

    Returns:
        date: The normalized UTC date object.

    Raises:
        TypeError: If date_val is not a string, date, or datetime.
        ValueError: If the string date format is invalid or cannot be parsed.
    """
    if isinstance(date_val, bool):
        raise TypeError(f"date_val must not be a boolean, got {date_val!r}")

    if isinstance(date_val, datetime):
        if date_val.tzinfo is not None:
            return date_val.astimezone(timezone.utc).date()
        return date_val.date()

    if isinstance(date_val, date):
        return date_val

    if isinstance(date_val, str):
        cleaned = date_val.strip()
        if not cleaned:
            raise ValueError("date_val string cannot be empty or whitespace.")

        # Handle ISO format with timezone or time components
        if "T" in cleaned or " " in cleaned:
            try:
                # Replace space with T if needed
                iso_str = cleaned.replace(" ", "T")
                # Normalize trailing Z to +00:00 for datetime.fromisoformat
                if iso_str.endswith("Z") or iso_str.endswith("z"):
                    iso_str = iso_str[:-1] + "+00:00"
                parsed_dt = datetime.fromisoformat(iso_str)
                if parsed_dt.tzinfo is not None:
                    return parsed_dt.astimezone(timezone.utc).date()
                return parsed_dt.date()
            except ValueError:
                # Fallback to date portion extraction
                date_part = cleaned.split("T")[0].split(" ")[0]
                try:
                    return datetime.strptime(date_part, "%Y-%m-%d").date()
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid ISO date string '{date_val}', expected 'YYYY-MM-DD' or ISO 8601 format."
                    ) from exc

        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid date format '{date_val}', expected 'YYYY-MM-DD' format."
            ) from exc

    raise TypeError(
        f"Unsupported date type {type(date_val).__name__}: expected str, date, or datetime."
    )


def calculate_historical_target_years(
    reference_date: Union[str, date, datetime],
    history_years: int = DEFAULT_HISTORICAL_YEARS,
) -> list[int]:
    """Calculates the list of historical target years (Y-1, Y-2, ...) preceding a reference date.

    Args:
        reference_date: The reference observation date (str, date, or datetime).
        history_years: Number of preceding historical years to evaluate (> 0). Defaults to 3.

    Returns:
        list[int]: Descending list of preceding historical target years (e.g. [2023, 2022, 2021]).

    Raises:
        TypeError: If reference_date or history_years types are invalid.
        ValueError: If history_years is not a strictly positive integer.
    """
    if not isinstance(history_years, int) or isinstance(history_years, bool):
        raise TypeError(
            f"history_years must be an integer, got {type(history_years).__name__}: {history_years!r}"
        )

    if history_years <= 0:
        raise ValueError(
            f"history_years must be a strictly positive integer (> 0), got {history_years}"
        )

    ref_dt = parse_utc_date(reference_date)
    ref_year = ref_dt.year

    return [ref_year - k for k in range(1, history_years + 1)]


def construct_historical_temporal_window(
    reference_date: Union[str, date, datetime],
    target_year: int,
    window_half_days: int = DEFAULT_WINDOW_HALF_DAYS,
) -> HistoricalTemporalWindow:
    """Constructs a deterministic 31-day seasonal matching window for a target historical year.

    Implements Calendar-Date-Anchored Seasonal Windowing (DEC-015):
    1. Extracts month and day (M_0, D_0) from the reference observation.
    2. Maps to target historical year Y_h with leap-year clamping:
       - If reference is Feb 29 and Y_h is a common year, clamps anchor to Feb 28.
       - Otherwise, anchor is date(Y_h, M_0, D_0).
    3. Evaluates contiguous inclusive window [anchor - window_half_days, anchor + window_half_days].
    4. Formats Earth Engine half-open filter boundaries [start_date, end_date + 1 day).
    5. Preserves target-year ownership even when the window crosses January 1 or December 31.

    Args:
        reference_date: The reference observation date (str, date, or datetime).
        target_year: The authoritative historical target year (integer in [1, 9999]).
        window_half_days: Days on either side of the anchor date (>= 0). Defaults to 15 (31 days total).

    Returns:
        HistoricalTemporalWindow: Strongly typed seasonal window model.

    Raises:
        TypeError: If arguments have invalid types.
        ValueError: If target_year or window_half_days are out of valid bounds.
    """
    if not isinstance(target_year, int) or isinstance(target_year, bool):
        raise TypeError(
            f"target_year must be an integer, got {type(target_year).__name__}: {target_year!r}"
        )

    if not (1 <= target_year <= 9999):
        raise ValueError(
            f"target_year must be between 1 and 9999, got {target_year}"
        )

    if not isinstance(window_half_days, int) or isinstance(window_half_days, bool):
        raise TypeError(
            f"window_half_days must be an integer, got {type(window_half_days).__name__}: {window_half_days!r}"
        )

    if window_half_days < 0:
        raise ValueError(
            f"window_half_days must be non-negative (>= 0), got {window_half_days}"
        )

    ref_date = parse_utc_date(reference_date)
    ref_month = ref_date.month
    ref_day = ref_date.day
    ref_doy = ref_date.timetuple().tm_yday

    # Deterministic leap-year clamping rule (DEC-015)
    if ref_month == 2 and ref_day == 29:
        if calendar.isleap(target_year):
            anchor_date = date(target_year, 2, 29)
        else:
            anchor_date = date(target_year, 2, 28)
    else:
        anchor_date = date(target_year, ref_month, ref_day)

    delta = timedelta(days=window_half_days)
    start_date = anchor_date - delta
    end_date = anchor_date + delta

    ee_filter_start = start_date.strftime("%Y-%m-%d")
    ee_filter_end = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
    inclusive_day_count = (end_date - start_date).days + 1

    return HistoricalTemporalWindow(
        target_year=target_year,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date,
        ee_filter_start=ee_filter_start,
        ee_filter_end=ee_filter_end,
        inclusive_day_count=inclusive_day_count,
        reference_doy=ref_doy,
    )
