"""Read models for bounded, non-causal training-response trends."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class OutcomeSummary:
    feedback_records: int
    completed: int
    completed_limited: int
    skipped: int
    completed_among_feedback_percent: float | None


@dataclass(frozen=True, slots=True)
class FeedbackTrendRecord:
    """A deliberately text-free feedback fact for local trend calculations."""

    scheduled_date: date
    sport_type: str
    outcome: str
    perceived_exertion: int | None
    reason_code: str | None


@dataclass(frozen=True, slots=True)
class SportResponseSummary:
    sport_type: str
    outcomes: OutcomeSummary
    reported_rpe_average: float | None
    reported_rpe_data_points: int
    reason_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class FeedbackWindowSummary:
    start_date: date
    end_date: date
    outcomes: OutcomeSummary
    reported_rpe_average: float | None
    reported_rpe_data_points: int
    reason_counts: tuple[tuple[str, int], ...]
    sports: tuple[SportResponseSummary, ...]


@dataclass(frozen=True, slots=True)
class TrainingResponseTrends:
    """Observed feedback facts; never an inferred explanation or diagnosis."""

    as_of_date: date
    status: str
    recent: FeedbackWindowSummary
    previous: FeedbackWindowSummary
    recent_required_feedback_records: int
    previous_required_feedback_records: int
    comparison_available: bool
    limitations: tuple[str, ...]
