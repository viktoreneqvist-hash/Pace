from argparse import Namespace
from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect

from pace.cli import app
from pace.analysis.models import (
    PaceMetricSummary,
    RecoveryMetricSummary,
    TrainingSummary,
    TrainingWindowSummary,
)
from pace.services.garmin_sync_service import GarminSyncResult
from pace.explanations.models import ExplanationItem, ExplanationSummary
from pace.ai.models import ContextEventDraft, PaceAIAnswer
from pace.coach.models import CoachDialogueAnswer, PlanAdjustmentDraft
from pace.planning.models import HistoryCoverage, PlanReadiness
from pace.capacity.models import CapacityProfile
from pace.performance.models import (
    PerformanceDetailCoverage,
    PerformanceHistory,
    PerformanceReadiness,
)
from pace.services.performance_history_service import PerformanceSyncResult


def test_login_prompts_for_credentials_and_uses_local_token_directory(
    monkeypatch, capsys
):
    captured: dict[str, object] = {}
    prompts: list[str] = []
    hidden_responses = iter(("password", "123456"))

    class FakeGarminConnectClient:
        @classmethod
        def login_with_credentials(cls, **kwargs):
            captured.update(kwargs)
            captured["mfa"] = kwargs["prompt_mfa"]()

    def hidden_prompt(prompt: str) -> str:
        prompts.append(prompt)
        return next(hidden_responses)

    monkeypatch.setattr(app, "GarminConnectClient", FakeGarminConnectClient)
    monkeypatch.setattr(app, "getpass", hidden_prompt)

    exit_code = app.run_garmin_login(Namespace(email="athlete@example.com"))

    assert exit_code == 0
    assert captured["email"] == "athlete@example.com"
    assert captured["password"] == "password"
    assert captured["mfa"] == "123456"
    assert captured["token_dir"] == app.settings.garmin_token_dir
    assert prompts == ["Garmin-lösenord: ", "Garmin MFA-kod: "]
    assert "Garmin är anslutet" in capsys.readouterr().out


def test_sync_uses_last_seven_calendar_days_and_reports_result(monkeypatch, capsys):
    captured: dict[str, object] = {}

    class FakeGarminConnectClient:
        @classmethod
        def from_saved_tokens(cls, token_dir):
            captured["token_dir"] = token_dir
            return object()

    class FakeSyncService:
        def __init__(self, client):
            captured["client"] = client

        def sync(self, *, start_date, end_date):
            captured["start_date"] = start_date
            captured["end_date"] = end_date
            return GarminSyncResult(
                sync_run_id=1,
                status="success",
                start_date=start_date,
                end_date=end_date,
                activities_fetched=3,
                activities_inserted=2,
                activities_updated=1,
                daily_metrics_fetched=5,
                daily_metrics_inserted=5,
                daily_metrics_updated=0,
                recovery_errors=(),
            )

    monkeypatch.setattr(app, "GarminConnectClient", FakeGarminConnectClient)
    monkeypatch.setattr(app, "GarminSyncService", FakeSyncService)

    exit_code = app.run_sync(Namespace(days=7), today=date(2026, 7, 25))

    assert exit_code == 0
    assert captured["start_date"] == date(2026, 7, 19)
    assert captured["end_date"] == date(2026, 7, 25)
    assert "3 hämtade, 2 nya, 1 uppdaterade aktiviteter" in capsys.readouterr().out


