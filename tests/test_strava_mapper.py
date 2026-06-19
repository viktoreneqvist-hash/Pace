from datetime import date

from running_agent.integrations.strava_mapper import map_strava_activity_to_activity


def test_map_strava_activity_to_activity():
    strava_activity = {
        "id": 123456789,
        "start_date_local": "2026-06-14T10:30:00Z",
        "sport_type": "Run",
        "distance": 10000.0,
        "moving_time": 3000,
        "average_heartrate": 150.0,
        "max_heartrate": 175.0,
        "total_elevation_gain": 120.0,
    }

    activity = map_strava_activity_to_activity(strava_activity)

    assert activity.date == date(2026, 6, 14)
    assert activity.sport_type == "Run"
    assert activity.distance_km == 10.0
    assert activity.duration_s == 3000
    assert activity.average_hr == 150.0
    assert activity.max_hr == 175.0
    assert activity.elevation_gain_m == 120.0
    assert activity.source == "strava"
    assert activity.external_id == "123456789"