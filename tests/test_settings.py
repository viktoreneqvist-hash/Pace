from pathlib import Path

import pytest

from pace.config.settings import load_settings, resolve_openai_api_key


def test_default_athlete_timezone_is_stockholm(monkeypatch):
    monkeypatch.delenv("PACE_ATHLETE_TIMEZONE", raising=False)

    assert load_settings().athlete_timezone == "Europe/Stockholm"


def test_invalid_athlete_timezone_is_rejected(monkeypatch):
    monkeypatch.setenv("PACE_ATHLETE_TIMEZONE", "not/a-timezone")

    with pytest.raises(ValueError, match="valid IANA timezone"):
        load_settings()


def test_openai_settings_are_optional_and_have_a_bounded_default_model(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PACE_OPENAI_MODEL", raising=False)

    loaded = load_settings()

    assert loaded.openai_api_key is None
    assert loaded.openai_model == "gpt-5.6-terra"


def test_openai_api_key_loads_from_the_private_local_secrets_file(
    monkeypatch,
    tmp_path: Path,
):
    secrets_file = tmp_path / "running-agent.env"
    secrets_file.write_text('OPENAI_API_KEY="test-key"\nOTHER_SECRET=ignore-me\n')
    secrets_file.chmod(0o600)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PACE_OPENAI_SECRETS_FILE", str(secrets_file))

    loaded = load_settings()

    assert loaded.openai_api_key is None
    assert resolve_openai_api_key(loaded) == "test-key"
    assert loaded.openai_secrets_file == secrets_file


def test_openai_environment_variable_takes_precedence_over_the_secrets_file(
    monkeypatch,
    tmp_path: Path,
):
    secrets_file = tmp_path / "running-agent.env"
    secrets_file.write_text("OPENAI_API_KEY=file-key\n")
    secrets_file.chmod(0o600)
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    monkeypatch.setenv("PACE_OPENAI_SECRETS_FILE", str(secrets_file))

    assert resolve_openai_api_key(load_settings()) == "environment-key"


def test_openai_secrets_file_must_be_owner_only(monkeypatch, tmp_path: Path):
    secrets_file = tmp_path / "running-agent.env"
    secrets_file.write_text("OPENAI_API_KEY=test-key\n")
    secrets_file.chmod(0o644)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PACE_OPENAI_SECRETS_FILE", str(secrets_file))

    with pytest.raises(ValueError, match="readable only by its owner"):
        resolve_openai_api_key(load_settings())
