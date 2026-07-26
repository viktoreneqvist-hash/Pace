"""Typed contracts for a bounded Pace coaching dialogue."""

from dataclasses import dataclass

from pace.planning.draft_models import PlannedSessionDraft


@dataclass(frozen=True, slots=True)
class PlanAdjustmentDraft:
    """An unsaved same-day recommendation over one accepted plan session."""

    action: str
    replaces_session_id: int | None
    rationale: str
    proposed_session: PlannedSessionDraft | None


@dataclass(frozen=True, slots=True)
class CoachDialogueAnswer:
    """Validated answer for one plan-aware coach-dialogue turn."""

    answer: str
    observations: tuple[str, ...]
    uncertainties: tuple[str, ...]
    knowledge_references: tuple[str, ...]
    adjustment_draft: PlanAdjustmentDraft | None


@dataclass(frozen=True, slots=True)
class CoachDialogueRequest:
    """One athlete question plus bounded local facts and in-memory dialogue."""

    question: str
    context: dict[str, object]
    conversation: tuple[dict[str, str], ...] = ()
