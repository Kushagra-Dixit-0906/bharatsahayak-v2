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
"""Helper loader and builders for deterministic offline fusion JSON fixtures (Phase 4, DEC-022)."""

import json
from pathlib import Path
from typing import Any

from app.environment.chirps_types import CHIRPSRainfallAnalysis
from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.types import ERA5LandAnalysis
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.types import AnalysisRegionMetadata, HistoricalNdviAnalysis

FIXTURES_DIR = Path(__file__).parent / "fusion"


def load_fusion_fixture(filename: str) -> dict[str, Any]:
    """Loads and parses a fusion offline test fixture by filename."""
    file_path = FIXTURES_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Fusion fixture '{filename}' not found at {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_evidence_from_fixture(filename: str) -> tuple[
    AnalysisRegionMetadata,
    HistoricalNdviAnalysis,
    ERA5LandAnalysis,
    CHIRPSRainfallAnalysis,
    DynamicWorldAnalysis,
]:
    """Loads and constructs the 4 domain subsystem objects and region metadata from a fixture."""
    data = load_fusion_fixture(filename)
    region = AnalysisRegionMetadata.model_validate(data["region"])
    vegetation = HistoricalNdviAnalysis.model_validate(data["vegetation"])
    reanalysis = ERA5LandAnalysis.model_validate(data["reanalysis"])
    rainfall = CHIRPSRainfallAnalysis.model_validate(data["rainfall"])
    land_cover = DynamicWorldAnalysis.model_validate(data["land_cover"])
    return region, vegetation, reanalysis, rainfall, land_cover
