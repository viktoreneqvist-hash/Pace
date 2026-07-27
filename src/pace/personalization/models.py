"""Non-causal feedback evidence for a planning model."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PersonalizationEvidence:
    as_of_date: date
    start_date: date
    feedback_records: int
    required_feedback_records: int
    sport_feedback_records: tuple[tuple[str, int], ...]
    sport_required_feedback_records: int
    status: str
    limitations: tuple[str, ...]
