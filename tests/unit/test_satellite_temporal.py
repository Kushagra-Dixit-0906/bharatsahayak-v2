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
"""Unit tests for historical temporal windowing and seasonality matching (DEC-015, Phase 2B)."""

from datetime import date, datetime, timedelta, timezone
import pytest

from app.satellite.temporal import (
    DEFAULT_HISTORICAL_YEARS,
    DEFAULT_WINDOW_HALF_DAYS,
    calculate_historical_target_years,
    construct_historical_temporal_window,
    parse_utc_date,
)
from app.satellite.types import HistoricalTemporalWindow, SatelliteTemporalWindow


# ==============================================================================
# 1. PARSE_UTC_DATE TESTS (Input type handling & normalization)
# ==============================================================================


def test_parse_utc_date_from_date():
    d = date(2024, 8, 15)
    assert parse_utc_date(d) == d


def test_parse_utc_date_from_naive_datetime():
    dt = datetime(2024, 8, 15, 14, 30, 0)
    assert parse_utc_date(dt) == date(2024, 8, 15)


def test_parse_utc_date_from_utc_aware_datetime():
    dt = datetime(2024, 8, 15, 23, 59, 59, tzinfo=timezone.utc)
    assert parse_utc_date(dt) == date(2024, 8, 15)


def test_parse_utc_date_from_offset_aware_datetime():
    # 2024-08-16 02:30:00 +05:30 is 2024-08-15 21:00:00 UTC -> UTC date is 2024-08-15
    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2024, 8, 16, 2, 30, 0, tzinfo=ist)
    assert parse_utc_date(dt) == date(2024, 8, 15)


@pytest.mark.parametrize(
    ("iso_str", "expected_date"),
    [
        ("2024-08-15", date(2024, 8, 15)),
        ("2024-01-01", date(2024, 1, 1)),
        ("2024-12-31", date(2024, 12, 31)),
        ("2024-02-29", date(2024, 2, 29)),
        ("2024-08-15T05:30:00Z", date(2024, 8, 15)),
        ("2024-08-15T23:59:59.999Z", date(2024, 8, 15)),
        ("2024-08-15 10:30:00", date(2024, 8, 15)),
        ("  2024-08-15  ", date(2024, 8, 15)),
    ],
)
def test_parse_utc_date_valid_strings(iso_str, expected_date):
    assert parse_utc_date(iso_str) == expected_date


@pytest.mark.parametrize(
    "bad_str",
    [
        "",
        "   ",
        "invalid-date",
        "2024/08/15",
        "15-08-2024",
        "2023-02-29",  # non-existent leap day in common year
        "2024-04-31",  # April only has 30 days
        "2024-13-01",
    ],
)
def test_parse_utc_date_invalid_strings_raise_value_error(bad_str):
    with pytest.raises(ValueError):
        parse_utc_date(bad_str)


@pytest.mark.parametrize(
    "bad_type",
    [
        None,
        True,
        False,
        12345,
        3.14159,
        ["2024-08-15"],
        {"date": "2024-08-15"},
    ],
)
def test_parse_utc_date_invalid_types_raise_type_error(bad_type):
    with pytest.raises(TypeError):
        parse_utc_date(bad_type)


# ==============================================================================
# 2. CALCULATE_HISTORICAL_TARGET_YEARS TESTS
# ==============================================================================


def test_calculate_historical_target_years_default_3_years():
    assert calculate_historical_target_years("2026-09-27") == [2025, 2024, 2023]
    assert calculate_historical_target_years(date(2024, 1, 15)) == [2023, 2022, 2021]


def test_calculate_historical_target_years_custom_count():
    assert calculate_historical_target_years("2025-05-10", history_years=1) == [2024]
    assert calculate_historical_target_years("2025-05-10", history_years=5) == [
        2024,
        2023,
        2022,
        2021,
        2020,
    ]


