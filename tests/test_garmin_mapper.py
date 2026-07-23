from datetime import date

from pace.integrations.garmin.normalizers import normalize_garmin_activity


def test_normalize_garmin_activity():
    garmin_activity = {
        "date": "2026-06-14",
        "sport_type": "running",
        "distance_m": 10000,
        "duration_s": 3000,
        "average_hr": 150,
        "max_hr": 175,
        "elevation_gain_m": 120.0,
        "external_id": "garmin-activity-1",
    }

    activity = normalize_garmin_activity(garmin_activity)

    assert activity.date == date(2026, 6, 14)
    assert activity.sport_type == "running"
    assert activity.distance_km == 10.0
    assert activity.duration_s == 3000
    assert activity.average_hr == 150
    assert activity.source == "garmin"
    assert activity.external_id == "garmin-activity-1"
