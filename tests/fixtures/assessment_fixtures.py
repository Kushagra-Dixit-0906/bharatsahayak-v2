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
"""Helper loader and builders for deterministic offline assessment scenarios (Phase 5, DEC-023)."""

from datetime import date
from typing import Any

from app.environment.chirps_types import CHIRPSRainfallAnalysis
from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.types import ERA5LandAnalysis
from app.fusion.fusion import fuse_agricultural_environmental_evidence
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.types import AnalysisRegionMetadata, HistoricalNdviAnalysis
from tests.fixtures.fusion_fixtures import build_evidence_from_fixture, load_fusion_fixture


def create_scenario_evidence(
    scenario_name: str,
    reference_date: date = date(2026, 9, 15),
) -> AgriculturalEnvironmentalEvidence:
    """Constructs a deterministic AgriculturalEnvironmentalEvidence payload tailored for specific assessment test scenarios."""
    region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")

    if scenario_name == "stable_conditions":
        # Baseline normal vegetation
        veg_data = veg.model_dump()
        veg_data["anomaly"]["departure_band"] = "Near-Baseline Spectral Alignment"
        veg_data["anomaly"]["absolute_departure"] = 0.00
        veg_data["anomaly"]["z_score"] = 0.00
        veg_stable = HistoricalNdviAnalysis.model_validate(veg_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_stable,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

    elif scenario_name == "water_stress_consistent":
        # Depressed vegetation (Strong Negative Spectral Departure) + dry rainfall + depleted soil moisture
        veg_data = veg.model_dump()
        veg_data["anomaly"]["departure_band"] = "Strong Negative Spectral Departure"
        veg_data["anomaly"]["absolute_departure"] = -0.16
        veg_data["anomaly"]["z_score"] = -1.95
        veg_depressed = HistoricalNdviAnalysis.model_validate(veg_data)

        rain_data = rain.model_dump()
        rain_data["recent_30_days"]["total_precipitation_mm"] = 4.2
        rain_data["recent_30_days"]["mean_daily_precipitation_mm"] = 0.14
        rain_dry = CHIRPSRainfallAnalysis.model_validate(rain_data)

        rean_data = rean.model_dump()
        rean_data["recent_30_days"]["mean_soil_water_layer_1"] = 0.12
        rean_dry = ERA5LandAnalysis.model_validate(rean_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_depressed,
            reanalysis=rean_dry,
            rainfall=rain_dry,
            land_cover=lc,
        )

    elif scenario_name == "vegetation_stress_isolated":
        # Depressed vegetation, but rainfall/reanalysis unavailable (missing)
        veg_data = veg.model_dump()
        veg_data["anomaly"]["departure_band"] = "Moderate Negative Spectral Departure"
        veg_data["anomaly"]["absolute_departure"] = -0.08
        veg_depressed = HistoricalNdviAnalysis.model_validate(veg_data)

        _, _, rean_err, rain_missing, _ = build_evidence_from_fixture("partial_chirps_missing.json")

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_depressed,
            reanalysis=rean,
            rainfall=rain_missing,
            land_cover=lc,
        )

    elif scenario_name == "favorable_growth":
        # Elevated vegetation
        veg_data = veg.model_dump()
        veg_data["anomaly"]["departure_band"] = "Moderate Positive Spectral Departure"
        veg_data["anomaly"]["absolute_departure"] = 0.08
        veg_fav = HistoricalNdviAnalysis.model_validate(veg_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_fav,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

    elif scenario_name == "heat_stress_consistent":
        # High temperature records
        rean_data = rean.model_dump()
        rean_data["recent_7_days"]["max_temperature_c"] = 42.5
        rean_data["recent_7_days"]["mean_temperature_c"] = 36.2
        rean_hot = ERA5LandAnalysis.model_validate(rean_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg,
            reanalysis=rean_hot,
            rainfall=rain,
            land_cover=lc,
        )

    elif scenario_name == "excess_moisture_waterlogging":
        # Heavy rain + high runoff
        rain_data = rain.model_dump()
        rain_data["recent_30_days"]["total_precipitation_mm"] = 320.0
        rain_heavy = CHIRPSRainfallAnalysis.model_validate(rain_data)

        rean_data = rean.model_dump()
        rean_data["recent_7_days"]["total_runoff_mm"] = 45.0
        rean_data["recent_30_days"]["mean_soil_water_layer_1"] = 0.42
        rean_wet = ERA5LandAnalysis.model_validate(rean_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg,
            reanalysis=rean_wet,
            rainfall=rain_heavy,
            land_cover=lc,
        )

    elif scenario_name == "combined_environmental_stress":
        # Depressed vegetation + dry rain + dry soil + high temperature
        veg_data = veg.model_dump()
        veg_data["anomaly"]["departure_band"] = "Strong Negative Spectral Departure"
        veg_data["anomaly"]["absolute_departure"] = -0.15
        veg_depressed = HistoricalNdviAnalysis.model_validate(veg_data)

        rean_data = rean.model_dump()
        rean_data["recent_7_days"]["max_temperature_c"] = 41.5
        rean_data["recent_30_days"]["mean_soil_water_layer_1"] = 0.11
        rean_compound = ERA5LandAnalysis.model_validate(rean_data)

        rain_data = rain.model_dump()
        rain_data["recent_30_days"]["total_precipitation_mm"] = 3.5
        rain_dry = CHIRPSRainfallAnalysis.model_validate(rain_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_depressed,
            reanalysis=rean_compound,
            rainfall=rain_dry,
            land_cover=lc,
        )

    elif scenario_name == "conflicting_ndvi_rainfall":
        # Depressed vegetation despite elevated rainfall
        veg_data = veg.model_dump()
        veg_data["anomaly"]["departure_band"] = "Moderate Negative Spectral Departure"
        veg_data["anomaly"]["absolute_departure"] = -0.09
        veg_depressed = HistoricalNdviAnalysis.model_validate(veg_data)

        rain_data = rain.model_dump()
        rain_data["recent_30_days"]["total_precipitation_mm"] = 180.0
        rain_heavy = CHIRPSRainfallAnalysis.model_validate(rain_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_depressed,
            reanalysis=rean,
            rainfall=rain_heavy,
            land_cover=lc,
        )

    elif scenario_name == "non_crop_context":
        # Non-crop land cover (e.g. built)
        lc_data = lc.model_dump()
        lc_data["dominant_class"] = "built"
        lc_data["dominant_probability"] = 0.82
        lc_data["class_probabilities"]["built"] = 0.82
        lc_data["class_probabilities"]["crops"] = 0.08
        lc_built = DynamicWorldAnalysis.model_validate(lc_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc_built,
        )

    elif scenario_name == "historical_insufficient":
        region, veg_insuff, rean, rain, lc = build_evidence_from_fixture("historical_insufficient_history.json")
        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_insuff,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
        )

    elif scenario_name == "all_no_data":
        region, veg_nd, rean_nd, rain_nd, lc_nd = build_evidence_from_fixture("all_no_data.json")
        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_nd,
            reanalysis=rean_nd,
            rainfall=rain_nd,
            land_cover=lc_nd,
        )

    elif scenario_name == "all_error":
        region, veg_err, rean_err, rain_err, lc_err = build_evidence_from_fixture("all_error.json")
        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_err,
            reanalysis=rean_err,
            rainfall=rain_err,
            land_cover=lc_err,
        )

    elif scenario_name == "mixed_no_data_error":
        region, veg_m, rean_m, rain_m, lc_m = build_evidence_from_fixture("mixed_no_data_error.json")
        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_m,
            reanalysis=rean_m,
            rainfall=rain_m,
            land_cover=lc_m,
        )

    elif scenario_name == "partial_chirps":
        region, veg_c, rean_c, rain_c, lc_c = build_evidence_from_fixture("partial_chirps_missing.json")
        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_c,
            reanalysis=rean_c,
            rainfall=rain_c,
            land_cover=lc_c,
        )

    elif scenario_name == "partial_era5":
        rean_data = rean.model_dump()
        rean_data["status"] = "no_data"
        rean_data["recent_7_days"] = None
        rean_data["recent_30_days"] = None
        rean_data["recent_90_days"] = None
        rean_data["daily_observations"] = []
        rean_data["latest_available_date"] = None
        rean_data["data_lag_days"] = None
        rean_missing = ERA5LandAnalysis.model_validate(rean_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg,
            reanalysis=rean_missing,
            rainfall=rain,
            land_cover=lc,
        )

    elif scenario_name == "current_ndvi_unavailable":
        region, veg_u, rean_u, rain_u, lc_u = build_evidence_from_fixture("partial_ndvi_error.json")
        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg_u,
            reanalysis=rean_u,
            rainfall=rain_u,
            land_cover=lc_u,
        )

    elif scenario_name == "conflicting_temperature_soil_water":
        # Elevated temperature but normal/healthy soil moisture
        rean_data = rean.model_dump()
        rean_data["recent_7_days"]["max_temperature_c"] = 42.0
        rean_data["recent_30_days"]["mean_soil_water_layer_1"] = 0.32
        rean_hot_wet = ERA5LandAnalysis.model_validate(rean_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg,
            reanalysis=rean_hot_wet,
            rainfall=rain,
            land_cover=lc,
        )

    elif scenario_name == "crop_dominant_land_cover":
        # Explicit crop-dominant land cover context
        lc_data = lc.model_dump()
        lc_data["dominant_class"] = "crops"
        lc_data["dominant_probability"] = 0.91
        lc_data["class_probabilities"]["crops"] = 0.91
        lc_crop = DynamicWorldAnalysis.model_validate(lc_data)

        return fuse_agricultural_environmental_evidence(
            reference_date=reference_date,
            region=region,
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc_crop,
        )

    raise ValueError(f"Unknown scenario_name: {scenario_name}")
