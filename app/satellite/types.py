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
"""Type definitions and result contracts for satellite and Earth Engine operations."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

EarthEngineStatus = Literal["success", "no_data", "error"]
SatelliteStatus = EarthEngineStatus


class EarthEngineError(BaseModel):
    """Structured error details for Earth Engine operations."""

    type: str
    message: str


SatelliteError = EarthEngineError


class Sentinel2ImageMetadata(BaseModel):
    """Structured metadata for a selected Sentinel-2 satellite observation."""

    image_id: str
    acquisition_date: str
    cloud_percentage: float = Field(ge=0.0, le=100.0)
    spacecraft_name: str | None = None
    mgrs_tile: str | None = None
    product_id: str | None = None
    system_time_start: int | None = None
    usable_coverage_percentage: float | None = Field(default=None, ge=0.0, le=100.0)
    clear_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_band: str | None = None


SatelliteImageMetadata = Sentinel2ImageMetadata


class NdviRegionalStatistics(BaseModel):
    """Structured regional summary statistics for NDVI over an AnalysisRegion."""

    mean: float = Field(ge=-1.0, le=1.0)
    median: float = Field(ge=-1.0, le=1.0)
    min: float = Field(ge=-1.0, le=1.0)
    max: float = Field(ge=-1.0, le=1.0)
    valid_pixel_count: int | None = Field(default=None, ge=0)


SatelliteRegionalStatistics = NdviRegionalStatistics


class EarthEngineResult(BaseModel):
    """Minimal result contract for Earth Engine operations."""

    status: EarthEngineStatus
    dataset: str | None = None
    image_count: int | None = Field(default=None, ge=0)
    data: Any | None = None
    error: EarthEngineError | None = None


SatelliteResult = EarthEngineResult


class ObservationQualityEvidence(BaseModel):
    """Operational policy thresholds and verification evidence for satellite observation quality."""

    quality_dataset: str = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
    min_usable_coverage_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    max_scene_cloud_threshold: float = Field(default=20.0, ge=0.0, le=100.0)
    quality_mask_applied: bool
    is_usable: bool


SatelliteQualityEvidence = ObservationQualityEvidence


class ObservationFreshness(BaseModel):
    """Evidence-only temporal reference and derived age for a satellite observation."""

    reference_date: str
    observation_age_days: int = Field(ge=0)
    lookback_window_days: int = Field(default=30, gt=0)


SatelliteFreshness = ObservationFreshness


class AnalysisRegionMetadata(BaseModel):
    """Geographic footprint, buffer geometry, and spatial reduction parameters."""

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    radius_m: float = Field(default=100.0, gt=0.0)
    geometry_type: str = Field(default="PointBuffer")
    scale_m: float = Field(default=10.0, gt=0.0)


SatelliteRegionMetadata = AnalysisRegionMetadata


class RegionalNdviAnalysis(BaseModel):
    """Authoritative domain payload packaging observation provenance, quality evidence,

    freshness, spatial sampling region, and regional NDVI summary statistics.
    """

    observation: Sentinel2ImageMetadata
    quality: ObservationQualityEvidence
    freshness: ObservationFreshness
    region: AnalysisRegionMetadata
    statistics: NdviRegionalStatistics
    pipeline_version: str = Field(default="1.0.0")


SatelliteRegionalAnalysis = RegionalNdviAnalysis


class HistoricalTemporalWindow(BaseModel):
    """Deterministic date range for a single historical year's matched seasonal window (DEC-015).

    The window is strictly owned by target_year, even if the date range [start_date, end_date]
    crosses a calendar-year boundary into target_year - 1 or target_year + 1.
    """

    target_year: int = Field(
        description="The authoritative historical anchor year owning this seasonal window"
    )
    anchor_date: date = Field(
        description="The seasonal anchor date within target_year"
    )
    start_date: date = Field(
        description="Inclusive start date of the seasonal window"
    )
    end_date: date = Field(
        description="Inclusive end date of the seasonal window"
    )
    ee_filter_start: str = Field(
        description="Inclusive start date string YYYY-MM-DD for Earth Engine"
    )
    ee_filter_end: str = Field(
        description="Exclusive end date string YYYY-MM-DD for Earth Engine"
    )
    inclusive_day_count: int = Field(
        default=31, description="Total inclusive calendar days spanned"
    )
    reference_doy: int = Field(
        ge=1, le=366, description="Day of Year (1-366) of reference observation date"
    )


SatelliteTemporalWindow = HistoricalTemporalWindow


class HistoricalObservationSummary(BaseModel):
    """Provenance metadata for a single selected historical Sentinel-2 satellite observation (DEC-014 / DEC-016)."""

    image_id: str = Field(description="COPERNICUS/S2_SR_HARMONIZED image asset identifier")
    acquisition_date: str = Field(
        description="Observation acquisition date string (YYYY-MM-DD or ISO 8601)"
    )
    target_year: int = Field(
        gt=0, le=9999, description="Authoritative historical anchor year owning this seasonal window"
    )
    cloud_percentage: float = Field(
        ge=0.0, le=100.0, description="Catalog scene cloudy pixel percentage (0-100)"
    )
    usable_coverage_percentage: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Parcel buffer unmasked pixel coverage percentage (0-100)",
    )
    spacecraft_name: str | None = Field(
        default=None, description="Sentinel-2 spacecraft name (e.g. Sentinel-2A)"
    )
    mgrs_tile: str | None = Field(
        default=None, description="Military Grid Reference System tile ID"
    )
    product_id: str | None = Field(
        default=None, description="Sentinel-2 product ID URI"
    )
    system_time_start: int | None = Field(
        default=None, description="Earth Engine system:time_start millisecond epoch timestamp"
    )
    selection_rank: int | None = Field(
        default=None,
        ge=1,
        le=3,
        description="1-based recency selection rank within the seasonal window (1 = newest)",
    )
    clear_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Clear-sky probability threshold applied (default 0.60)",
    )
    quality_band: str | None = Field(
        default=None, description="Quality assessment band name (e.g. cs_cdf)"
    )

    @classmethod
    def from_sentinel2_metadata(
        cls,
        metadata: Sentinel2ImageMetadata,
        target_year: int,
        selection_rank: int | None = None,
    ) -> "HistoricalObservationSummary":
        """Construct a HistoricalObservationSummary from a Sentinel2ImageMetadata instance."""
        return cls(
            image_id=metadata.image_id,
            acquisition_date=metadata.acquisition_date,
            target_year=target_year,
            cloud_percentage=metadata.cloud_percentage,
            usable_coverage_percentage=metadata.usable_coverage_percentage,
            spacecraft_name=metadata.spacecraft_name,
            mgrs_tile=metadata.mgrs_tile,
            product_id=metadata.product_id,
            system_time_start=metadata.system_time_start,
            selection_rank=selection_rank,
            clear_threshold=metadata.clear_threshold,
            quality_band=metadata.quality_band,
        )


SatelliteHistoricalObservationSummary = HistoricalObservationSummary


class AnnualHistoricalNdviObservation(BaseModel):
    """Representative seasonal-window NDVI observation for a single historical year (DEC-014 / DEC-016).

    Encapsulates the pixel-wise median NDVI composite and empirical observation density evidence
    for one target historical anchor year.
    """

    target_year: int = Field(
        gt=0, le=9999, description="Authoritative historical anchor year"
    )
    temporal_window: HistoricalTemporalWindow = Field(
        description="Deterministic 31-day seasonal matching window for this historical year"
    )
    available_usable_scenes_count: int = Field(
        ge=0, description="Total count of scenes in window meeting the Phase 1 quality threshold"
    )
    selected_scenes_count: int = Field(
        ge=0, le=3, description="Count of newest usable scenes selected for compositing (0 to 3)"
    )
    selected_observations: list[HistoricalObservationSummary] = Field(
        default_factory=list,
        description="Metadata summaries for the selected observations sorted newest-first",
    )
    statistics: NdviRegionalStatistics | None = Field(
        default=None,
        description="Regional zonal NDVI summary statistics over the median composite raster",
    )
    status: EarthEngineStatus = Field(
        default="success",
        description="Status of this historical year observation: success | no_data | error",
    )
    composite_method: str = Field(
        default="pixel_median",
        description="Compositing strategy applied (pixel_median for N>=2, identity for N=1, none for N=0)",
    )
    pipeline_version: str = Field(
        default="1.0.0", description="Semantic version of the satellite processing pipeline"
    )
    error: EarthEngineError | None = Field(
        default=None, description="Structured error details if status is error"
    )

    @property
    def selected_scenes(self) -> list[HistoricalObservationSummary]:
        """Alias for selected_observations for backward/forward compatibility."""
        return self.selected_observations

    @model_validator(mode="after")
    def validate_historical_consistency(self) -> "AnnualHistoricalNdviObservation":
        if self.temporal_window.target_year != self.target_year:
            raise ValueError(
                f"temporal_window.target_year ({self.temporal_window.target_year}) "
                f"must match observation target_year ({self.target_year})"
            )

        if self.available_usable_scenes_count < self.selected_scenes_count:
            raise ValueError(
                f"available_usable_scenes_count ({self.available_usable_scenes_count}) "
                f"cannot be less than selected_scenes_count ({self.selected_scenes_count})"
            )

        if len(self.selected_observations) != self.selected_scenes_count:
            raise ValueError(
                f"Length of selected_observations ({len(self.selected_observations)}) "
                f"must equal selected_scenes_count ({self.selected_scenes_count})"
            )

        for i, obs in enumerate(self.selected_observations):
            if obs.target_year != self.target_year:
                raise ValueError(
                    f"Selected observation at index {i} has target_year {obs.target_year}, "
                    f"which does not match observation target_year {self.target_year}"
                )

        if self.status == "success":
            if self.selected_scenes_count == 0:
                raise ValueError(
                    "status='success' requires at least 1 selected observation "
                    "(selected_scenes_count >= 1)"
                )
            if self.statistics is None:
                raise ValueError(
                    "status='success' requires valid composite NdviRegionalStatistics"
                )
        elif self.status == "no_data":
            if self.selected_scenes_count > 0:
                raise ValueError(
                    "status='no_data' cannot contain selected observations "
                    f"(selected_scenes_count={self.selected_scenes_count})"
                )
            if self.statistics is not None:
                raise ValueError(
                    "status='no_data' cannot contain regional statistics"
                )
        elif self.status == "error":
            if self.statistics is not None:
                raise ValueError(
                    "status='error' cannot contain regional statistics"
                )

        return self


SatelliteAnnualHistoricalNdviObservation = AnnualHistoricalNdviObservation


# ==============================================================================
# PHASE 2D DOMAIN CONTRACTS (DEC-013 / DEC-014 / DEC-017)
# ==============================================================================


class HistoricalNdviBaseline(BaseModel):
    """Statistical baseline derived across represented annual historical NDVI observations (DEC-013 / DEC-014 / DEC-017).

    Encapsulates the central tendency (median) and descriptive population dispersion across
    at least 2 represented historical target years.
    """

    median: float = Field(
        ge=-1.0, le=1.0, description="Primary historical baseline: median of represented annual regional NDVI means"
    )
    mean: float = Field(
        ge=-1.0, le=1.0, description="Secondary descriptive baseline: arithmetic mean of annual regional NDVI means"
    )
    standard_deviation: float = Field(
        ge=0.0,
        description="Population standard deviation (ddof=0) describing dispersion among represented historical means",
    )
    min: float = Field(
        ge=-1.0, le=1.0, description="Minimum annual regional NDVI mean observed in historical horizon"
    )
    max: float = Field(
        ge=-1.0, le=1.0, description="Maximum annual regional NDVI mean observed in historical horizon"
    )
    represented_years: list[int] = Field(
        description="Historical target years contributing valid observations, sorted descending"
    )
    annual_values: list[float] = Field(
        description="Annual regional mean NDVI values corresponding to represented_years"
    )
    annual_count: int = Field(
        ge=2, description="Count of represented annual observations (N_annual >= 2 required for a valid baseline)"
    )

    @model_validator(mode="after")
    def validate_baseline_invariants(self) -> "HistoricalNdviBaseline":
        if len(self.represented_years) != self.annual_count:
            raise ValueError(
                f"Length of represented_years ({len(self.represented_years)}) must equal annual_count ({self.annual_count})"
            )
        if len(self.annual_values) != self.annual_count:
            raise ValueError(
                f"Length of annual_values ({len(self.annual_values)}) must equal annual_count ({self.annual_count})"
            )
        if len(set(self.represented_years)) != len(self.represented_years):
            raise ValueError("Duplicate target years detected in represented_years")
        for i, val in enumerate(self.annual_values):
            if not (-1.0 <= val <= 1.0):
                raise ValueError(f"annual_values[{i}]={val} is outside valid NDVI range [-1.0, 1.0]")
        if not (self.min <= self.median <= self.max):
            raise ValueError(f"Baseline median ({self.median}) outside [min ({self.min}), max ({self.max})]")
        if not (self.min <= self.mean <= self.max):
            raise ValueError(f"Baseline mean ({self.mean}) outside [min ({self.min}), max ({self.max})]")
        return self


SatelliteHistoricalNdviBaseline = HistoricalNdviBaseline


class HistoricalSufficiencyEvidence(BaseModel):
    """Empirical data sufficiency evidence for multi-year historical comparison (DEC-014 / DEC-017)."""

    requested_years_count: int = Field(
        default=3, gt=0, description="Number of historical years requested in lookback horizon"
    )
    represented_years_count: int = Field(
        ge=0, description="Number of distinct historical years with valid usable observations"
    )
    minimum_required_years: int = Field(
        default=2, gt=0, description="Minimum distinct historical years required for a valid baseline (default 2)"
    )
    is_sufficient: bool = Field(
        description="True if represented_years_count >= minimum_required_years (N_annual >= 2 and Y >= 2)"
    )
    represented_years: list[int] = Field(
        default_factory=list, description="List of historical target years successfully represented"
    )
    missing_years: list[int] = Field(
        default_factory=list, description="List of historical target years with no usable data or errors"
    )
    sufficiency_notes: str | None = Field(
        default=None, description="Neutral evidence-based explanation of historical sufficiency state"
    )


SatelliteHistoricalSufficiencyEvidence = HistoricalSufficiencyEvidence


SpectralDepartureBand = Literal[
    "Strong Positive Spectral Departure",
    "Moderate Positive Spectral Departure",
    "Near-Baseline Spectral Alignment",
    "Moderate Negative Spectral Departure",
    "Strong Negative Spectral Departure",
]
SatelliteSpectralDepartureBand = SpectralDepartureBand


class NdviAnomalyEvidence(BaseModel):
    """Quantified mathematical departures between current NDVI and historical baseline (DEC-013 / DEC-014 / DEC-017)."""

    current_mean: float = Field(
        ge=-1.0, le=1.0, description="Current observation regional mean NDVI"
    )
    baseline_median: float = Field(
        ge=-1.0, le=1.0, description="Historical baseline median NDVI"
    )
    absolute_departure: float = Field(
        ge=-2.0, le=2.0, description="Primary anomaly: current_mean - baseline_median (in NDVI units)"
    )
    percentage_departure: float | None = Field(
        default=None, description="Gated relative departure (%): ((current - baseline) / baseline) * 100"
    )
    historical_mean: float = Field(
        ge=-1.0, le=1.0, description="Historical descriptive arithmetic mean NDVI used for Z-score"
    )
    historical_std_dev: float = Field(
        ge=0.0, description="Historical population standard deviation (ddof=0) used for Z-score"
    )
    z_score: float | None = Field(
        default=None, description="Gated standardized anomaly: (current_mean - historical_mean) / historical_std_dev"
    )
    departure_band: SpectralDepartureBand = Field(
        description="Empirical non-agronomic spectral departure classification"
    )
    percentage_unavailable_reason: str | None = Field(
        default=None, description="Explicit reason percentage departure was withheld (e.g. 'baseline_below_threshold')"
    )
    z_score_unavailable_reason: str | None = Field(
        default=None, description="Explicit reason Z-score was withheld (e.g. 'insufficient_sample_size', 'negligible_variance')"
    )


SatelliteNdviAnomalyEvidence = NdviAnomalyEvidence


HistoricalAnalysisStatus = Literal["success", "insufficient_history", "no_data", "error"]
SatelliteHistoricalAnalysisStatus = HistoricalAnalysisStatus


class HistoricalNdviAnalysis(BaseModel):
    """Complete multi-year historical satellite intelligence payload (DEC-014 / DEC-017)."""

    current: RegionalNdviAnalysis | None = Field(
        default=None, description="Authoritative Phase 1 current observation payload"
    )
    historical_observations: list[AnnualHistoricalNdviObservation] = Field(
        default_factory=list, description="Per-year historical observation results for Y-1, Y-2, Y-3"
    )
    baseline: HistoricalNdviBaseline | None = Field(
        default=None, description="Multi-year statistical baseline (present if status='success')"
    )
    sufficiency: HistoricalSufficiencyEvidence = Field(
        description="Data sufficiency evaluation and year completeness evidence"
    )
    anomaly: NdviAnomalyEvidence | None = Field(
        default=None, description="Mathematical anomaly metrics (present if status='success')"
    )
    status: HistoricalAnalysisStatus = Field(
        description="Universal operational status of the historical comparison"
    )
    pipeline_version: str = Field(
        default="2.0.0", description="Semantic version of the historical baseline pipeline"
    )
    error: EarthEngineError | None = Field(
        default=None, description="Error details if status is 'error'"
    )


SatelliteHistoricalNdviAnalysis = HistoricalNdviAnalysis