@pytest.mark.parametrize("bad_years", [0, -1, -5])
def test_calculate_historical_target_years_invalid_value_raises(bad_years):
    with pytest.raises(ValueError, match="strictly positive"):
        calculate_historical_target_years("2025-05-10", history_years=bad_years)


@pytest.mark.parametrize("bad_type", [None, True, False, 2.5, "3"])
def test_calculate_historical_target_years_invalid_type_raises(bad_type):
    with pytest.raises(TypeError):
        calculate_historical_target_years("2025-05-10", history_years=bad_type)


# ==============================================================================
# 3. PHASE 2B CANONICAL 18-CASE EDGE MATRIX TESTS (DEC-015, Section 14)
# ==============================================================================


@pytest.mark.parametrize(
    (
        "test_id",
        "ref_date",
        "target_year",
        "expected_anchor",
        "expected_start",
        "expected_end",
        "expected_ee_start",
        "expected_ee_end",
    ),
    [
        # TC-01: Normal Mid-Year Date
        (
            "TC-01",
            "2024-08-15",
            2023,
            date(2023, 8, 15),
            date(2023, 7, 31),
            date(2023, 8, 30),
            "2023-07-31",
            "2023-08-31",
        ),
        # TC-02: Exact Jan 1 Boundary
        (
            "TC-02",
            "2024-01-01",
            2023,
            date(2023, 1, 1),
            date(2022, 12, 17),
            date(2023, 1, 16),
            "2022-12-17",
            "2023-01-17",
        ),
        # TC-03: Early Jan (Jan 5)
        (
            "TC-03",
            "2024-01-05",
            2023,
            date(2023, 1, 5),
            date(2022, 12, 21),
            date(2023, 1, 20),
            "2022-12-21",
            "2023-01-21",
        ),
        # TC-04: Mid Jan (Jan 15)
        (
            "TC-04",
            "2024-01-15",
            2023,
            date(2023, 1, 15),
            date(2022, 12, 31),
            date(2023, 1, 30),
            "2022-12-31",
            "2023-01-31",
        ),
        # TC-05: Late Dec (Dec 20)
        (
            "TC-05",
            "2023-12-20",
            2022,
            date(2022, 12, 20),
            date(2022, 12, 5),
            date(2023, 1, 4),
            "2022-12-05",
            "2023-01-05",
        ),
        # TC-06: Late Dec (Dec 25)
        (
            "TC-06",
            "2023-12-25",
            2022,
            date(2022, 12, 25),
            date(2022, 12, 10),
            date(2023, 1, 9),
            "2022-12-10",
            "2023-01-10",
        ),
        # TC-07: Exact Dec 31 Boundary
        (
            "TC-07",
            "2023-12-31",
            2022,
            date(2022, 12, 31),
            date(2022, 12, 16),
            date(2023, 1, 15),
            "2022-12-16",
            "2023-01-16",
        ),
        # TC-08: Feb 28 in Leap Year -> Common Year
        (
            "TC-08",
            "2024-02-28",
            2023,
            date(2023, 2, 28),
            date(2023, 2, 13),
            date(2023, 3, 15),
            "2023-02-13",
            "2023-03-16",
        ),
        # TC-09: Feb 29 in Leap Year -> Clamped Feb 28 in Common Year
        (
            "TC-09",
            "2024-02-29",
            2023,
            date(2023, 2, 28),
            date(2023, 2, 13),
            date(2023, 3, 15),
            "2023-02-13",
            "2023-03-16",
        ),
        # TC-10: Mar 1 in Leap Year -> Common Year
        (
            "TC-10",
            "2024-03-01",
            2023,
            date(2023, 3, 1),
            date(2023, 2, 14),
            date(2023, 3, 16),
            "2023-02-14",
            "2023-03-17",
        ),
        # TC-11: Feb 28 in Common Year -> Common Year
        (
            "TC-11",
            "2023-02-28",
            2022,
            date(2022, 2, 28),
            date(2022, 2, 13),
            date(2022, 3, 15),
            "2022-02-13",
            "2022-03-16",
        ),
        # TC-12: Mar 1 in Common Year -> Common Year
        (
            "TC-12",
            "2023-03-01",
            2022,
            date(2022, 3, 1),
            date(2022, 2, 14),
            date(2022, 3, 16),
            "2022-02-14",
            "2022-03-17",
        ),
        # TC-13: Leap Obs -> Non-Leap Historical Mid-Year
        (
            "TC-13",
            "2024-06-15",
            2023,
            date(2023, 6, 15),
            date(2023, 5, 31),
            date(2023, 6, 30),
            "2023-05-31",
            "2023-07-01",
        ),
        # TC-14: Non-Leap Obs -> Leap Historical Mid-Year
        (
            "TC-14",
            "2025-06-15",
            2024,
            date(2024, 6, 15),
            date(2024, 5, 31),
            date(2024, 6, 30),
            "2024-05-31",
            "2024-07-01",
        ),
        # TC-15: Exact Lower Boundary (Anchor - 15 days)
        (
            "TC-15",
            "2024-08-15",
            2023,
            date(2023, 8, 15),
            date(2023, 7, 31),
            date(2023, 8, 30),
            "2023-07-31",
            "2023-08-31",
        ),
        # TC-16: Exact Upper Boundary (Anchor + 15 days)
        (
            "TC-16",
            "2024-08-15",
            2023,
            date(2023, 8, 15),
            date(2023, 7, 31),
            date(2023, 8, 30),
            "2023-07-31",
            "2023-08-31",
        ),
        # TC-17: Timestamp Near Midnight (Normalization)
        (
            "TC-17",
            "2024-08-15T23:59:59Z",
            2023,
            date(2023, 8, 15),
            date(2023, 7, 31),
            date(2023, 8, 30),
            "2023-07-31",
            "2023-08-31",
        ),
    ],
)
def test_phase_2b_edge_matrix(
    test_id,
    ref_date,
    target_year,
    expected_anchor,
    expected_start,
    expected_end,
    expected_ee_start,
    expected_ee_end,
):
    window = construct_historical_temporal_window(
        reference_date=ref_date,
        target_year=target_year,
        window_half_days=15,
    )
    assert window.target_year == target_year
    assert window.anchor_date == expected_anchor
    assert window.start_date == expected_start
    assert window.end_date == expected_end
    assert window.ee_filter_start == expected_ee_start
    assert window.ee_filter_end == expected_ee_end
    assert window.inclusive_day_count == 31


