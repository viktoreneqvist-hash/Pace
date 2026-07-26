from argparse import Namespace
from datetime import date

from pace.cli import app

from pace.planning.plan_models import (
    CoachAssessmentFact,
    PlanSessionFact,
    SessionTargetFact,
    TrainingPlanFact,
)
from pace.presentation.plan_views import (
    render_plan_html,
    render_plan_review,
    render_plan_today,
    select_plan_for_today,
    write_plan_html_report,
)


def _plan(*, identifier: int = 3, status: str = "draft") -> TrainingPlanFact:
    return TrainingPlanFact(
        id=identifier,
        parent_plan_id=None,
        status=status,
        contract_version=2,
        goal_mode="general",
        race_id=None,
        as_of_date=date(2026, 7, 26),
        block_start_date=date(2026, 7, 26),
        block_end_date=date(2026, 8, 22),
        detailed_start_date=date(2026, 7, 26),
        detailed_end_date=date(2026, 8, 8),
        block_outline=(
            {
                "week_start": "2026-07-26",
                "week_end": "2026-08-01",
                "focus": "Lugn återgång.",
            },
        ),
        sessions=(
            PlanSessionFact(
                id=16,
                scheduled_date=date(2026, 7, 27),
                sport_type="ride",
                purpose="Lätt <aerob> cykling.",
                distance_meters=20_000,
                duration_seconds=2_700,
                heart_rate_zone=1,
                target=SessionTargetFact("rpe", 2, 3, None, None, None),
                target_display="Z1 (99–118 bpm) | RPE 2–3",
                feedback_outcome="completed",
            ),
            PlanSessionFact(
                id=17,
                scheduled_date=date(2026, 7, 29),
                sport_type="run",
                purpose="Kort lugn löpning.",
                distance_meters=3_000,
                duration_seconds=1_200,
                heart_rate_zone=None,
                target=SessionTargetFact("rpe", 2, 3, None, None, None),
                target_display="RPE 2–3",
                feedback_outcome=None,
            ),
        ),
        coach_assessment=CoachAssessmentFact(
            fact_references=("capacity_profile", "training_preference"),
            observed_facts=("raw-provider-data-must-not-be-rendered",),
            inferences=("Cykling prioriteras utifrån aktuell historik.",),
            rationale="Planen bygger kontinuitet utan fartkrav.",
            uncertainties=("Ingen tävling är angiven.",),
            coaching_principles=("Prioritera jämnhet.",),
            knowledge_references=("progression_continuity",),
        ),
    )


def test_terminal_review_is_readable_and_omits_raw_observed_fact_content():
    review = render_plan_review(_plan(), on_date=date(2026, 7, 26))

    assert "Pace plan 3 — Utkast — inte accepterat" in review
    assert "Nästa pass" in review
    assert "20 km" in review
    assert "Coachens bedömning" in review
    assert "Faktisk träningshistorik och kontinuitet" in review
    assert "Kunskapsstöd" in review
    assert "Progression utan universell veckoregel" in review
    assert "raw-provider-data-must-not-be-rendered" not in review


def test_today_view_shows_the_next_session_when_today_has_no_session():
    today = render_plan_today(_plan(), on_date=date(2026, 7, 26))

    assert "Inget pass är planerat i dag." in today
    assert "27 Jul 2026" in today
    assert "pace plan accept --id 3" in today


def test_today_selection_defaults_to_an_active_accepted_plan():
    accepted = _plan(identifier=4, status="accepted")

    selected = select_plan_for_today(
        (_plan(), accepted), on_date=date(2026, 7, 26), plan_id=None
    )

    assert selected.id == 4


def test_html_report_is_escaped_private_and_rendered_with_owner_only_permissions(tmp_path):
    report_directory = tmp_path / "reports"
    output_path = write_plan_html_report(_plan(), reports_directory=report_directory)
    html = output_path.read_text(encoding="utf-8")

    assert output_path.name == "plan-3.html"
    assert output_path.stat().st_mode & 0o777 == 0o600
    assert report_directory.stat().st_mode & 0o777 == 0o700
    assert "Lätt &lt;aerob&gt; cykling." in html
    assert "raw-provider-data-must-not-be-rendered" not in html
    assert "Kunskapsstöd" in html
    assert "Progression utan universell veckoregel" in html
    assert "Rapporten är en läsvy och ändrar inte planen." in html


def test_html_render_is_self_contained_without_external_urls():
    html = render_plan_html(_plan())

    assert "<style>" in html
    assert "https://" not in html


def test_cli_exposes_readable_review_and_today_views(monkeypatch, capsys):
    plan = _plan()

    class FakePlanService:
        def get_plan(self, *, plan_id: int):
            assert plan_id == 3
            return plan

        def list_plans(self):
            return (plan,)

    monkeypatch.setattr(app, "TrainingPlanService", FakePlanService)

    assert app.run_plan_review(Namespace(id=3)) == 0
    assert "Coachens bedömning" in capsys.readouterr().out
    assert app.run_plan_today(
        Namespace(id=3, date=None), today=date(2026, 7, 26)
    ) == 0
    assert "Nästa pass" in capsys.readouterr().out


def test_cli_report_writes_only_through_the_local_report_boundary(monkeypatch, capsys, tmp_path):
    plan = _plan()
    output_path = tmp_path / "plan-3.html"

    class FakePlanService:
        def get_plan(self, *, plan_id: int):
            assert plan_id == 3
            return plan

    monkeypatch.setattr(app, "TrainingPlanService", FakePlanService)
    monkeypatch.setattr(app, "write_plan_html_report", lambda _plan: output_path)

    assert app.run_plan_report(Namespace(id=3)) == 0
    assert str(output_path) in capsys.readouterr().out


def test_plan_parser_accepts_the_j33_view_commands():
    parser = app.build_parser()

    today_args = parser.parse_args(["plan", "today", "--id", "3"])
    review_args = parser.parse_args(["plan", "review", "--id", "3"])
    report_args = parser.parse_args(["plan", "report", "--id", "3"])

    assert today_args.id == review_args.id == report_args.id == 3
