"""Typed boundary models for the read-only Pace AI assistant."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ContextEventDraft:
    """An unpersisted context-event proposal that needs athlete confirmation."""

    event_type: str
    start_date: date
    end_date: date | None
    ongoing: bool
    note: str


@dataclass(frozen=True, slots=True)
class PaceAIAnswer:
    """Validated language output from one explicit athlete question."""

    answer: str
    observations: tuple[str, ...]
    uncertainties: tuple[str, ...]
    context_event_draft: ContextEventDraft | None


@dataclass(frozen=True, slots=True)
class PaceAIRequest:
    """The user question and selected, normalized facts sent to the model."""

    question: str
    context: dict[str, object]
