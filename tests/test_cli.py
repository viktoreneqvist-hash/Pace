from argparse import Namespace
from datetime import date
import json

from pace.cli import app
from pace.analysis.models import (
    PaceMetricSummary,
    RecoveryMetricSummary,
    TrainingSummary,
    TrainingWindowSummary,
)
from pace.services.garmin_sync_service import GarminSyncResult


def test_login_prompts_for_credentials_and_uses_local_token_directory(monkeypatch, capsys):
    captured: dict[str, object] = {}

    class FakeGarminConnectClient:
        @classmethod
        def login_with_credentials(cls, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(app, "GarminConnectClient", FakeGarminConnectClient)
    monkeypatch.setattr(app, "getpass", lambda _: "password")

    exit_code = app.run_garmin_login(Namespace(email="athlete@example.com"))

    assert exit_code == 0
    assert captured["email"] == "athlete@example.com"
    assert captured["password"] == "password"
    assert captured["token_dir"] == app.settings.garmin_token_dir
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


def test_sync_rejects_a_non_positive_day_count():
    parser = app.build_parser()

    try:
        parser.parse_args(["sync", "--days", "0"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("The parser should reject zero days.")


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
