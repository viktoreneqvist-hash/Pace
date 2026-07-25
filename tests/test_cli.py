from argparse import Namespace
from datetime import date

from pace.cli import app
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
