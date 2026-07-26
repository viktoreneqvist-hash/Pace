import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

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


def test_normalize_activity_list_payload_with_top_level_summary_fields():
    activity = normalize_garmin_activity(
        {
            "activityId": 123,
            "activityName": "Bike ride",
            "startTimeGMT": "2026-06-14T05:30:00.0",
            "activityType": {"typeKey": "cycling"},
            "duration": 3600,
            "distance": 25_000,
            "elevationGain": 250,
            "averageHR": 140,
            "maxHR": 165,
            "averageSpeed": 6.94,
        }
    )

    assert activity.sport_type == "ride"
    assert activity.duration_seconds == 3600
    assert activity.distance_meters == 25_000
    assert activity.elevation_gain_meters == 250
    assert activity.average_heart_rate == 140
    assert activity.maximum_heart_rate == 165


@pytest.mark.parametrize(
    ("provider_type", "expected_type"),
    [
        ("trail_running", "run"),
        ("treadmill_running", "run"),
        ("virtual_running", "run"),
        ("indoor_cycling", "ride"),
        ("gravel_cycling", "ride"),
        ("e_bike_mountain", "ride"),
        ("strength_training", "other"),
    ],
)
def test_normalize_activity_profiles_into_strict_sport_families(
    provider_type: str,
    expected_type: str,
):
    activity = normalize_garmin_activity(
        {
            "activityId": provider_type,
            "startTimeGMT": "2026-06-14T05:30:00Z",
            "activityType": {"typeKey": provider_type},
            "duration": 3600,
            "distance": 10_000,
        }
    )

    assert activity.sport_type == expected_type


def test_top_level_fields_fill_a_partial_summary_payload():
    activity = normalize_garmin_activity(
        {
            "activityId": 123,
            "startTimeGMT": "2026-06-14T05:30:00Z",
            "activityType": {"typeKey": "running"},
            "duration": 3600,
            "distance": 10_000,
            "summaryDTO": {"averageHR": 140},
        }
    )

    assert activity.duration_seconds == 3600
    assert activity.distance_meters == 10_000
    assert activity.average_heart_rate == 140


def test_missing_activity_duration_is_rejected_instead_of_invented_as_zero():
    with pytest.raises(ValueError, match="missing duration"):
        normalize_garmin_activity(
            {
                "activityId": 123,
                "startTimeGMT": "2026-06-14T05:30:00Z",
                "activityType": {"typeKey": "running"},
            }
        )
