"""Read models for a transparent, non-automatic workout evaluation."""

from dataclasses import dataclass
from datetime import date

from pace.planning.plan_models import WorkoutStepFact


@dataclass(frozen=True, slots=True)
class MatchingActivityFact:
    provider_activity_id: str
    activity_date: date
    distance_meters: float | None
    duration_seconds: int


@dataclass(frozen=True, slots=True)
class WorkoutEvaluation:
    session_id: int
    plan_id: int
    scheduled_date: date
    sport_type: str
    planned_steps: tuple[WorkoutStepFact, ...]
    feedback_outcome: str | None
    feedback_perceived_exertion: int | None
    feedback_reason_code: str | None
    matching_activities: tuple[MatchingActivityFact, ...]
    limitations: tuple[str, ...]