def test_tc18_mixed_multi_year_horizon():
    # TC-18: Reference 2025-02-20 across 2024 (leap), 2023 (common), 2022 (common)
    ref = "2025-02-20"
    target_years = calculate_historical_target_years(ref, history_years=3)
    assert target_years == [2024, 2023, 2022]

    # Year 2024 (Leap year)
    w_2024 = construct_historical_temporal_window(ref, 2024)
    assert w_2024.anchor_date == date(2024, 2, 20)
    assert w_2024.start_date == date(2024, 2, 5)
    assert w_2024.end_date == date(2024, 3, 6)  # 2024 has Feb 29
    assert w_2024.inclusive_day_count == 31

    # Year 2023 (Common year)
    w_2023 = construct_historical_temporal_window(ref, 2023)
    assert w_2023.anchor_date == date(2023, 2, 20)
    assert w_2023.start_date == date(2023, 2, 5)
    assert w_2023.end_date == date(2023, 3, 7)  # 2023 has no Feb 29
    assert w_2023.inclusive_day_count == 31

    # Year 2022 (Common year)
    w_2022 = construct_historical_temporal_window(ref, 2022)
    assert w_2022.anchor_date == date(2022, 2, 20)
    assert w_2022.start_date == date(2022, 2, 5)
    assert w_2022.end_date == date(2022, 3, 7)
    assert w_2022.inclusive_day_count == 31


