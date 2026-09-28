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
"""Unit tests for Phase 5 Assessment Orchestration Pipeline (DEC-023)."""

from datetime import date
from unittest.mock import patch
import pytest

from app.assessment.pipeline import (
    evaluate_agricultural_assessment,
    fetch_agricultural_assessment,
)
from app.assessment.types import AgriculturalAssessment
from tests.fixtures.assessment_fixtures import create_scenario_evidence


def test_evaluate_agricultural_assessment():
    evidence = create_scenario_evidence("stable_conditions")
    assessment = evaluate_agricultural_assessment(evidence)

    assert isinstance(assessment, AgriculturalAssessment)
    assert assessment.status == "success"
    assert assessment.overall_condition == "stable"


def test_fetch_agricultural_assessment_mocked():
    evidence = create_scenario_evidence("stable_conditions")

    with patch(
        "app.assessment.pipeline.fetch_agricultural_environmental_evidence",
        return_value=evidence,
    ) as mock_fetch:
        assessment = fetch_agricultural_assessment(
            latitude=30.9010,
            longitude=75.8573,
            reference_date=date(2026, 9, 15),
            radius_m=100.0,
        )

        assert mock_fetch.called
        assert isinstance(assessment, AgriculturalAssessment)
        assert assessment.status == "success"


def test_fetch_agricultural_assessment_invalid_lat_raises():
    with pytest.raises(Exception):
        fetch_agricultural_assessment(
            latitude=95.0,  # Invalid lat > 90
            longitude=75.8573,
        )


def test_fetch_agricultural_assessment_invalid_lon_raises():
    with pytest.raises(Exception):
        fetch_agricultural_assessment(
            latitude=30.9010,
            longitude=200.0,  # Invalid lon > 180
        )
