"""Structured, deterministic planning-readiness outputs."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class HistoryCoverage:
    """Auditable Garmin-sync coverage used before planning can begin."""

    required_calendar_days: int
    covered_calendar_days: int
    required_start_date: date | None
    covered_start_date: date | None
    covered_end_date: date | None
    is_contiguous: bool


@dataclass(frozen=True, slots=True)
class PlanningBlocker:
    """One explicit reason that prevents Pace from drafting a training plan."""

    code: str
    event_type: str | None = None
    start_date: date | None = None


@dataclass(frozen=True, slots=True)
class RacePlanningFact:
    """Selected, non-private race information relevant to future planning."""

    id: int
    name: str
    sport_type: str
    race_date: date
    distance_meters: float
    priority: str
    desired_time_seconds: int | None
    taper: str


@dataclass(frozen=True, slots=True)
class PlanReadiness:
    """Whether Pace has the minimum approved facts to begin plan generation."""

    as_of_date: date
    status: str
    history: HistoryCoverage
    upcoming_races: tuple[RacePlanningFact, ...]
    blockers: tuple[PlanningBlocker, ...]
    limitations: tuple[str, ...]
