from datetime import date
from pathlib import Path

import pytest
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
)

from pace.integrations.garmin import client as client_module
from pace.integrations.garmin.client import (
    GarminAuthenticationRequiredError,
    GarminConnectClient,
    GarminIntegrationError,
    secure_token_file,
)


class FakeGarmin:
    instances: list["FakeGarmin"] = []
    login_error: Exception | None = None
    write_token_file = True

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.client = self
        self.login_token_dir: str | None = None
        self.activity_args: tuple[str, str] | None = None
        self.detail_args: tuple[str, int, int] | None = None
        self.split_activity_id: str | None = None
        FakeGarmin.instances.append(self)

    def login(self, token_dir: str) -> None:
        self.login_token_dir = token_dir
        if self.login_error is not None:
            raise self.login_error

    def dump(self, token_dir: str) -> None:
        if self.write_token_file:
            (Path(token_dir) / "garmin_tokens.json").write_text(
                '{"di_token":"synthetic"}',
                encoding="utf-8",
            )
        else:
            raise OSError("synthetic disk failure")

    def get_activities_by_date(self, start_date: str, end_date: str):
        self.activity_args = (start_date, end_date)
        return [{"activityId": "one"}]

    def get_activity_details(self, activity_id: str, maxchart: int, maxpoly: int):
        self.detail_args = (activity_id, maxchart, maxpoly)
        return {"activityDetailDTO": {}}

    def get_activity_splits(self, activity_id: str):
        self.split_activity_id = activity_id
        return {"lapDTOs": []}


@pytest.fixture(autouse=True)
def reset_fake_garmin(monkeypatch):
    FakeGarmin.instances = []
    FakeGarmin.login_error = None
    FakeGarmin.write_token_file = True
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
    token_file = token_dir / "garmin_tokens.json"
    assert token_file.stat().st_size > 0
    assert token_file.stat().st_mode & 0o777 == 0o600


def test_secure_token_file_uses_owner_only_permissions(tmp_path: Path):
    token_file = tmp_path / "garmin_tokens.json"
    token_file.touch(mode=0o644)
    token_file.chmod(0o644)

    secure_token_file(tmp_path)

    assert token_file.stat().st_mode & 0o777 == 0o600


def test_login_fails_if_a_reusable_token_was_not_saved(tmp_path: Path):
    FakeGarmin.write_token_file = False

    with pytest.raises(GarminIntegrationError, match="could not be saved locally"):
        GarminConnectClient.login_with_credentials(
            email="athlete@example.com",
            password="not-stored",
            token_dir=tmp_path / "tokens",
            prompt_mfa=lambda: "123456",
        )


def test_saved_token_session_is_used_for_activity_requests(tmp_path: Path):
    token_dir = tmp_path / "tokens"
    token_dir.mkdir()
    (token_dir / "garmin_tokens.json").touch()

    client = GarminConnectClient.from_saved_tokens(token_dir)

    activities = client.get_activities(date(2026, 7, 1), date(2026, 7, 7))

    api = FakeGarmin.instances[0]
    assert api.kwargs == {}
    assert api.activity_args == ("2026-07-01", "2026-07-07")
    assert activities == [{"activityId": "one"}]


def test_performance_requests_disable_route_and_chart_data(tmp_path: Path):
    token_dir = tmp_path / "tokens"
    token_dir.mkdir()
    (token_dir / "garmin_tokens.json").touch()

    client = GarminConnectClient.from_saved_tokens(token_dir)
    client.get_activity_performance_detail("123")
    client.get_activity_splits("123")

    api = FakeGarmin.instances[0]
    assert api.detail_args == ("123", 1, 0)
    assert api.split_activity_id == "123"


def test_missing_saved_session_has_a_clear_pace_error(tmp_path: Path):
    with pytest.raises(GarminAuthenticationRequiredError, match="pace garmin login"):
        GarminConnectClient.from_saved_tokens(tmp_path / "tokens")


def test_invalid_saved_session_requires_login(tmp_path: Path):
    token_dir = tmp_path / "tokens"
    token_dir.mkdir()
    (token_dir / "garmin_tokens.json").touch()
    FakeGarmin.login_error = GarminConnectAuthenticationError("expired")

    with pytest.raises(GarminAuthenticationRequiredError, match="pace garmin login"):
        GarminConnectClient.from_saved_tokens(token_dir)


def test_connection_failure_does_not_claim_tokens_are_missing(tmp_path: Path):
    token_dir = tmp_path / "tokens"
    token_dir.mkdir()
    (token_dir / "garmin_tokens.json").touch()
    FakeGarmin.login_error = GarminConnectConnectionError("offline")

    with pytest.raises(GarminIntegrationError, match="connection error"):
        GarminConnectClient.from_saved_tokens(token_dir)
