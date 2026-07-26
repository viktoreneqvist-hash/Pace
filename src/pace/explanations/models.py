"""Typed outputs for Pace's deterministic explanation layer."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class ExplanationItem:
    """One concise template-backed explanation for a rule outcome."""

    explanation_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ContextCheckIn:
    """An optional, neutral request for athlete-provided missing context."""

    question: str
    suggested_event_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExplanationSummary:
    """Readable deterministic explanations for one athlete-state date."""

    as_of_date: date
    items: tuple[ExplanationItem, ...]
    context_check_in: ContextCheckIn | None
