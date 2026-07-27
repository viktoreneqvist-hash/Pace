"""Read-only facts describing when an accepted plan needs athlete action."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RaceCheckpointFact:
    race_id: int
    name: str
    race_date: date
    priority: str
    days_until_race: int
    inside_detailed_window: bool


@dataclass(frozen=True, slots=True)
class PlanCheckpoint:
    as_of_date: date
    status: str
    active_plan_id: int | None
    detailed_end_date: date | None
    detailed_days_remaining: int | None
    upcoming_races: tuple[RaceCheckpointFact, ...]
    reasons: tuple[str, ...]
    recommended_command: str | None
