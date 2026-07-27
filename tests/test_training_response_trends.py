from datetime import date

from pace.trends.analysis import build_training_response_trends
from pace.trends.models import FeedbackTrendRecord


def _record(day: int, *, outcome="completed", rpe=None, reason=None, sport="ride"):
    return FeedbackTrendRecord(
        scheduled_date=date(2026, 7, day),
        sport_type=sport,
        outcome=outcome,
        perceived_exertion=rpe,
        reason_code=reason,
    )


def test_trends_are_ready_only_after_six_explicit_recent_feedback_records():
    trends = build_training_response_trends(
        as_of_date=date(2026, 7, 26),
        records=(
            _record(1, rpe=5),
            _record(2, rpe=6),
            _record(3, rpe=5),
            _record(4, rpe=4),
            _record(5, rpe=6),
            _record(6, outcome="completed_limited", rpe=7, reason="fatigue"),
            _record(7, outcome="skipped", reason="schedule"),
            _record(8, rpe=5, sport="run"),
            _record(9, rpe=6, sport="run"),
            _record(10, rpe=4, sport="run"),
        ),
    )

    assert trends.status == "ready"
    assert trends.recent.outcomes.feedback_records == 10
    assert trends.recent.outcomes.completed == 8
    assert trends.recent.outcomes.completed_limited == 1
    assert trends.recent.outcomes.skipped == 1
    assert trends.recent.reported_rpe_average == 5.3
    assert trends.recent.reason_counts == (("fatigue", 1), ("schedule", 1))
    assert trends.comparison_available is False
    assert "explicit_feedback_only" in trends.limitations
    assert "insufficient_previous_feedback" in trends.limitations


def test_trends_do_not_treat_missing_feedback_as_a_skipped_session():
    trends = build_training_response_trends(
        as_of_date=date(2026, 7, 26),
        records=(_record(26, outcome="skipped", reason="travel"),),
    )

    assert trends.status == "insufficient_data"
    assert trends.recent.outcomes.feedback_records == 1
    assert trends.recent.outcomes.skipped == 1
    assert trends.recent.outcomes.completed_among_feedback_percent == 0.0
