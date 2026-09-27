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
"""Unit tests for Phase 4 Multi-Source Evidence Fusion assembly and status resolution (DEC-022).

Covers all 20 canonical architectural scenarios specified in the Phase 4 design.
"""

import ast
from datetime import date
from pathlib import Path
import pytest

from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.types import ERA5LandAnalysis
from app.fusion.fusion import fuse_agricultural_environmental_evidence
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.types import EarthEngineError, HistoricalNdviAnalysis
from tests.fixtures.fusion_fixtures import build_evidence_from_fixture


class TestFusionAssembly:
    """Tests covering the 20 canonical assembly scenarios for DEC-022."""

    # Scenario 1: All 4 sources successful
    def test_scenario_01_all_sources_successful(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "success"
        assert evidence.sources_requested_count == 4
        assert evidence.sources_available_count == 4
        assert evidence.sources_fully_available_count == 4
        assert evidence.is_fully_available is True
        assert evidence.error is None

    # Scenario 2: CHIRPS no_data while other 3 sources succeed
    def test_scenario_02_chirps_no_data(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("partial_chirps_missing.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 3
        assert evidence.sources_fully_available_count == 3
        assert evidence.is_fully_available is False
        assert evidence.rainfall.status == "no_data"
        assert evidence.vegetation.status == "success"

    # Scenario 3: Dynamic World no_data while other 3 sources succeed
    def test_scenario_03_dynamic_world_no_data(self):
        region, veg, rean, rain, _ = build_evidence_from_fixture("complete_success.json")
        lc_no_data = DynamicWorldAnalysis(
            region=region,
            requested_end_date=date(2026, 9, 20),
            status="no_data",
        )
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc_no_data,
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 3
        assert evidence.sources_fully_available_count == 3
        assert evidence.is_fully_available is False
        assert evidence.land_cover.status == "no_data"

    # Scenario 4: ERA5-Land error while other 3 sources succeed
    def test_scenario_04_era5_land_error(self):
        region, veg, _, rain, lc = build_evidence_from_fixture("complete_success.json")
        rean_error = ERA5LandAnalysis(
            region=region,
            requested_end_date=date(2026, 9, 20),
            status="error",
            error=EarthEngineError(type="Timeout", message="Reanalysis timeout"),
        )
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean_error,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 3
        assert evidence.sources_fully_available_count == 3
        assert evidence.is_fully_available is False
        assert evidence.reanalysis.status == "error"
        assert evidence.reanalysis.error is not None
        assert evidence.reanalysis.error.type == "Timeout"

    # Scenario 5: Historical NDVI insufficient_history with valid current NDVI
    def test_scenario_05_historical_insufficient_history(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("historical_insufficient_history.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "partial"
        # Usable count includes partial vegetation evidence (4 usable), but only 3 fully available
        assert evidence.sources_available_count == 4
        assert evidence.sources_fully_available_count == 3
        assert evidence.is_fully_available is False
        assert evidence.vegetation.status == "insufficient_history"
        assert evidence.current_vegetation is not None
        assert evidence.current_vegetation.statistics.mean == pytest.approx(0.70)

    # Scenario 6: Historical NDVI no_data while other 3 sources succeed
    def test_scenario_06_historical_no_data(self):
        region, _, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        veg_no_data = HistoricalNdviAnalysis(
            current=None,
            historical_observations=[],
            sufficiency={
                "requested_years_count": 3,
                "represented_years_count": 0,
                "minimum_required_years": 2,
                "is_sufficient": False,
                "represented_years": [],
                "missing_years": [2025, 2024, 2023],
            },
            status="no_data",
        )
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg_no_data,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 3
        assert evidence.sources_fully_available_count == 3
        assert evidence.is_fully_available is False
        assert evidence.vegetation.status == "no_data"

    # Scenario 7: Historical NDVI error while other 3 sources succeed
    def test_scenario_07_historical_error(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("partial_ndvi_error.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 3
        assert evidence.sources_fully_available_count == 3
        assert evidence.is_fully_available is False
        assert evidence.vegetation.status == "error"
        assert evidence.vegetation.error is not None

    # Scenario 8: Mixed no_data + error with usable evidence
    def test_scenario_08_mixed_no_data_error_with_usable_evidence(self):
        region, veg, _, _, _ = build_evidence_from_fixture("complete_success.json")
        rean_error = ERA5LandAnalysis(
            region=region,
            requested_end_date=date(2026, 9, 20),
            status="error",
            error=EarthEngineError(type="EEError", message="Failed"),
        )
        rain_no_data = build_evidence_from_fixture("partial_chirps_missing.json")[3]
        lc_error = DynamicWorldAnalysis(
            region=region,
            requested_end_date=date(2026, 9, 20),
            status="error",
            error=EarthEngineError(type="EEError", message="Failed"),
        )

        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean_error,
            rainfall=rain_no_data,
            land_cover=lc_error,
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 1
        assert evidence.sources_fully_available_count == 1
        assert evidence.is_fully_available is False
        assert evidence.vegetation.status == "success"

    # Scenario 9: All 4 sources no_data
    def test_scenario_09_all_sources_no_data(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("all_no_data.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "no_data"
        assert evidence.sources_available_count == 0
        assert evidence.sources_fully_available_count == 0
        assert evidence.is_fully_available is False
        assert evidence.error is None

    # Scenario 10: All 4 sources error
    def test_scenario_10_all_sources_error(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("all_error.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.status == "error"
        assert evidence.sources_available_count == 0
        assert evidence.sources_fully_available_count == 0
        assert evidence.is_fully_available is False
        assert evidence.vegetation.error is not None
        assert evidence.reanalysis.error is not None
        assert evidence.rainfall.error is not None
        assert evidence.land_cover.error is not None

    # Scenario 11: Zero usable evidence with mixed no_data and error
    def test_scenario_11_zero_usable_with_mixed_no_data_and_error(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("mixed_no_data_error.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        # Fails to error because operational failures were encountered without usable data
        assert evidence.status == "error"
        assert evidence.sources_available_count == 0
        assert evidence.sources_fully_available_count == 0
        assert evidence.is_fully_available is False

    # Scenario 12: Missing values remain None (never defaulted to 0.0)
    def test_scenario_12_missing_values_remain_none(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("all_no_data.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.vegetation.current is None
        assert evidence.vegetation.baseline is None
        assert evidence.vegetation.anomaly is None
        assert evidence.reanalysis.latest_available_date is None
        assert evidence.reanalysis.data_lag_days is None
        assert evidence.reanalysis.recent_7_days is None
        assert evidence.rainfall.latest_available_date is None
        assert evidence.rainfall.data_lag_days is None
        assert evidence.rainfall.recent_7_days is None
        assert evidence.land_cover.observation_date is None
        assert evidence.land_cover.dominant_class is None
        assert evidence.land_cover.dominant_probability is None

    # Scenario 13: Native spatial resolutions preserved
    def test_scenario_13_native_spatial_resolutions_preserved(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.vegetation.current.region.scale_m == 10.0
        assert evidence.reanalysis.spatial_resolution_km == 11.1
        assert evidence.rainfall.spatial_resolution_km == 5.566
        assert evidence.land_cover.spatial_resolution_m == 10.0

    # Scenario 14: Source-specific observation dates preserved without fabrication
    def test_scenario_14_observation_dates_preserved(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.vegetation.current.observation.acquisition_date == "2026-09-18"
        assert evidence.reanalysis.latest_available_date == date(2026, 9, 15)
        assert evidence.rainfall.latest_available_date == date(2026, 9, 18)
        assert evidence.land_cover.observation_date == date(2026, 9, 16)

    # Scenario 15: Source-specific data_lag_days preserved without distortion
    def test_scenario_15_data_lags_preserved(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.vegetation.current.freshness.observation_age_days == 2
        assert evidence.reanalysis.data_lag_days == 5
        assert evidence.rainfall.data_lag_days == 2
        assert evidence.land_cover.data_lag_days == 4

    # Scenario 16: Reference date correctly preserved
    def test_scenario_16_reference_date_preserved(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date="2026-09-20",
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert evidence.reference_date == date(2026, 9, 20)

    # Scenario 17: Zero Earth Engine imports in app/fusion/fusion.py
    def test_scenario_17_zero_ee_imports_in_pure_assembly(self):
        fusion_py_path = Path(__file__).parent.parent.parent / "app" / "fusion" / "fusion.py"
        with open(fusion_py_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(fusion_py_path))

        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append(node.module)

        for mod in imported_modules:
            assert mod != "ee", f"Found prohibited Earth Engine import 'ee' in {fusion_py_path}"
            assert not mod.startswith("ee."), f"Found prohibited Earth Engine import '{mod}' in {fusion_py_path}"

    # Scenario 18: Zero network I/O in pure assembly
    def test_scenario_18_pure_assembly_offline_execution(self, monkeypatch):
        # Patch socket to guarantee zero network activity
        import socket

        def guarded_connect(*args, **kwargs):
            raise RuntimeError("Network I/O attempted in pure assembly module!")

        monkeypatch.setattr(socket.socket, "connect", guarded_connect)

        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )
        assert evidence.status == "success"

    # Scenario 19: Source domain objects are not mutated during fusion
    def test_scenario_19_source_objects_not_mutated(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        veg_dump_before = veg.model_dump()
        rean_dump_before = rean.model_dump()
        rain_dump_before = rain.model_dump()
        lc_dump_before = lc.model_dump()

        fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        assert veg.model_dump() == veg_dump_before
        assert rean.model_dump() == rean_dump_before
        assert rain.model_dump() == rain_dump_before
        assert lc.model_dump() == lc_dump_before

    # Scenario 20: Zero synthetic confidence percentages generated
    def test_scenario_20_zero_synthetic_confidence_values(self):
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = fuse_agricultural_environmental_evidence(
            reference_date=date(2026, 9, 20),
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

        evidence_dict = evidence.model_dump()
        # Verify no prohibited confidence or risk fields exist
        for forbidden_key in ["confidence", "confidence_score", "risk_score", "stress_score", "soil_health"]:
            assert forbidden_key not in evidence_dict, f"Found prohibited key '{forbidden_key}' in evidence model"
