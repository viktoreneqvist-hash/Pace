"""Derive current, non-persistent feedback evidence for L3."""

from collections import Counter
from datetime import date, timedelta
from statistics import mean

from pace.database.session import session_scope
from pace.personalization.models import (
    ObservedPersonalizationPattern,
    PersonalizationEvidence,
)
from pace.repositories.training_plan_repository import list_feedback_trend_records


class PersonalizationEvidenceService:
    def get_evidence(self, *, end_date: date) -> PersonalizationEvidence:
        start_date = end_date - timedelta(days=55)
        with session_scope() as session:
            records = list_feedback_trend_records(session, start_date=start_date, end_date=end_date)
        sports = tuple(sorted(Counter(item.sport_type for item in records).items()))
        ready = len(records) >= 12
        limitations = ["explicit_feedback_only"]
        if not ready:
            limitations.append("insufficient_56_day_feedback")
        if not any(count >= 4 for _, count in sports):
            limitations.append("insufficient_same_sport_feedback")
        return PersonalizationEvidence(
            as_of_date=end_date,
            start_date=start_date,
            feedback_records=len(records),
            required_feedback_records=12,
            sport_feedback_records=sports,
            sport_required_feedback_records=4,
            status="ready" if ready else "insufficient_data",
            limitations=tuple(limitations),
            observed_patterns=_patterns(records) if ready else (),
        )


def _patterns(records) -> tuple[ObservedPersonalizationPattern, ...]:
    """Describe explicit observations only after the global evidence gate passes."""

    patterns: list[ObservedPersonalizationPattern] = []
    completed = sum(item.outcome == "completed" for item in records)
    completion_percent = round(completed / len(records) * 100, 1)
    patterns.append(
        ObservedPersonalizationPattern(
            pattern_id="overall_explicit_completion",
            scope="overall",
            metric="completed_among_feedback_percent",
            value=completion_percent,
            data_points=len(records),
            observation=(
                f"{completion_percent:g}% of sessions with explicit feedback were reported as fully completed."
            ),
        )
    )
    rpe_values = [item.perceived_exertion for item in records if item.perceived_exertion]
    if len(rpe_values) >= 6:
        average = round(mean(rpe_values), 1)
        patterns.append(
            ObservedPersonalizationPattern(
                pattern_id="overall_reported_rpe",
                scope="overall",
                metric="reported_rpe_average",
                value=average,
                data_points=len(rpe_values),
                observation=f"Reported RPE averaged {average:g}/10.",
            )
        )
    reason_counts = Counter(
        item.reason_code for item in records if item.reason_code is not None
    )
    if reason_counts:
        reason, count = reason_counts.most_common(1)[0]
        if count >= 3:
            patterns.append(
                ObservedPersonalizationPattern(
                    pattern_id="most_reported_limitation_reason",
                    scope="overall",
                    metric="reason_code",
                    value=reason,
                    data_points=count,
                    observation=f"{reason} was reported as the reason for {count} sessions.",
                )
            )
    for sport_type in sorted({item.sport_type for item in records}):
        sport_records = tuple(item for item in records if item.sport_type == sport_type)
        if len(sport_records) < 4:
            continue
        sport_completed = sum(item.outcome == "completed" for item in sport_records)
        sport_percent = round(sport_completed / len(sport_records) * 100, 1)
        patterns.append(
            ObservedPersonalizationPattern(
                pattern_id=f"{sport_type}_explicit_completion",
                scope=sport_type,
                metric="completed_among_feedback_percent",
                value=sport_percent,
                data_points=len(sport_records),
                observation=(
                    f"{sport_percent:g}% of {sport_type} sessions with feedback were reported as fully completed."
                ),
            )
        )
    return tuple(patterns)
