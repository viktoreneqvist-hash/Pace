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
