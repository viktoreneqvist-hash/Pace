"""Shared test configuration for an isolated migrated SQLite database."""

import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import delete


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / "pace-test-suite.db"

TEST_DATABASE_PATH.unlink(missing_ok=True)
os.environ["PACE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH}"


def pytest_sessionstart() -> None:
    """Create a fresh test database by applying the real Alembic migrations."""

    alembic_config = Config(PROJECT_ROOT / "alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", os.environ["PACE_DATABASE_URL"])
    command.upgrade(alembic_config, "head")


@pytest.fixture(autouse=True)
def clear_database() -> None:
    """Keep tests independent while using the same migrated test database."""

    from pace.database.models import (
        Activity,
        ActivityPerformanceDetail,
        ContextEvent,
        DailyMetric,
        PerformanceEvidence,
        PerformanceSyncRun,
        Race,
        SyncRun,
    )
    from pace.database.session import SessionFactory

    with SessionFactory.begin() as session:
        for model in (
            PerformanceEvidence,
            ActivityPerformanceDetail,
            PerformanceSyncRun,
            Activity,
            DailyMetric,
            ContextEvent,
            Race,
            SyncRun,
        ):
            session.execute(delete(model))
