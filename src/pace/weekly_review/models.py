"""Structured output contract for an explicit weekly Pace review."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WeeklyReviewAnswer:
    summary: str
    observations: tuple[str, ...]
    recommendations: tuple[str, ...]
    uncertainties: tuple[str, ...]
    knowledge_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WeeklyReviewRequest:
    context: dict[str, object]
