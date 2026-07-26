"""Read models for local, versioned Pace plans."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PlanSessionFact:
    id: int
    scheduled_date: date
    sport_type: str
    purpose: str
    distance_meters: float | None
    duration_seconds: int | None
    heart_rate_zone: int | None
    target: "SessionTargetFact"
    target_display: str
    feedback_outcome: str | None


@dataclass(frozen=True, slots=True)
class SessionTargetFact:
    kind: str
    rpe_min: int | None
    rpe_max: int | None
    pace_seconds_per_km: int | None
    power_watts: int | None
    evidence_reference_id: str | None


@dataclass(frozen=True, slots=True)
class CoachAssessmentFact:
    fact_references: tuple[str, ...]
    observed_facts: tuple[str, ...]
    inferences: tuple[str, ...]
    rationale: str
    uncertainties: tuple[str, ...]
    coaching_principles: tuple[str, ...]
    knowledge_references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TrainingPlanFact:
    id: int
    parent_plan_id: int | None
    status: str
    contract_version: int
    goal_mode: str
    race_id: int | None
    as_of_date: date
    block_start_date: date
    block_end_date: date
    detailed_start_date: date
    detailed_end_date: date
    block_outline: tuple[dict[str, object], ...]
    sessions: tuple[PlanSessionFact, ...]
    coach_assessment: CoachAssessmentFact
