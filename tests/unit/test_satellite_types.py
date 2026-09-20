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
"""Unit tests for satellite and Earth Engine result contracts and type definitions."""

import json

from pydantic import ValidationError
import pytest

from app.satellite.types import EarthEngineError, EarthEngineResult


def test_valid_success_result() -> None:
    """Test creating a valid success result with dataset and image count."""
    result = EarthEngineResult(
        status="success",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=5,
        data={"info": "sample_data"},
    )
    assert result.status == "success"
    assert result.dataset == "COPERNICUS/S2_SR_HARMONIZED"
    assert result.image_count == 5
    assert result.data == {"info": "sample_data"}
    assert result.error is None


def test_valid_no_data_result() -> None:
    """Test creating a valid no_data result with image_count=0 and no error."""
    result = EarthEngineResult(
        status="no_data",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=0,
        error=None,
    )
    assert result.status == "no_data"
    assert result.dataset == "COPERNICUS/S2_SR_HARMONIZED"
    assert result.image_count == 0
    assert result.data is None
    assert result.error is None


def test_valid_error_result() -> None:
    """Test creating a valid error result with structured error details."""
    error = EarthEngineError(
        type="EEInitializationError",
        message="Earth Engine client failed to initialize with provided credentials.",
    )
    result = EarthEngineResult(
        status="error",
        error=error,
    )
    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "EEInitializationError"
    assert "credentials" in result.error.message
    assert result.dataset is None
    assert result.image_count is None


def test_invalid_status_rejected() -> None:
    """Test that an invalid status string raises a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        EarthEngineResult(status="pending")  # type: ignore[arg-type]

    assert "status" in str(exc_info.value)


def test_negative_image_count_rejected() -> None:
    """Test that a negative image_count raises a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        EarthEngineResult(
            status="success",
            image_count=-1,
        )
    assert "image_count" in str(exc_info.value)


def test_model_serialization() -> None:
    """Test model serialization using model_dump() and model_dump_json()."""
    error = EarthEngineError(
        type="QueryTimeout",
        message="Request timed out after 30 seconds.",
    )
    result = EarthEngineResult(
        status="error",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=0,
        data={"query_time_ms": 30000},
        error=error,
    )

    dumped_dict = result.model_dump()
    assert dumped_dict == {
        "status": "error",
        "dataset": "COPERNICUS/S2_SR_HARMONIZED",
        "image_count": 0,
        "data": {"query_time_ms": 30000},
        "error": {
            "type": "QueryTimeout",
            "message": "Request timed out after 30 seconds.",
        },
    }

    dumped_json = result.model_dump_json()
    parsed_json = json.loads(dumped_json)
    assert parsed_json["status"] == "error"
    assert parsed_json["error"]["type"] == "QueryTimeout"

    # Also test success serialization without error
    success_result = EarthEngineResult(
        status="success",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=3,
    )
    success_dict = success_result.model_dump()
    assert success_dict["status"] == "success"
    assert success_dict["error"] is None
    assert success_dict["image_count"] == 3
