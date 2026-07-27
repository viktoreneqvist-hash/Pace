from datetime import date

from pace.services.personalization_evidence_service import _patterns
from pace.trends.models import FeedbackTrendRecord


def test_patterns_are_structured_observations_over_explicit_feedback_only():
    records = tuple(
        FeedbackTrendRecord(
            scheduled_date=date(2026, 7, day),
            sport_type="run" if day % 2 else "ride",
            outcome="completed" if day <= 9 else "completed_limited",
            perceived_exertion=5,
            reason_code="fatigue" if day >= 10 else None,
        )
        for day in range(1, 13)
    )

    patterns = _patterns(records)

    ids = {item.pattern_id for item in patterns}
    assert "overall_explicit_completion" in ids
    assert "overall_reported_rpe" in ids
    assert "run_explicit_completion" in ids
    assert "ride_explicit_completion" in ids
    assert all(item.data_points >= 3 for item in patterns)
