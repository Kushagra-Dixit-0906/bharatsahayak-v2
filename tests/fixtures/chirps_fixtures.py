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
"""Deterministic offline fixture loaders for CHIRPS rainfall testing (Phase 3B, DEC-020)."""

import json
from pathlib import Path
from typing import Any

_FIXTURES_DIR = Path(__file__).resolve().parent / "chirps"


def get_chirps_fixture_path(name: str) -> Path:
    """Return the absolute path to a CHIRPS fixture JSON file."""
    if not name.endswith(".json"):
        name = f"{name}.json"
    path = _FIXTURES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"CHIRPS fixture not found: {path}")
    return path


def load_chirps_fixture_raw(name: str) -> dict[str, Any]:
    """Load raw JSON dictionary from a CHIRPS test fixture."""
    path = get_chirps_fixture_path(name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_punjab_monsoon_wet_raw() -> dict[str, Any]:
    """Load the Punjab monsoon wet 90-day fixture dictionary."""
    return load_chirps_fixture_raw("punjab_monsoon_wet_90d")


def load_punjab_winter_dry_raw() -> dict[str, Any]:
    """Load the Punjab winter dry 90-day fixture dictionary."""
    return load_chirps_fixture_raw("punjab_winter_dry_90d")


def load_chirps_lagged_partial_raw() -> dict[str, Any]:
    """Load the lagged partial 90-day CHIRPS fixture dictionary."""
    return load_chirps_fixture_raw("lagged_partial_90d")


def load_chirps_negative_artifact_raw() -> dict[str, Any]:
    """Load the negative artifact edge case CHIRPS fixture dictionary."""
    return load_chirps_fixture_raw("negative_artifact_edge_case")


def load_chirps_no_data_empty_raw() -> dict[str, Any]:
    """Load the empty no-data CHIRPS fixture dictionary."""
    return load_chirps_fixture_raw("no_data_empty")
