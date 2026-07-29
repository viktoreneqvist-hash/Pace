from dataclasses import dataclass, field
from datetime import date
import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pace.ai.models import ContextEventDraft
from pace.coach.models import CoachDialogueAnswer, SessionFeedbackDraft
from pace.personalization.models import PersonalizationEvidence
from pace.planning.checkpoint_models import PlanCheckpoint
from pace.training_analysis.models import SportWindowAnalysis, TransparentTrainingAnalysis
from pace.web.app import WebServices, create_app
from pace.web.presentation import render_web_onboarding


@dataclass
class FakePlanService:
    plan: object
    feedback_calls: list[dict]
    draft_calls: list[dict] = field(default_factory=list)

    def list_plans(self):
        return (self.plan,)

    def add_feedback(self, **kwargs):
        self.feedback_calls.append(kwargs)

    def generate_draft(self, **kwargs):
        self.draft_calls.append(kwargs)
        return SimpleNamespace(id=18, goal_mode="general", race_id=kwargs["race_id"])

class FakeCoachService:
    def __init__(self):
        self.calls = []

    def ask(self, **kwargs):
        self.calls.append(kwargs)
        return CoachDialogueAnswer(
            answer="Det här är ett avgränsat coachsvar.",
            observations=("Explicit feedback saknas.",),
            uncertainties=("Orsaken till tröttheten är okänd.",),
            knowledge_references=(),
            adjustment_draft=None,
            context_event_draft=ContextEventDraft(
                event_type="work_stress",
                start_date=date(2026, 7, 27),
                end_date=None,
                ongoing=True,
                note="Hög arbetsstress.",
            ),
            feedback_draft=SessionFeedbackDraft(
                planned_session_id=12,
                outcome="completed_limited",
                perceived_exertion=8,
                reason_code="fatigue",
                note="Ovanligt trött.",
            ),
        )


class FakeContextService:
    def __init__(self):
        self.inputs = []

    def add_event(self, event_input):
        self.inputs.append(event_input)
        return SimpleNamespace(id=44)


class FakeSyncService:
    def __init__(self):
        self.calls = []

    def sync(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            start_date=kwargs["start_date"],
            end_date=kwargs["end_date"],
            activities_fetched=3,
            activities_inserted=1,
            activities_updated=2,
            daily_metrics_fetched=7,
        )


class FakeWeeklyReviewService:
    def __init__(self, output_path):
        self.calls = []
        self.output_path = output_path

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.output_path


