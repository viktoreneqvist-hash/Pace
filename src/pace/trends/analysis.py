"""Pure aggregation of explicit, structured athlete feedback."""

from collections import Counter
from datetime import date
from statistics import mean
from typing import Iterable

from pace.trends.models import (
    FeedbackTrendRecord,
    FeedbackWindowSummary,
    OutcomeSummary,
    SportResponseSummary,
    TrainingResponseTrends,
)


RECENT_REQUIRED_FEEDBACK_RECORDS = 6
PREVIOUS_REQUIRED_FEEDBACK_RECORDS = 4


def build_training_response_trends(
    *, as_of_date: date, records: Iterable[FeedbackTrendRecord]
) -> TrainingResponseTrends:
    """Aggregate two fixed 28-day windows without guessing unreported outcomes."""

    recent_start = as_of_date.fromordinal(as_of_date.toordinal() - 27)
    previous_start = as_of_date.fromordinal(as_of_date.toordinal() - 55)
    previous_end = as_of_date.fromordinal(as_of_date.toordinal() - 28)
    all_records = tuple(records)
    recent_records = tuple(
        record for record in all_records if recent_start <= record.scheduled_date <= as_of_date
    )
    previous_records = tuple(
        record
        for record in all_records
        if previous_start <= record.scheduled_date <= previous_end
    )
    recent = _window_summary(recent_start, as_of_date, recent_records)
    previous = _window_summary(previous_start, previous_end, previous_records)
    recent_ready = recent.outcomes.feedback_records >= RECENT_REQUIRED_FEEDBACK_RECORDS
    comparison_available = recent_ready and (
        previous.outcomes.feedback_records >= PREVIOUS_REQUIRED_FEEDBACK_RECORDS
    )
    limitations = ["explicit_feedback_only"]
    if not recent_ready:
        limitations.append("insufficient_recent_feedback")
    if not comparison_available:
        limitations.append("insufficient_previous_feedback")
    if recent.reported_rpe_data_points == 0:
        limitations.append("no_recent_reported_rpe")
    return TrainingResponseTrends(
        as_of_date=as_of_date,
        status="ready" if recent_ready else "insufficient_data",
        recent=recent,
        previous=previous,
        recent_required_feedback_records=RECENT_REQUIRED_FEEDBACK_RECORDS,
        previous_required_feedback_records=PREVIOUS_REQUIRED_FEEDBACK_RECORDS,
        comparison_available=comparison_available,
        limitations=tuple(limitations),
    )


def _window_summary(
    start_date: date, end_date: date, records: tuple[FeedbackTrendRecord, ...]
) -> FeedbackWindowSummary:
    sports = tuple(
        _sport_summary(sport_type, tuple(item for item in records if item.sport_type == sport_type))
        for sport_type in sorted({item.sport_type for item in records})
    )
    return FeedbackWindowSummary(
        start_date=start_date,
        end_date=end_date,
        outcomes=_outcomes(records),
        reported_rpe_average=_rpe_average(records),
        reported_rpe_data_points=sum(item.perceived_exertion is not None for item in records),
        reason_counts=_reason_counts(records),
        sports=sports,
    )


def _sport_summary(
    sport_type: str, records: tuple[FeedbackTrendRecord, ...]
) -> SportResponseSummary:
    return SportResponseSummary(
        sport_type=sport_type,
        outcomes=_outcomes(records),
        reported_rpe_average=_rpe_average(records),
        reported_rpe_data_points=sum(item.perceived_exertion is not None for item in records),
        reason_counts=_reason_counts(records),
    )


def _outcomes(records: tuple[FeedbackTrendRecord, ...]) -> OutcomeSummary:
    counts = Counter(item.outcome for item in records)
    record_count = len(records)
    completed = counts["completed"]
    return OutcomeSummary(
        feedback_records=record_count,
        completed=completed,
        completed_limited=counts["completed_limited"],
        skipped=counts["skipped"],
        completed_among_feedback_percent=(
            round(completed / record_count * 100, 1) if record_count else None
        ),
    )


def _rpe_average(records: tuple[FeedbackTrendRecord, ...]) -> float | None:
    values = [item.perceived_exertion for item in records if item.perceived_exertion is not None]
    return round(mean(values), 1) if values else None


def _reason_counts(records: tuple[FeedbackTrendRecord, ...]) -> tuple[tuple[str, int], ...]:
    counts = Counter(item.reason_code for item in records if item.reason_code is not None)
    return tuple(sorted(counts.items()))
