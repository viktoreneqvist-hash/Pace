"""Typed contracts for a bounded Pace coaching dialogue."""

from dataclasses import dataclass

from pace.ai.models import ContextEventDraft
from pace.planning.draft_models import PlannedSessionDraft


@dataclass(frozen=True, slots=True)
class PlanAdjustmentDraft:
    """An unsaved same-day recommendation over one accepted plan session."""

    action: str
    replaces_session_id: int | None
    rationale: str
    proposed_session: PlannedSessionDraft | None


@dataclass(frozen=True, slots=True)
class SessionFeedbackDraft:
    """An unsaved athlete-outcome proposal that requires an explicit UI action."""

    planned_session_id: int
    outcome: str
    perceived_exertion: int | None
    reason_code: str | None
    note: str | None


@dataclass(frozen=True, slots=True)
class CoachDialogueAnswer:
    """Validated answer for one plan-aware coach-dialogue turn."""

    answer: str
    observations: tuple[str, ...]
    uncertainties: tuple[str, ...]
    knowledge_references: tuple[str, ...]
    adjustment_draft: PlanAdjustmentDraft | None
    context_event_draft: ContextEventDraft | None = None
    feedback_draft: SessionFeedbackDraft | None = None


@dataclass(frozen=True, slots=True)
class CoachDialogueRequest:
    """One athlete question plus bounded local facts and in-memory dialogue."""

    question: str
    context: dict[str, object]
    conversation: tuple[dict[str, str], ...] = ()
