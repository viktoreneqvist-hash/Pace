"""Typed, deterministic outputs for privacy-minimized performance history."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PerformanceDetailCoverage:
    """Detail coverage over the explicitly bounded twelve-week review window."""

    start_date: date
    end_date: date
    eligible_activities: int
    detailed_activities: int
    missing_details: int


@dataclass(frozen=True, slots=True)
class DetailedActivityFact:
    """An activity identifier and minimal facts needed to review evidence links."""

    garmin_activity_id: str
    activity_date: date
    sport_type: str
    split_count: int
    duration_seconds: int | None
    distance_meters: float | None


@dataclass(frozen=True, slots=True)
class RaceEvidenceFact:
    """Observed Garmin result linked explicitly to a configured race."""

    garmin_activity_id: str
    activity_date: date
    sport_type: str
    race_id: int
    race_name: str
    race_date: date
    race_distance_meters: float
    duration_seconds: int | None
    distance_meters: float | None
    average_speed_mps: float | None
    average_heart_rate: int | None
    average_power: float | None
    split_count: int


@dataclass(frozen=True, slots=True)
class PerformanceHistory:
    """Inspectable evidence facts, not target, fitness, or plan output."""

    as_of_date: date
    detail_coverage: PerformanceDetailCoverage
    detailed_activities: tuple[DetailedActivityFact, ...]
    race_evidence: tuple[RaceEvidenceFact, ...]
    limitations: tuple[str, ...]