def _web_client(tmp_path):
    session = SimpleNamespace(
        id=12,
        scheduled_date=date(2026, 7, 27),
        sport_type="ride",
        purpose="Jämn distanscykling.",
        distance_meters=30_000,
        duration_seconds=5_400,
        target_display="Z2 (119–138 bpm)",
        feedback_outcome=None,
        feedback_perceived_exertion=None,
        feedback_reason_code=None,
        workout_steps=(),
    )
    plan = SimpleNamespace(
        id=7,
        status="accepted",
        goal_mode="race",
        block_start_date=date(2026, 7, 20),
        block_end_date=date(2026, 8, 22),
        detailed_end_date=date(2026, 8, 2),
        detailed_start_date=date(2026, 7, 20),
        block_outline=(),
        coach_assessment=SimpleNamespace(
            rationale="Fortsätt med jämn kontinuitet.",
            inferences=(),
            uncertainties=(),
            coaching_principles=(),
            knowledge_references=(),
            fact_references=(),
        ),
        sessions=(session,),
    )
    plan_service = FakePlanService(plan, [])
    coach = FakeCoachService()
    context = FakeContextService()
    sync = FakeSyncService()
    checkpoint = PlanCheckpoint(
        as_of_date=date(2026, 7, 27),
        status="current",
        active_plan_id=7,
        detailed_end_date=date(2026, 8, 2),
        detailed_days_remaining=6,
        upcoming_races=(),
        reasons=("detailed_window_current",),
        recommended_command=None,
    )
    personalization = PersonalizationEvidence(
        as_of_date=date(2026, 7, 27),
        start_date=date(2026, 6, 2),
        feedback_records=2,
        required_feedback_records=12,
        sport_feedback_records=(("ride", 2),),
        sport_required_feedback_records=4,
        status="insufficient_data",
        limitations=("explicit_feedback_only",),
    )
    analysis = TransparentTrainingAnalysis(
        start_date=date(2026, 6, 30),
        end_date=date(2026, 7, 27),
        sports=(
            SportWindowAnalysis("run", 1, 1, 0.5, 5.0, 0),
            SportWindowAnalysis("ride", 3, 3, 5.0, 120.0, 0),
        ),
        total_duration_hours=5.5,
        total_active_days=4,
        feedback_records=2,
        reported_rpe_average=6.0,
        recovery_coverage=(("hrv", 28, 28),),
        limitations=("no_proprietary_training_load_score",),
    )
    reports_directory = tmp_path / "reports"
    reports_directory.mkdir()
    (reports_directory / "dashboard.html").write_text("<h1>Dashboard</h1>")
    (reports_directory / "plan-7.html").write_text("<h1>Plan 7</h1>")
    (reports_directory / "weekly-review.json").write_text(
        '{"end_date":"2026-07-27","summary":"Veckan är sammanfattad.",'
        '"observations":["En lokal observation."],'
        '"coach_assessment":["En coachbedömning."],'
        '"recommendations":["En rekommendation."],'
        '"uncertainties":["En osäkerhet."]}'
    )
    weekly_review = FakeWeeklyReviewService(reports_directory / "weekly-review.html")
    dashboard_state = SimpleNamespace(
        as_of_date=date(2026, 7, 27),
        recent_recovery_observations=(),
        data_quality=SimpleNamespace(recovery=(), latest_completed_sync=None),
        relevant_context=SimpleNamespace(events=()),
    )
    dashboard_trends = SimpleNamespace(
        recent=SimpleNamespace(
            outcomes=SimpleNamespace(feedback_records=2, completed=1, completed_limited=1, skipped=0),
            reason_counts=(),
            reported_rpe_average=None,
            reported_rpe_data_points=0,
        ),
        recent_required_feedback_records=6,
        limitations=(),
        status="insufficient_data",
    )
    services = WebServices(
        plan_service=plan_service,
        checkpoint_service=SimpleNamespace(get_checkpoint=lambda **_kwargs: checkpoint),
        preference_service=SimpleNamespace(
            get_preference=lambda: SimpleNamespace(
                sport_role="ride_primary",
                coaching_ambition="ambitious",
                available_days=[{"day": "mon", "minutes": None}],
            )
        ),
        zone_service=SimpleNamespace(
            get_profile=lambda **_kwargs: SimpleNamespace(
                zones=[{"zone": 2, "lower_bpm": 119, "upper_bpm": 138}]
            )
        ),
        personalization_service=SimpleNamespace(get_evidence=lambda **_kwargs: personalization),
        race_service=SimpleNamespace(
            list_upcoming_races=lambda **_kwargs: (
                SimpleNamespace(
                    id=3,
                    name="Testlopp",
                    race_date=date(2026, 8, 15),
                    sport_type="run",
                    priority="A",
                    taper_override=None,
                ),
            )
        ),
        analysis_service=SimpleNamespace(get_analysis=lambda **_kwargs: analysis),
        dashboard_service=SimpleNamespace(
            get_dashboard_data=lambda **_kwargs: SimpleNamespace(
                state=dashboard_state,
                trends=dashboard_trends,
                plan=plan,
                activities=(),
                recovery_observations=(),
            )
        ),
        context_service=context,
        reports_directory=reports_directory,
        coach_service_factory=lambda: coach,
        sync_service_factory=lambda: sync,
        weekly_review_service_factory=lambda: weekly_review,
        plan_generation_service_factory=lambda: plan_service,
        today=lambda: date(2026, 7, 27),
    )
    return (
        TestClient(create_app(services=services)),
        plan_service,
        context,
        coach,
        sync,
        weekly_review,
    )


def _csrf(client: TestClient) -> str:
    response = client.get("/")
    match = re.search(r'<meta name="pace-csrf" content="([^"]+)">', response.text)
    assert match is not None
    return match.group(1)


