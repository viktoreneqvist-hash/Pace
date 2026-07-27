"""Typed, deterministic facts without a proprietary training-load score."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class SportWindowAnalysis:
    sport_type: str
    activity_count: int
    active_days: int
    duration_hours: float
    known_distance_km: float
    missing_distance_activities: int


@dataclass(frozen=True, slots=True)
class TransparentTrainingAnalysis:
    start_date: date
    end_date: date
    sports: tuple[SportWindowAnalysis, ...]
    total_duration_hours: float
    total_active_days: int
    feedback_records: int
    reported_rpe_average: float | None
    recovery_coverage: tuple[tuple[str, int, int], ...]
    limitations: tuple[str, ...]
