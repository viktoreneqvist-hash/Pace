"""Structured AI plan-draft contracts validated before local persistence."""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class BlockOutlineItem:
    week_start: date
    week_end: date
    focus: str


@dataclass(frozen=True, slots=True)
class PlannedSessionDraft:
    scheduled_date: date
    sport_type: str
    purpose: str
    distance_meters: float | None
    duration_seconds: int | None
    heart_rate_zone: int | None
    target: "SessionTargetDraft"


@dataclass(frozen=True, slots=True)
class SessionTargetDraft:
    """Machine-checkable primary target; display text is Python-rendered."""

    kind: str
    rpe_min: int | None
    rpe_max: int | None
    pace_seconds_per_km: int | None
    power_watts: int | None
    evidence_reference_id: str | None


@dataclass(frozen=True, slots=True)
class CoachAssessmentDraft:
    """LLM conclusions kept distinct from observed Pace facts."""

    fact_references: tuple[str, ...] = ()
    inferences: tuple[str, ...] = ()
    rationale: str = ""
    uncertainties: tuple[str, ...] = ()
    coaching_principles: tuple[str, ...] = ()
    knowledge_references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeneratedPlanDraft:
    block_outline: tuple[BlockOutlineItem, ...]
    sessions: tuple[PlannedSessionDraft, ...]
    coach_assessment: CoachAssessmentDraft = field(default_factory=CoachAssessmentDraft)


@dataclass(frozen=True, slots=True)
class PlanGenerationRequest:
    mode: str
    context: dict[str, object]
