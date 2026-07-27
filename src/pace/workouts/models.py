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
    detail_available: bool
    splits: tuple["ActivitySplitFact", ...]


@dataclass(frozen=True, slots=True)
class ActivitySplitFact:
    split_number: int
    duration_seconds: int | None
    distance_meters: float | None
    average_heart_rate: int | None
    average_speed_mps: float | None
    average_cadence: float | None
    average_power: float | None


@dataclass(frozen=True, slots=True)
class PlannedActualComparison:
    provider_activity_id: str
    planned_duration_seconds: int | None
    actual_duration_seconds: int
    duration_difference_seconds: int | None
    planned_distance_meters: float | None
    actual_distance_meters: float | None
    distance_difference_meters: float | None
    planned_interval_repetitions: int
    observed_split_count: int
    limitations: tuple[str, ...]


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
    comparisons: tuple[PlannedActualComparison, ...]
    limitations: tuple[str, ...]
