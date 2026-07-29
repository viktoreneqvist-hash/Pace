"""Local application settings for Pace."""

import os
from dataclasses import dataclass
from pathlib import Path
from stat import S_IMODE
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPENAI_SECRETS_FILE = PROJECT_ROOT / ".local" / "pace.env"


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration values used by the Pace application."""

    database_url: str
    garmin_token_dir: Path
    athlete_timezone: str
    openai_api_key: str | None
    openai_model: str
    openai_secrets_file: Path


def load_settings() -> Settings:
    """Load settings from environment variables and safe local defaults."""

    default_database_path = PROJECT_ROOT / "data" / "pace.db"
    default_token_dir = PROJECT_ROOT / ".local" / "garmin_tokens"

    database_url = os.getenv(
        "PACE_DATABASE_URL",
        f"sqlite:///{default_database_path}",
    )

    garmin_token_dir = Path(
        os.getenv(
            "PACE_GARMIN_TOKEN_DIR",
            str(default_token_dir),
        )
    ).expanduser()
    athlete_timezone = os.getenv("PACE_ATHLETE_TIMEZONE", "Europe/Stockholm")
    openai_secrets_file = Path(
        os.getenv("PACE_OPENAI_SECRETS_FILE", str(DEFAULT_OPENAI_SECRETS_FILE))
    ).expanduser()
    openai_api_key = os.getenv("OPENAI_API_KEY") or None
    openai_model = os.getenv("PACE_OPENAI_MODEL", "gpt-5.6-terra")

    try:
        ZoneInfo(athlete_timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError(
            f"PACE_ATHLETE_TIMEZONE is not a valid IANA timezone: {athlete_timezone}"
        ) from error

    return Settings(
        database_url=database_url,
        garmin_token_dir=garmin_token_dir,
        athlete_timezone=athlete_timezone,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        openai_secrets_file=openai_secrets_file,
    )


def _read_openai_api_key(secrets_file: Path) -> str | None:
    """Read only OPENAI_API_KEY from an owner-only local environment file."""

    if not secrets_file.is_file():
        return None

    if S_IMODE(secrets_file.stat().st_mode) & 0o077:
        raise ValueError(
            "PACE_OPENAI_SECRETS_FILE must be readable only by its owner."
        )

    for raw_line in secrets_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, value = line.partition("=")
        if key == "OPENAI_API_KEY" and separator and value.strip():
            return value.strip().strip('"').strip("'")

    return None


settings = load_settings()


def resolve_openai_api_key(config: Settings = settings) -> str | None:
    """Read the local secret only when the explicit AI command needs it."""

    return config.openai_api_key or _read_openai_api_key(config.openai_secrets_file)


def save_openai_api_key(*, api_key: str, config: Settings = settings) -> None:
    """Persist one owner-only API key for Pace's local UI setup flow.

    The value is deliberately written only to Pace's own ignored local file. It
    is never returned by an API response or embedded into HTML.
    """

    clean_key = api_key.strip()
    if not clean_key:
        raise ValueError("OpenAI API-nyckeln får inte vara tom.")
    secrets_file = config.openai_secrets_file
    secrets_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if secrets_file.parent.stat().st_mode & 0o777 != 0o700:
        secrets_file.parent.chmod(0o700)
    secrets_file.write_text(f"OPENAI_API_KEY={clean_key}\n", encoding="utf-8")
    secrets_file.chmod(0o600)
