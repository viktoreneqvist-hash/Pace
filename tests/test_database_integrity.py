"""Regression coverage for SQLite integrity boundaries used by Pace."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from pace.database.models import PlannedSession
from pace.database.session import session_scope


def test_sqlite_foreign_keys_reject_an_orphaned_planned_session():
    """The application engine must enforce the schema's foreign keys."""

    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.add(
                PlannedSession(
                    plan_id=99_999,
                    scheduled_date=date(2026, 7, 26),
                    sport_type="run",
                    purpose="Synthetic orphan.",
                    distance_meters=5_000,
                    duration_seconds=None,
                    intensity_type="rpe",
                    intensity_zone=None,
                    intensity_target="RPE 2–3",
                    heart_rate_zone=None,
                    target={
                        "kind": "rpe",
                        "rpe_min": 2,
                        "rpe_max": 3,
                        "pace_seconds_per_km": None,
                        "power_watts": None,
                        "evidence_reference_id": None,
                    },
                )
            )
            session.flush()