def test_local_web_home_renders_current_plan_and_report_navigation(tmp_path):
    client, _plans, _context, _coach, _sync, _review = _web_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "LOCAL COACHING SYSTEM" in response.text
    assert "COACHKANAL" in response.text
    assert "UTKAST ATT GRANSKA" not in response.text
    assert "Dashboard" in response.text
    assert '"taper": "full"' in response.text
    assert "Offensiv" not in response.text
    assert "Noir" not in response.text


def test_first_run_onboarding_contains_the_complete_local_setup_path():
    page = render_web_onboarding(
        state={
            "onboarding": {
                "active": True,
                "openai_configured": False,
                "garmin_connected": False,
                "preferences_configured": False,
                "ride_zones_required": False,
                "ride_zones_configured": False,
                "history_ready": False,
            },
            "races": [],
        },
        csrf_token="local-csrf",
    )

    assert "Bygg din" in page
    assert "Endast löpning" in page
    assert "Endast cykling" in page
    assert "/api/setup/history/confirm" not in page
    assert "onboarding.js" in page


def test_chat_keeps_conversation_in_server_memory_and_returns_confirmation_drafts(tmp_path):
    client, _plans, _context, coach, _sync, _review = _web_client(tmp_path)
    csrf = _csrf(client)

    response = client.post(
        "/api/chat",
        headers={"X-Pace-CSRF": csrf},
        json={"question": "Jag var ovanligt trött i dag."},
    )

    assert response.status_code == 200
    assert response.json()["context_event_draft"]["event_type"] == "work_stress"
    assert response.json()["feedback_draft"]["perceived_exertion"] == 8
    assert coach.calls[0]["conversation"] == ()


def test_confirmation_endpoints_require_csrf_and_reuse_existing_services(tmp_path):
    client, plans, context, _coach, _sync, _review = _web_client(tmp_path)
    csrf = _csrf(client)

    denied = client.post(
        "/api/context/confirm",
        json={
            "event_type": "work_stress",
            "start_date": "2026-07-27",
            "ongoing": True,
            "note": "Hög arbetsstress.",
        },
    )
    assert denied.status_code == 403

    context_response = client.post(
        "/api/context/confirm",
        headers={"X-Pace-CSRF": csrf},
        json={
            "event_type": "work_stress",
            "start_date": "2026-07-27",
            "end_date": None,
            "ongoing": True,
            "note": "Hög arbetsstress.",
        },
    )
    feedback_response = client.post(
        "/api/feedback/confirm",
        headers={"X-Pace-CSRF": csrf},
        json={
            "planned_session_id": 12,
            "outcome": "completed_limited",
            "perceived_exertion": 8,
            "reason_code": "fatigue",
            "note": "Ovanligt trött.",
        },
    )

    assert context_response.json() == {"status": "saved", "event_id": 44}
    assert feedback_response.json() == {"status": "saved", "session_id": 12}
    assert context.inputs[0].event_type == "work_stress"
    assert plans.feedback_calls[0]["outcome"] == "completed_limited"


def test_plan_draft_confirmation_uses_only_the_selected_race_or_general_mode(tmp_path):
    client, plans, _context, _coach, _sync, _review = _web_client(tmp_path)
    csrf = _csrf(client)

    general = client.post(
        "/api/plan/draft/confirm",
        headers={"X-Pace-CSRF": csrf},
        json={"race_id": None},
    )
    race_target = client.post(
        "/api/plan/draft/confirm",
        headers={"X-Pace-CSRF": csrf},
        json={"race_id": 3},
    )

    assert general.status_code == 200
    assert race_target.status_code == 200
    assert plans.draft_calls == [
        {
            "as_of_date": date(2026, 7, 27),
            "detailed_days": 14,
            "race_id": None,
        },
        {
            "as_of_date": date(2026, 7, 27),
            "detailed_days": 14,
            "race_id": 3,
        },
    ]


