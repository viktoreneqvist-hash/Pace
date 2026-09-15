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
    preference = SimpleNamespace(
        coaching_ambition="ambitious",
        sport_role="ride_primary",
        available_days=[
            {"day": "mon", "minutes": None},
            {"day": "wed", "minutes": 90},
        ],
    )
    ride_zone_profile = SimpleNamespace(
        zones=[
            {"zone": 1, "lower_bpm": 99, "upper_bpm": 118},
            {"zone": 2, "lower_bpm": 119, "upper_bpm": 138},
        ]
    )

    html = render_home_html(
        checkpoint=checkpoint,
        plan=plan,
        personalization=personalization,
        races=(),
        preference=preference,
        ride_zone_profile=ride_zone_profile,
    )

    assert "uv run pace plan revise --id 5 --days 14" in html
    assert 'href="dashboard.html"' in html
    assert 'href="plan-5.html"' in html
    assert "Ambitious" in html
    assert "Cycling primary" in html
    assert "Mon</b> · no time limit" in html
    assert "Wed</b> · 90 min" in html
    assert "Z2</b> · 119–138 bpm" in html
    assert "does not sync Garmin" in html


def test_home_handles_missing_optional_settings():
    checkpoint = PlanCheckpoint(
        as_of_date=date(2026, 7, 27),
        status="no_active_plan",
        active_plan_id=None,
        detailed_end_date=None,
        detailed_days_remaining=None,
        upcoming_races=(),
        reasons=("no_active_accepted_plan",),
        recommended_command="uv run pace plan draft --days 14",
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

    html = render_home_html(
        checkpoint=checkpoint,
        plan=None,
        personalization=personalization,
        races=(),
        preference=None,
        ride_zone_profile=None,
    )

    assert "Planning preferences" in html
    assert "Not configured" in html
    assert "No cycling zones saved" in html