def test_sync_uses_an_explicit_end_date_for_a_bounded_history_batch(
    monkeypatch,
    capsys,
):
    captured: dict[str, date] = {}

    class FakeGarminConnectClient:
        @classmethod
        def from_saved_tokens(cls, _token_dir):
            return object()

    class FakeSyncService:
        def __init__(self, _client):
            pass

        def sync(self, *, start_date, end_date):
            captured.update(start_date=start_date, end_date=end_date)
            return GarminSyncResult(
                sync_run_id=1,
                status="success",
                start_date=start_date,
                end_date=end_date,
                activities_fetched=0,
                activities_inserted=0,
                activities_updated=0,
                daily_metrics_fetched=0,
                daily_metrics_inserted=0,
                daily_metrics_updated=0,
                recovery_errors=(),
            )

    monkeypatch.setattr(app, "GarminConnectClient", FakeGarminConnectClient)
    monkeypatch.setattr(app, "GarminSyncService", FakeSyncService)

    exit_code = app.run_sync(
        Namespace(days=7, end_date=date(2026, 6, 14)),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    assert captured == {
        "start_date": date(2026, 6, 8),
        "end_date": date(2026, 6, 14),
    }
    capsys.readouterr()


def test_sync_rejects_a_non_positive_day_count():
    parser = app.build_parser()

    try:
        parser.parse_args(["sync", "--days", "0"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("The parser should reject zero days.")


def test_sync_rejects_more_than_seven_days():
    parser = app.build_parser()

    try:
        parser.parse_args(["sync", "--days", "8"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("The parser should reject an unbounded batch.")


def test_partial_rate_limit_returns_retryable_exit_code(monkeypatch, capsys):
    class FakeGarminConnectClient:
        @classmethod
        def from_saved_tokens(cls, _token_dir):
            return object()

    class FakeSyncService:
        def __init__(self, _client):
            pass

        def sync(self, *, start_date, end_date):
            return GarminSyncResult(
                sync_run_id=1,
                status="partial",
                start_date=start_date,
                end_date=end_date,
                activities_fetched=1,
                activities_inserted=1,
                activities_updated=0,
                daily_metrics_fetched=1,
                daily_metrics_inserted=1,
                daily_metrics_updated=0,
                recovery_errors=("rate limited",),
                recovery_stop_reason="rate_limit",
            )

    monkeypatch.setattr(app, "GarminConnectClient", FakeGarminConnectClient)
    monkeypatch.setattr(app, "GarminSyncService", FakeSyncService)

    exit_code = app.run_sync(
        Namespace(days=1, end_date=date(2026, 7, 25)),
    )

    assert exit_code == 3
    assert "vänta och kör samma batch igen" in capsys.readouterr().out


def test_db_init_applies_migrations_to_a_new_private_database(
    monkeypatch,
    tmp_path: Path,
    capsys,
):
    database_path = tmp_path / "pace-init.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setattr(
        app,
        "settings",
        SimpleNamespace(database_url=database_url),
    )

    exit_code = app.run_db_init(Namespace())

    assert exit_code == 0
    assert {
        "activities",
        "context_events",
        "daily_metrics",
        "sync_runs",
    }.issubset(inspect(create_engine(database_url)).get_table_names())
    assert database_path.stat().st_mode & 0o777 == 0o600
    assert "senaste schema" in capsys.readouterr().out


def test_metrics_summary_prints_structured_local_facts(monkeypatch, capsys):
    training_window = TrainingWindowSummary(
        start_date=date(2026, 7, 19),
        end_date=date(2026, 7, 25),
        activity_count=3,
        active_days=3,
        running_distance_km=20,
        cycling_duration_hours=2,
        total_duration_hours=4,
        longest_run_km=12,
        longest_ride_km=40,
    )
    summary = PaceMetricSummary(
        end_date=date(2026, 7, 25),
        training=TrainingSummary(
            current=training_window,
            previous=training_window,
            running_distance_change_percent=0,
            cycling_duration_change_percent=0,
        ),
        recovery=(
            RecoveryMetricSummary(
                metric="hrv",
                unit="ms",
                baseline_start_date=date(2026, 6, 28),
                baseline_end_date=date(2026, 7, 25),
                baseline_value=55,
                baseline_data_points=7,
                expected_baseline_days=28,
                recent_start_date=date(2026, 7, 19),
                recent_end_date=date(2026, 7, 25),
                recent_value=55,
                recent_data_points=7,
                latest_value=57,
                latest_date=date(2026, 7, 25),
                latest_deviation_percent=3.64,
            ),
        ),
    )

    class FakeMetricService:
        def get_summary(self, *, end_date):
            assert end_date == date(2026, 7, 25)
            return summary

    monkeypatch.setattr(app, "MetricService", FakeMetricService)

    exit_code = app.run_metrics_summary(
        Namespace(end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["training"]["current"]["running_distance_km"] == 20
    assert payload["recovery"][0]["metric"] == "hrv"


def test_note_add_and_list_use_the_context_service(monkeypatch, capsys):
    captured: dict[str, object] = {}

    class FakeContextService:
        def add_event(self, event_input):
            captured["input"] = event_input
            return SimpleNamespace(
                event_type="poor_sleep",
                start_date=date(2026, 7, 25),
                end_date=date(2026, 7, 25),
            )

        def list_events(self, *, start_date, end_date):
            captured["range"] = (start_date, end_date)
            return []

    monkeypatch.setattr(app, "ContextService", FakeContextService)

    add_exit_code = app.run_note_add(
        Namespace(
            event_type="poor_sleep",
            start_date=date(2026, 7, 25),
            end_date=None,
            ongoing=False,
            note="Somnade sent.",
        )
    )
    list_exit_code = app.run_note_list(
        Namespace(
            start_date=date(2026, 7, 19),
            end_date=date(2026, 7, 25),
        )
    )

    assert add_exit_code == 0
    assert list_exit_code == 0
    assert captured["input"].event_type == "poor_sleep"
    assert captured["range"] == (date(2026, 7, 19), date(2026, 7, 25))
    output = capsys.readouterr().out
    assert "Context-not sparad" in output
    assert "[]" in output


def test_note_parser_limits_the_first_context_contract():
    parser = app.build_parser()

    args = parser.parse_args(
        [
            "note",
            "add",
            "--type",
            "pain",
            "--date",
            "2026-07-25",
            "--ongoing",
            "Känning i vänster vad.",
        ]
    )

    assert args.event_type == "pain"
    assert args.ongoing is True


def test_state_show_uses_the_read_only_state_service(monkeypatch, capsys):
    captured: dict[str, date] = {}

    @dataclass
    class FakeAthleteState:
        as_of_date: date

    class FakeAthleteStateService:
        def get_state(self, *, end_date):
            captured["end_date"] = end_date
            return FakeAthleteState(as_of_date=end_date)

    monkeypatch.setattr(app, "AthleteStateService", FakeAthleteStateService)

    exit_code = app.run_state_show(
        Namespace(end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    assert captured["end_date"] == date(2026, 7, 25)
    assert json.loads(capsys.readouterr().out) == {"as_of_date": "2026-07-25"}


def test_state_show_parser_accepts_a_reproducible_end_date():
    parser = app.build_parser()

    args = parser.parse_args(["state", "show", "--end-date", "2026-07-25"])

    assert args.end_date == date(2026, 7, 25)


def test_rules_evaluate_uses_the_deterministic_rule_service(monkeypatch, capsys):
    captured: dict[str, date] = {}

    @dataclass
    class FakeRuleSummary:
        as_of_date: date

    class FakeRuleService:
        def evaluate(self, *, end_date):
            captured["end_date"] = end_date
            return FakeRuleSummary(as_of_date=end_date)

    monkeypatch.setattr(app, "RuleService", FakeRuleService)

    exit_code = app.run_rules_evaluate(
        Namespace(end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    assert captured["end_date"] == date(2026, 7, 25)
    assert json.loads(capsys.readouterr().out) == {"as_of_date": "2026-07-25"}


def test_rules_evaluate_parser_accepts_a_reproducible_end_date():
    parser = app.build_parser()

    args = parser.parse_args(["rules", "evaluate", "--end-date", "2026-07-25"])

    assert args.end_date == date(2026, 7, 25)


def test_explain_uses_the_deterministic_explanation_service(monkeypatch, capsys):
    captured: dict[str, date] = {}

    class FakeExplanationService:
        def explain(self, *, end_date):
            captured["end_date"] = end_date
            return ExplanationSummary(
                as_of_date=end_date,
                items=(ExplanationItem("test", "Deterministisk testförklaring."),),
                context_check_in=None,
            )

    monkeypatch.setattr(app, "ExplanationService", FakeExplanationService)

    exit_code = app.run_explain(
        Namespace(end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    assert captured["end_date"] == date(2026, 7, 25)
    assert "Deterministisk testförklaring." in capsys.readouterr().out


def test_explain_parser_accepts_a_reproducible_end_date():
    parser = app.build_parser()

    args = parser.parse_args(["explain", "--end-date", "2026-07-25"])

    assert args.end_date == date(2026, 7, 25)


def test_ask_requires_a_local_api_key_before_building_or_sending_context(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        app,
        "settings",
        SimpleNamespace(
            openai_api_key=None,
            openai_model="test-model",
            openai_secrets_file=Path("/missing/running-agent.env"),
        ),
    )

    exit_code = app.run_ask(
        Namespace(question="Hur ser läget ut?", end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().out


def test_ask_uses_the_read_only_service_and_marks_context_drafts_as_unsaved(
    monkeypatch, capsys
):
    captured: dict[str, object] = {}

    class FakeAskService:
        def __init__(self, *, client):
            captured["client"] = client

        def ask(self, *, question, end_date):
            captured["question"] = question
            captured["end_date"] = end_date
            return PaceAIAnswer(
                answer="Pace använder den valda faktabilden.",
                observations=("HRV-underlaget är begränsat.",),
                uncertainties=("Ingen slutsats kan dras ännu.",),
                context_event_draft=ContextEventDraft(
                    event_type="alcohol",
                    start_date=date(2026, 7, 24),
                    end_date=date(2026, 7, 24),
                    ongoing=False,
                    note="Sen kväll.",
                ),
            )

    monkeypatch.setattr(
        app,
        "settings",
        SimpleNamespace(
            openai_api_key="test-key",
            openai_model="test-model",
            openai_secrets_file=Path("/missing/running-agent.env"),
        ),
    )
    monkeypatch.setattr(app, "PaceAskService", FakeAskService)

    exit_code = app.run_ask(
        Namespace(question="Varför är HRV lägre?", end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    assert captured["question"] == "Varför är HRV lägre?"
    assert captured["end_date"] == date(2026, 7, 25)
    output = capsys.readouterr().out
    assert "Context-utkast — inte sparat" in output
    assert "AI:n kan inte spara dem" in output
    assert "Kopiera detta om uppgifterna stämmer:" in output
    assert (
        "uv run pace note add --type alcohol --date 2026-07-24 'Sen kväll.'"
        in output
    )


def test_ask_parser_accepts_a_reproducible_end_date():
    parser = app.build_parser()

    args = parser.parse_args(["ask", "Hur ser läget ut?", "--end-date", "2026-07-25"])

    assert args.question == "Hur ser läget ut?"
    assert args.end_date == date(2026, 7, 25)


def test_knowledge_commands_read_the_local_curated_library_without_an_ai_call(capsys):
    list_exit_code = app.run_knowledge_list(Namespace())
    list_output = capsys.readouterr().out
    show_exit_code = app.run_knowledge_show(Namespace(brief_id="hrv_training_context"))
    show_output = capsys.readouterr().out

    assert list_exit_code == 0
    assert "hrv_training_context" in list_output
    assert show_exit_code == 0
    assert "Begränsningar:" in show_output
    assert "pubmed.ncbi.nlm.nih.gov" in show_output


def test_knowledge_parser_accepts_a_brief_id():
    parser = app.build_parser()

    args = parser.parse_args(["knowledge", "show", "--id", "progression_continuity"])

    assert args.brief_id == "progression_continuity"


def test_coach_parser_accepts_a_quick_question_and_an_interactive_dialogue():
    parser = app.build_parser()

    ask_args = parser.parse_args(
        ["coach", "ask", "Kan jag byta?", "--plan-id", "3", "--end-date", "2026-07-25"]
    )
    chat_args = parser.parse_args(["coach", "chat", "--plan-id", "3"])

    assert ask_args.plan_id == 3
    assert ask_args.end_date == date(2026, 7, 25)
    assert chat_args.plan_id == 3


def test_preferences_parser_accepts_coaching_ambition():
    parser = app.build_parser()

    args = parser.parse_args(
        [
            "preferences",
            "set",
            "--sport-role",
            "ride_primary",
            "--ambition",
            "ambitious",
            "--day",
            "mon:any",
        ]
    )

    assert args.ambition == "ambitious"

    change_args = parser.parse_args(
        ["preferences", "ambition", "--ambition", "cautious"]
    )

    assert change_args.ambition == "cautious"


def test_coach_renderer_marks_a_replacement_as_unsaved():
    answer = CoachDialogueAnswer(
        answer="Byt passet.",
        observations=(),
        uncertainties=(),
        knowledge_references=(),
        adjustment_draft=PlanAdjustmentDraft(
            action="skip",
            replaces_session_id=4,
            rationale="Aktuellt underlag är begränsat.",
            proposed_session=None,
        ),
    )

    rendered = app._render_coach_answer(answer, plan_id=3, as_of_date=date(2026, 7, 25))

    assert "Planjusteringsutkast — inte sparat" in rendered
    assert "pace plan revise --id 3 --days 7" in rendered


def test_race_add_passes_only_explicit_race_choices_to_the_service(monkeypatch, capsys):
    captured: dict[str, object] = {}

    class FakeRaceService:
        def add_race(self, race_input):
            captured["input"] = race_input
            return SimpleNamespace(
                name=race_input.name,
                race_date=race_input.race_date,
                priority=race_input.priority,
                taper_override=None,
            )

    monkeypatch.setattr(app, "RaceService", FakeRaceService)
    monkeypatch.setattr(app, "resolved_taper", lambda _race: "full")

    exit_code = app.run_race_add(
        Namespace(
            name="Stockholm Marathon",
            sport="run",
            date=date(2026, 10, 10),
            distance_km=42.195,
            priority="A",
            desired_time=10_800,
            taper=None,
        )
    )

    assert exit_code == 0
    assert captured["input"].distance_meters == 42_195
    assert captured["input"].desired_time_seconds == 10_800
    assert "taper full" in capsys.readouterr().out


def test_plan_readiness_prints_deterministic_planning_gates(monkeypatch, capsys):
    readiness = PlanReadiness(
        as_of_date=date(2026, 7, 25),
        status="blocked",
        history=HistoryCoverage(
            required_calendar_days=28,
            covered_calendar_days=7,
            required_start_date=date(2026, 6, 28),
            covered_start_date=date(2026, 7, 19),
            covered_end_date=date(2026, 7, 25),
            is_contiguous=False,
        ),
        upcoming_races=(),
        blockers=(),
        limitations=("requires_28_contiguous_garmin_history_days",),
    )

    class FakePlanReadinessService:
        def get_readiness(self, *, as_of_date):
            assert as_of_date == date(2026, 7, 25)
            return readiness

    monkeypatch.setattr(app, "PlanReadinessService", FakePlanReadinessService)

    exit_code = app.run_plan_readiness(
        Namespace(end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["history"]["covered_calendar_days"] == 7


def test_race_and_plan_parsers_accept_the_j1_contract():
    parser = app.build_parser()

    race_args = parser.parse_args(
        [
            "race",
            "add",
            "Stockholm Marathon",
            "--date",
            "2026-10-10",
            "--sport",
            "run",
            "--distance-km",
            "42.195",
            "--priority",
            "A",
            "--desired-time",
            "3:00:00",
        ]
    )
    readiness_args = parser.parse_args(
        ["plan", "readiness", "--end-date", "2026-07-25"]
    )

    assert race_args.desired_time == 10_800
    assert race_args.distance_km == 42.195
    assert readiness_args.end_date == date(2026, 7, 25)


def test_capacity_show_prints_read_only_capacity_facts(monkeypatch, capsys):
    profile = CapacityProfile(
        as_of_date=date(2026, 7, 25),
        status="ready",
        source_start_date=date(2026, 6, 28),
        source_end_date=date(2026, 7, 25),
        history=HistoryCoverage(28, 28, date(2026, 6, 28), date(2026, 6, 28), date(2026, 7, 25), True),
        sports=(),
        continuity=None,
        sport_balance=None,
        recovery_coverage=(),
        upcoming_races=(),
        planning_blockers=(),
        limitations=("performance_readiness_required_for_j3",),
    )

    class FakeCapacityService:
        def get_profile(self, *, end_date):
            assert end_date == date(2026, 7, 25)
            return profile

    monkeypatch.setattr(app, "CapacityService", FakeCapacityService)

    exit_code = app.run_capacity_show(
        Namespace(end_date=None),
        today=date(2026, 7, 25),
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ready"


def test_performance_sync_uses_the_same_bounded_window_without_main_sync(
    monkeypatch, capsys
):
    captured: dict[str, object] = {}

    class FakeGarminConnectClient:
        @classmethod
        def from_saved_tokens(cls, token_dir):
            captured["token_dir"] = token_dir
            return object()

    class FakePerformanceHistoryService:
        def __init__(self, client):
            captured["client"] = client

        def sync_details(self, *, start_date, end_date):
            captured["window"] = (start_date, end_date)
            return PerformanceSyncResult(
                sync_run_id=1,
                status="success",
                start_date=start_date,
                end_date=end_date,
                candidate_activities=2,
                details_fetched=2,
                details_inserted=1,
                details_updated=1,
                errors=(),
            )

    monkeypatch.setattr(app, "GarminConnectClient", FakeGarminConnectClient)
    monkeypatch.setattr(app, "PerformanceHistoryService", FakePerformanceHistoryService)

    exit_code = app.run_performance_sync(
        Namespace(days=7, end_date=None), today=date(2026, 7, 25)
    )

    assert exit_code == 0
    assert captured["window"] == (date(2026, 7, 19), date(2026, 7, 25))
    assert "2 run/ride-kandidater" in capsys.readouterr().out


def test_performance_show_prints_local_facts_without_target_generation(monkeypatch, capsys):
    history = PerformanceHistory(
        as_of_date=date(2026, 7, 25),
        detail_coverage=PerformanceDetailCoverage(
            start_date=date(2026, 5, 3),
            end_date=date(2026, 7, 25),
            eligible_activities=2,
            detailed_activities=1,
            missing_details=1,
        ),
        detailed_activities=(),
        race_evidence=(),
        benchmark_evidence=(),
        limitations=("performance_target_proposals_belong_to_j3",),
    )

    class FakePerformanceHistoryService:
        def get_history(self, *, end_date):
            assert end_date == date(2026, 7, 25)
            return history

    monkeypatch.setattr(app, "PerformanceHistoryService", FakePerformanceHistoryService)

    exit_code = app.run_performance_show(
        Namespace(end_date=None), today=date(2026, 7, 25)
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["detail_coverage"]["missing_details"] == 1


def test_performance_parsers_accept_bounded_sync_and_explicit_race_link():
    parser = app.build_parser()

    sync_args = parser.parse_args(
        ["performance", "sync", "--days", "7", "--end-date", "2026-07-25"]
    )
    link_args = parser.parse_args(
        [
            "performance",
            "link-race",
            "--garmin-activity-id",
            "12345",
            "--race-id",
            "8",
        ]
    )

    assert sync_args.days == 7
    assert sync_args.end_date == date(2026, 7, 25)
    assert link_args.garmin_activity_id == "12345"
    assert link_args.race_id == 8


def test_performance_parser_accepts_an_approved_benchmark_and_readiness_date():
    parser = app.build_parser()

    benchmark_args = parser.parse_args(
        [
            "performance",
            "mark-benchmark",
            "--garmin-activity-id",
            "12345",
            "--protocol",
            "run_5k_time_trial",
        ]
    )
    readiness_args = parser.parse_args(
        ["performance", "readiness", "--end-date", "2026-07-25"]
    )

    assert benchmark_args.protocol == "run_5k_time_trial"
    assert readiness_args.end_date == date(2026, 7, 25)


def test_performance_readiness_prints_python_owned_eligibility(monkeypatch, capsys):
    readiness = PerformanceReadiness(
        as_of_date=date(2026, 7, 25),
        evidence_start_date=date(2026, 5, 3),
        history=HistoryCoverage(28, 28, date(2026, 6, 28), date(2026, 6, 28), date(2026, 7, 25), True),
        planning_blockers=(),
        sports=(),
    )

    class FakePerformanceHistoryService:
        def get_readiness(self, *, end_date):
            assert end_date == date(2026, 7, 25)
            return readiness

    monkeypatch.setattr(app, "PerformanceHistoryService", FakePerformanceHistoryService)

    exit_code = app.run_performance_readiness(
        Namespace(end_date=None), today=date(2026, 7, 25)
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["evidence_start_date"] == "2026-05-03"
