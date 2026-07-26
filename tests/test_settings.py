import pytest

from pace.config.settings import load_settings


def test_default_athlete_timezone_is_stockholm(monkeypatch):
    monkeypatch.delenv("PACE_ATHLETE_TIMEZONE", raising=False)

    assert load_settings().athlete_timezone == "Europe/Stockholm"


def test_invalid_athlete_timezone_is_rejected(monkeypatch):
    monkeypatch.setenv("PACE_ATHLETE_TIMEZONE", "not/a-timezone")

    with pytest.raises(ValueError, match="valid IANA timezone"):
        load_settings()
