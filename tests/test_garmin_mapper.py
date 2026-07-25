import json
from datetime import UTC, datetime
from pathlib import Path

from pace.integrations.garmin.normalizers import normalize_garmin_activity


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "garmin"


def test_normalize_garmin_activity():
    garmin_activity = json.loads(
        (FIXTURES_PATH / "running_activity.json").read_text(encoding="utf-8")
    )

    activity = normalize_garmin_activity(garmin_activity)

    assert activity.start_time == datetime(2026, 6, 14, 5, 30, tzinfo=UTC)
    assert activity.sport_type == "run"
    assert activity.distance_meters == 10_000
    assert activity.duration_seconds == 3000
    assert activity.average_heart_rate == 150
    assert activity.provider == "garmin"
    assert activity.provider_activity_id == "mock-garmin-1"
