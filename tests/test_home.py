from datetime import date
from types import SimpleNamespace

from pace.personalization.models import PersonalizationEvidence
from pace.planning.checkpoint_models import PlanCheckpoint
from pace.presentation.home import render_home_html


def test_home_is_a_read_only_entry_point_with_report_links():
    checkpoint = PlanCheckpoint(
        as_of_date=date(2026, 7, 27),
        status="revision_due",
        active_plan_id=5,
        detailed_end_date=date(2026, 8, 9),
        detailed_days_remaining=3,
        upcoming_races=(),
        reasons=("detailed_window_ending",),
        recommended_command="uv run pace plan revise --id 5 --days 14",
    )
    personalization = PersonalizationEvidence(
        as_of_date=date(2026, 7, 27),
        start_date=date(2026, 6, 2),
        feedback_records=0,
        required_feedback_records=12,
        sport_feedback_records=(),
        sport_required_feedback_records=4,
        status="insufficient_data",
        limitations=("explicit_feedback_only",),
    )
    plan = SimpleNamespace(id=5, sessions=())

    html = render_home_html(
        checkpoint=checkpoint,
        plan=plan,
        personalization=personalization,
        races=(),
    )

    assert "uv run pace plan revise --id 5 --days 14" in html
    assert 'href="dashboard.html"' in html
    assert 'href="plan-5.html"' in html
    assert "synkar inte Garmin" in html