def test_feb_29_to_leap_historical_year():
    # Feb 29 reference in leap year 2024 to leap historical year 2020 -> preserves Feb 29
    w = construct_historical_temporal_window("2024-02-29", 2020)
    assert w.anchor_date == date(2020, 2, 29)
    assert w.start_date == date(2020, 2, 14)
    assert w.end_date == date(2020, 3, 15)
    assert w.ee_filter_start == "2020-02-14"
    assert w.ee_filter_end == "2020-03-16"
    assert w.inclusive_day_count == 31


# ==============================================================================
# 4. REFERENCE DOY & INPUT FORM TESTS
# ==============================================================================


def test_reference_doy_derivation():
    # 2024-01-01 is DOY 1
    w1 = construct_historical_temporal_window("2024-01-01", 2023)
    assert w1.reference_doy == 1

    # 2024-08-15 (leap year) is DOY 228
    w2 = construct_historical_temporal_window("2024-08-15", 2023)
    assert w2.reference_doy == 228

    # 2023-08-15 (common year) is DOY 227
    w3 = construct_historical_temporal_window("2023-08-15", 2022)
    assert w3.reference_doy == 227


def test_input_forms_produce_identical_results():
    date_input = date(2024, 8, 15)
    dt_input = datetime(2024, 8, 15, 10, 30, tzinfo=timezone.utc)
    str_input = "2024-08-15"

    w_date = construct_historical_temporal_window(date_input, 2023)
    w_dt = construct_historical_temporal_window(dt_input, 2023)
    w_str = construct_historical_temporal_window(str_input, 2023)

    assert w_date == w_dt == w_str


# ==============================================================================
# 5. INPUT VALIDATION & ERROR HANDLING TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "bad_year",
    [0, -2023, 10000, 2023.5, "2023", None, True, False],
)
def test_invalid_target_year_raises(bad_year):
    if isinstance(bad_year, int) and not isinstance(bad_year, bool):
        with pytest.raises(ValueError):
            construct_historical_temporal_window("2024-08-15", target_year=bad_year)
    else:
        with pytest.raises(TypeError):
            construct_historical_temporal_window("2024-08-15", target_year=bad_year)


@pytest.mark.parametrize(
    "bad_half_days",
    [-1, -15, 15.5, "15", None, True, False],
)
def test_invalid_window_half_days_raises(bad_half_days):
    if isinstance(bad_half_days, int) and not isinstance(bad_half_days, bool):
        with pytest.raises(ValueError):
            construct_historical_temporal_window(
                "2024-08-15", 2023, window_half_days=bad_half_days
            )
    else:
        with pytest.raises(TypeError):
            construct_historical_temporal_window(
                "2024-08-15", 2023, window_half_days=bad_half_days
            )


# ==============================================================================
# 6. MATHEMATICAL & ARCHITECTURAL INVARIANTS
# ==============================================================================


@pytest.mark.parametrize("half_days", [0, 5, 15, 30])
def test_window_invariants(half_days):
    ref = date(2024, 7, 20)
    target_year = 2023
    w = construct_historical_temporal_window(
        ref, target_year=target_year, window_half_days=half_days
    )

    # 1. Day count invariant
    assert (w.end_date - w.start_date).days == 2 * half_days
    assert w.inclusive_day_count == 2 * half_days + 1

    # 2. Containment invariant
    assert w.start_date <= w.anchor_date <= w.end_date

    # 3. EE filter boundary invariant (end_date + 1 day)
    expected_ee_end = (w.end_date + timedelta(days=1)).strftime("%Y-%m-%d")
    assert w.ee_filter_end == expected_ee_end
    assert w.ee_filter_start == w.start_date.strftime("%Y-%m-%d")

    # 4. Target year ownership invariant
    assert w.anchor_date.year == target_year


def test_alias_equivalence():
    assert SatelliteTemporalWindow is HistoricalTemporalWindow
