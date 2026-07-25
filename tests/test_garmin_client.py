from datetime import date
from pathlib import Path

import pytest
from garminconnect import GarminConnectConnectionError

from pace.integrations.garmin import client as client_module
from pace.integrations.garmin.client import (
    GarminAuthenticationRequiredError,
    GarminConnectClient,
)


class FakeGarmin:
    instances: list["FakeGarmin"] = []
    login_error: Exception | None = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.login_token_dir: str | None = None
        self.activity_args: tuple[str, str] | None = None
        FakeGarmin.instances.append(self)

    def login(self, token_dir: str) -> None:
        self.login_token_dir = token_dir
        if self.login_error is not None:
            raise self.login_error

    def get_activities_by_date(self, start_date: str, end_date: str):
        self.activity_args = (start_date, end_date)
        return [{"activityId": "one"}]


@pytest.fixture(autouse=True)
def reset_fake_garmin(monkeypatch):
    FakeGarmin.instances = []
    FakeGarmin.login_error = None
    monkeypatch.setattr(client_module, "Garmin", FakeGarmin)


def test_login_uses_private_token_directory_and_never_keeps_password(tmp_path: Path):
    token_dir = tmp_path / "tokens"

    client = GarminConnectClient.login_with_credentials(
        email="athlete@example.com",
        password="not-stored",
        token_dir=token_dir,
        prompt_mfa=lambda: "123456",
    )

    api = FakeGarmin.instances[0]
    assert client is not None
    assert api.kwargs["email"] == "athlete@example.com"
    assert api.kwargs["password"] == "not-stored"
    assert api.login_token_dir == str(token_dir)
    assert token_dir.stat().st_mode & 0o777 == 0o700


def test_saved_token_session_is_used_for_activity_requests(tmp_path: Path):
    client = GarminConnectClient.from_saved_tokens(tmp_path / "tokens")

    activities = client.get_activities(date(2026, 7, 1), date(2026, 7, 7))

    api = FakeGarmin.instances[0]
    assert api.kwargs == {}
    assert api.activity_args == ("2026-07-01", "2026-07-07")
    assert activities == [{"activityId": "one"}]


def test_missing_saved_session_has_a_clear_pace_error(tmp_path: Path):
    FakeGarmin.login_error = GarminConnectConnectionError("missing token file")

    with pytest.raises(GarminAuthenticationRequiredError, match="pace garmin login"):
        GarminConnectClient.from_saved_tokens(tmp_path / "tokens")
