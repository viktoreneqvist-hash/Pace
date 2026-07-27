from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from pace.services.transparent_training_analysis_service import _sport_analysis


def _activity(
    *,
    start_time: datetime,
    duration_seconds: float,
    distance_meters: float | None,
):
    return SimpleNamespace(
        start_time=start_time,
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
    )


def test_sport_analysis_keeps_missing_distance_separate_from_known_distance():
    activities = (
        _activity(
            start_time=datetime(2026, 7, 25, 8, tzinfo=timezone.utc),
            duration_seconds=3_600,
            distance_meters=30_000,
        ),
        _activity(
            start_time=datetime(2026, 7, 26, 8, tzinfo=timezone.utc),
            duration_seconds=1_800,
            distance_meters=None,
        ),
    )

    result = _sport_analysis("ride", activities)

    assert result.activity_count == 2
    assert result.active_days == 2
    assert result.duration_hours == pytest.approx(1.5)
    assert result.known_distance_km == pytest.approx(30)
    assert result.missing_distance_activities == 1