def test_settings_is_a_local_view_and_history_sync_keeps_seven_day_batches(tmp_path):
    client, _plans, _context, _coach, sync, _review = _web_client(tmp_path)
    csrf = _csrf(client)

    page = client.get("/settings")
    result = client.post(
        "/api/setup/history/confirm",
        headers={"X-Pace-CSRF": csrf},
        json={"days": 80},
    )

    assert page.status_code == 200
    assert "Inställningar" in page.text
    assert 'href="/settings"' in page.text
    assert result.status_code == 200
    assert len(sync.calls) == 12
    assert all(
        (call["end_date"] - call["start_date"]).days <= 6 for call in sync.calls
    )
    assert sync.calls[-1] == {
        "start_date": date(2026, 5, 9),
        "end_date": date(2026, 5, 11),
    }


def test_history_sync_stream_reports_each_bounded_batch_and_completion(tmp_path):
    client, _plans, _context, _coach, sync, _review = _web_client(tmp_path)
    csrf = _csrf(client)

    response = client.post(
        "/api/setup/history/stream",
        headers={"X-Pace-CSRF": csrf},
        json={"days": 8},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: progress") == 4
    assert "event: completed" in response.text
    assert len(sync.calls) == 2
    assert sync.calls == [
        {"start_date": date(2026, 7, 21), "end_date": date(2026, 7, 27)},
        {"start_date": date(2026, 7, 20), "end_date": date(2026, 7, 20)},
    ]


def test_reports_are_available_only_from_the_safe_local_report_catalog(tmp_path):
    client, _plans, _context, _coach, _sync, _review = _web_client(tmp_path)

    dashboard = client.get("/reports/dashboard.html")
    missing_review = client.get("/reports/weekly-review.html")
    invalid = client.get("/reports/pace.env")

    assert dashboard.status_code == 200
    assert "Dashboard" in dashboard.text
    assert missing_review.status_code == 404
    assert invalid.status_code == 404


def test_in_app_reports_keep_navigation_and_use_current_local_views(tmp_path):
    client, _plans, _context, _coach, _sync, _review = _web_client(tmp_path)

    dashboard = client.get("/dashboard")
    plan = client.get("/plan")
    review = client.get("/weekly-review")

    for response in (dashboard, plan, review):
        assert response.status_code == 200
        assert "LOCAL COACHING SYSTEM" in response.text
        assert 'href="/dashboard"' in response.text
        assert 'href="/plan"' in response.text
        assert 'href="/weekly-review"' in response.text
        assert response.headers["cache-control"] == "no-store"
    assert "Träning · 28 dagar" in dashboard.text
    assert "Detaljerade pass" in plan.text
    assert "Veckan är sammanfattad." in review.text


def test_web_commands_are_allowlisted_and_external_actions_need_confirmation(tmp_path):
    client, _plans, _context, coach, sync, weekly_review = _web_client(tmp_path)
    csrf = _csrf(client)

    help_response = client.post(
        "/api/command", headers={"X-Pace-CSRF": csrf}, json={"command": "/help"}
    )
    sync_draft = client.post(
        "/api/command", headers={"X-Pace-CSRF": csrf}, json={"command": "/sync"}
    )
    sync_result = client.post(
        "/api/command/confirm",
        headers={"X-Pace-CSRF": csrf},
        json={"action": "sync"},
    )
    review_draft = client.post(
        "/api/command",
        headers={"X-Pace-CSRF": csrf},
        json={"command": "/review weekly"},
    )
    review_result = client.post(
        "/api/command/confirm",
        headers={"X-Pace-CSRF": csrf},
        json={"action": "weekly_review"},
    )
    unknown = client.post(
        "/api/command", headers={"X-Pace-CSRF": csrf}, json={"command": "/rm"}
    )

    assert help_response.status_code == 200
    assert "/analysis" in help_response.json()["answer"]
    assert sync_draft.json()["confirmation"]["action"] == "sync"
    assert sync.calls[0]["start_date"] == date(2026, 7, 21)
    assert sync_result.json()["status"] == "completed"
    assert review_draft.json()["confirmation"]["action"] == "weekly_review"
    assert weekly_review.calls == [{"end_date": date(2026, 7, 27)}]
    assert review_result.json()["status"] == "completed"
    assert unknown.status_code == 422
    assert coach.calls == []
