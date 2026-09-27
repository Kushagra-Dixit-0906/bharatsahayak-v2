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
"""Unit tests for Phase 4 Multi-Source Evidence Fusion domain types (DEC-022)."""

from datetime import date
import pytest
from pydantic import ValidationError

from app.fusion.types import AgriculturalEnvironmentalEvidence, FusionStatus
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError
from tests.fixtures.fusion_fixtures import build_evidence_from_fixture


class TestFusionTypes:
    """Tests for AgriculturalEnvironmentalEvidence schema, immutability, and validation invariants."""

    def test_valid_model_construction_complete_success(self):
        """Verifies construction of a fully populated success evidence envelope."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = AgriculturalEnvironmentalEvidence(
            region=region,
            reference_date=date(2026, 9, 20),
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
            status="success",
            sources_requested_count=4,
            sources_available_count=4,
            sources_fully_available_count=4,
            is_fully_available=True,
            pipeline_version="4.0.0",
            error=None,
        )

        assert evidence.status == "success"
        assert evidence.sources_requested_count == 4
        assert evidence.sources_available_count == 4
        assert evidence.sources_fully_available_count == 4
        assert evidence.is_fully_available is True
        assert evidence.pipeline_version == "4.0.0"
        assert evidence.error is None
        assert evidence.region.latitude == pytest.approx(30.9010)
        assert evidence.reference_date == date(2026, 9, 20)

    def test_current_vegetation_convenience_property(self):
        """Verifies that current_vegetation returns vegetation.current directly."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = AgriculturalEnvironmentalEvidence(
            region=region,
            reference_date=date(2026, 9, 20),
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
            status="success",
            sources_available_count=4,
            sources_fully_available_count=4,
            is_fully_available=True,
        )

        assert evidence.current_vegetation is not None
        assert evidence.current_vegetation == veg.current
        assert evidence.current_vegetation.statistics.mean == pytest.approx(0.70)

    def test_current_vegetation_when_none(self):
        """Verifies current_vegetation returns None when vegetation.current is None."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("partial_ndvi_error.json")
        evidence = AgriculturalEnvironmentalEvidence(
            region=region,
            reference_date=date(2026, 9, 20),
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
            status="partial",
            sources_available_count=3,
            sources_fully_available_count=3,
            is_fully_available=False,
        )

        assert evidence.current_vegetation is None

    def test_model_immutability(self):
        """Verifies frozen=True prevents attribute mutation."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        evidence = AgriculturalEnvironmentalEvidence(
            region=region,
            reference_date=date(2026, 9, 20),
            vegetation=veg,
            reanalysis=rean,
            rainfall=rain,
            land_cover=lc,
            status="success",
            sources_available_count=4,
            sources_fully_available_count=4,
            is_fully_available=True,
        )

        with pytest.raises(ValidationError):
            evidence.status = "partial"  # type: ignore

        with pytest.raises(ValidationError):
            evidence.pipeline_version = "5.0.0"  # type: ignore

    def test_extra_fields_forbidden(self):
        """Verifies extra='forbid' rejects unregistered fields."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        with pytest.raises(ValidationError) as exc_info:
            AgriculturalEnvironmentalEvidence(
                region=region,
                reference_date=date(2026, 9, 20),
                vegetation=veg,
                reanalysis=rean,
                rainfall=rain,
                land_cover=lc,
                status="success",
                sources_available_count=4,
                sources_fully_available_count=4,
                is_fully_available=True,
                unauthorized_score=0.95,  # type: ignore
            )
        assert "extra" in str(exc_info.value).lower()

    def test_count_ordering_invariant(self):
        """Verifies violation when fully_available > available."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        with pytest.raises(ValidationError) as exc_info:
            AgriculturalEnvironmentalEvidence(
                region=region,
                reference_date=date(2026, 9, 20),
                vegetation=veg,
                reanalysis=rean,
                rainfall=rain,
                land_cover=lc,
                status="partial",
                sources_available_count=2,
                sources_fully_available_count=3,  # Invalid: fully > available
                is_fully_available=False,
            )
        assert "Count invariant violation" in str(exc_info.value)

    def test_is_fully_available_consistency(self):
        """Verifies is_fully_available must strictly match sources_fully_available_count == requested_count."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        with pytest.raises(ValidationError) as exc_info:
            AgriculturalEnvironmentalEvidence(
                region=region,
                reference_date=date(2026, 9, 20),
                vegetation=veg,
                reanalysis=rean,
                rainfall=rain,
                land_cover=lc,
                status="success",
                sources_available_count=4,
                sources_fully_available_count=4,
                is_fully_available=False,  # Inconsistent with 4/4
            )
        assert "is_fully_available" in str(exc_info.value)

    def test_status_success_invariant_requires_all_sources(self):
        """Verifies status='success' cannot have sources_fully_available_count < 4."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("partial_chirps_missing.json")
        with pytest.raises(ValidationError) as exc_info:
            AgriculturalEnvironmentalEvidence(
                region=region,
                reference_date=date(2026, 9, 20),
                vegetation=veg,
                reanalysis=rean,
                rainfall=rain,
                land_cover=lc,
                status="success",  # Inconsistent with 3/4
                sources_available_count=3,
                sources_fully_available_count=3,
                is_fully_available=False,
            )
        assert "status='success' requires sources_fully_available_count" in str(exc_info.value)

    def test_status_partial_invariant_requires_usable_sources(self):
        """Verifies status='partial' cannot have 0 available sources."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("all_no_data.json")
        with pytest.raises(ValidationError) as exc_info:
            AgriculturalEnvironmentalEvidence(
                region=region,
                reference_date=date(2026, 9, 20),
                vegetation=veg,
                reanalysis=rean,
                rainfall=rain,
                land_cover=lc,
                status="partial",  # Inconsistent with 0/4
                sources_available_count=0,
                sources_fully_available_count=0,
                is_fully_available=False,
            )
        assert "status='partial' requires at least 1 usable source" in str(exc_info.value)

    def test_status_no_data_invariant_requires_zero_available(self):
        """Verifies status='no_data' cannot have available sources > 0."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        with pytest.raises(ValidationError) as exc_info:
            AgriculturalEnvironmentalEvidence(
                region=region,
                reference_date=date(2026, 9, 20),
                vegetation=veg,
                reanalysis=rean,
                rainfall=rain,
                land_cover=lc,
                status="no_data",  # Inconsistent with 4/4
                sources_available_count=4,
                sources_fully_available_count=4,
                is_fully_available=True,
            )
        assert "status='no_data' requires sources_available_count == 0" in str(exc_info.value)

    def test_top_level_error_requires_status_error(self):
        """Verifies top-level error forces status='error'."""
        region, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")
        err = EarthEngineError(type="InternalError", message="Top level failure")
        with pytest.raises(ValidationError) as exc_info:
            AgriculturalEnvironmentalEvidence(
                region=region,
                reference_date=date(2026, 9, 20),
                vegetation=veg,
                reanalysis=rean,
                rainfall=rain,
                land_cover=lc,
                status="partial",  # Inconsistent with top-level error
                sources_available_count=3,
                sources_fully_available_count=3,
                is_fully_available=False,
                error=err,
            )
        assert "Top-level error requires status='error'" in str(exc_info.value)
