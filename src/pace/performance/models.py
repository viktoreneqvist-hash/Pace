"""Typed, deterministic outputs for privacy-minimized performance history."""

from dataclasses import dataclass
from datetime import date

from pace.planning.models import HistoryCoverage, PlanningBlocker


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
    scalar_source: str
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
    scalar_source: str


@dataclass(frozen=True, slots=True)
class BenchmarkEvidenceFact:
    """Observed Garmin facts from an athlete-confirmed standard test."""

    garmin_activity_id: str
    activity_date: date
    sport_type: str
    protocol: str
    duration_seconds: int | None
    distance_meters: float | None
    average_speed_mps: float | None
    average_heart_rate: int | None
    average_power: float | None
    split_count: int
    scalar_source: str


@dataclass(frozen=True, slots=True)
class PerformanceHistory:
    """Inspectable evidence facts, not target, fitness, or plan output."""

    as_of_date: date
    detail_coverage: PerformanceDetailCoverage
    detailed_activities: tuple[DetailedActivityFact, ...]
    race_evidence: tuple[RaceEvidenceFact, ...]
    benchmark_evidence: tuple[BenchmarkEvidenceFact, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntensityEvidenceFact:
    """Minimal verified evidence a coach may cite for a structured target."""

    reference_id: str
    sport_type: str
    evidence_type: str
    protocol: str | None
    activity_date: date
    duration_seconds: int | None
    distance_meters: float | None
    average_speed_mps: float | None
    qualifying_power_watts: float | None


@dataclass(frozen=True, slots=True)
class SportPerformanceReadiness:
    """Python-owned eligibility facts for a later AI intensity proposal."""

    sport_type: str
    status: str
    verified_evidence_count: int
    latest_evidence_date: date | None
    recent_activity_count: int
    required_recent_activity_count: int
    can_propose_intensity_target: bool
    limitations: tuple[str, ...]
    allowed_intensity_types: tuple[str, ...] = ("rpe", "none")
    heart_rate_zones: tuple[dict[str, int], ...] = ()
    intensity_evidence: tuple[IntensityEvidenceFact, ...] = ()


@dataclass(frozen=True, slots=True)
class PerformanceReadiness:
    """Read-only evidence and continuity gate without a target or plan."""

    as_of_date: date
    evidence_start_date: date
    history: HistoryCoverage
    planning_blockers: tuple[PlanningBlocker, ...]
    sports: tuple[SportPerformanceReadiness, ...]
