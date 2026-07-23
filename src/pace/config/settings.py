"""Local application settings for Pace."""

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration values used by the Pace application."""

    database_url: str
    garmin_token_dir: Path


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

    return Settings(
        database_url=database_url,
        garmin_token_dir=garmin_token_dir,
    )


settings = load_settings()
