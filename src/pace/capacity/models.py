"""Typed outputs for Pace's deterministic capacity-profile layer."""

from dataclasses import dataclass
from datetime import date

from pace.planning.models import HistoryCoverage, PlanningBlocker, RacePlanningFact


@dataclass(frozen=True, slots=True)
class SportCapacityFact:
    """Observed training facts for one included Pace sport."""

    sport_type: str
    activity_count: int
    active_days: int
    total_duration_hours: float
    total_distance_km: float | None
    longest_duration_hours: float | None
    longest_distance_km: float | None


@dataclass(frozen=True, slots=True)
class ContinuityFact:
    """Calendar-based adherence facts without a coaching judgement."""

    calendar_days: int
    active_days: int
    expected_weeks: int
    weeks_with_activity: int
    weeks_without_activity: int
    longest_inactive_streak_days: int


@dataclass(frozen=True, slots=True)
class SportBalanceFact:
    """Duration-based split of observed run and ride training."""

    total_duration_hours: float
    running_duration_share_percent: float | None
    cycling_duration_share_percent: float | None


@dataclass(frozen=True, slots=True)
class RecoveryCoverageFact:
    """Observed recovery coverage reused from existing Pace metric facts."""

    metric: str
    baseline_data_points: int
    expected_baseline_days: int
    latest_date: date | None


@dataclass(frozen=True, slots=True)
class CapacityProfile:
    """A compact, read-only fact profile for later bounded plan generation."""

    as_of_date: date
    status: str
    source_start_date: date | None
    source_end_date: date | None
    history: HistoryCoverage
    sports: tuple[SportCapacityFact, ...]
    continuity: ContinuityFact | None
    sport_balance: SportBalanceFact | None
    recovery_coverage: tuple[RecoveryCoverageFact, ...]
    upcoming_races: tuple[RacePlanningFact, ...]
    planning_blockers: tuple[PlanningBlocker, ...]
    limitations: tuple[str, ...]
