from datetime import date

from pace.presentation.dashboard import render_dashboard_html, write_dashboard_html
from pace.state.models import (
    AthleteContextWindow,
    AthleteState,
    AthleteStateDataQuality,
)
from pace.trends.analysis import build_training_response_trends


class _Metrics:
    pass


def _state():
    return AthleteState(
        as_of_date=date(2026, 7, 26),
        metrics=_Metrics(),
        relevant_context=AthleteContextWindow(date(2026, 7, 20), date(2026, 7, 26), ()),
        data_quality=AthleteStateDataQuality(None, ()),
        recent_recovery_observations=(),
        garmin_current_facts=(),
    )


def test_dashboard_is_self_contained_and_owner_only(tmp_path, monkeypatch):
    import pace.presentation.dashboard as dashboard

    monkeypatch.setattr(dashboard, "DASHBOARD_PATH", tmp_path / "reports" / "dashboard.html")
    trends = build_training_response_trends(as_of_date=date(2026, 7, 26), records=())

    output = write_dashboard_html(state=_state(), trends=trends, plan=None, activities=())
    html = output.read_text(encoding="utf-8")

    assert output.name == "dashboard.html"
    assert output.stat().st_mode & 0o777 == 0o600
    assert "Träning · 28 dagar" in html
    assert "https://" not in html
    assert "Ingen accepterad aktiv plan" in html


def test_dashboard_renders_without_raw_notes_or_external_assets():
    trends = build_training_response_trends(as_of_date=date(2026, 7, 26), records=())
    html = render_dashboard_html(state=_state(), trends=trends, plan=None, activities=())

    assert "LOKAL DASHBOARD" in html
    assert "Dashboarden är läsande" in html
