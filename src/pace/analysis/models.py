"""Typed, deterministic outputs from Pace's analysis layer."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class TrainingWindowSummary:
    """Factual training totals for one inclusive calendar-date window."""

    start_date: date
    end_date: date
    activity_count: int
    active_days: int
    running_distance_km: float
    cycling_duration_hours: float
    total_duration_hours: float
    longest_run_km: float | None
    longest_ride_km: float | None


@dataclass(frozen=True, slots=True)
class TrainingSummary:
    """Current seven-day training facts and the immediately preceding window."""

    current: TrainingWindowSummary
    previous: TrainingWindowSummary
    running_distance_change_percent: float | None
    cycling_duration_change_percent: float | None


@dataclass(frozen=True, slots=True)
class RecoveryMetricSummary:
    """Observed value, recent average, and transparent rolling baseline."""

    metric: str
    unit: str
    baseline_start_date: date
    baseline_end_date: date
    baseline_value: float | None
    baseline_data_points: int
    expected_baseline_days: int
    recent_start_date: date
    recent_end_date: date
    recent_value: float | None
    recent_data_points: int
    latest_value: float | None
    latest_date: date | None
    latest_deviation_percent: float | None


@dataclass(frozen=True, slots=True)
class PaceMetricSummary:
    """A complete factual summary returned by the first deterministic layer."""

    end_date: date
    training: TrainingSummary
    recovery: tuple[RecoveryMetricSummary, ...]
