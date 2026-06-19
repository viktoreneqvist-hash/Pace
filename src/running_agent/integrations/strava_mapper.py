from datetime import date

from running_agent.models.activity import Activity


def map_strava_activity_to_activity(strava_activity: dict) -> Activity:
    return Activity(
        date=date.fromisoformat(strava_activity["start_date_local"][:10]),
        sport_type=strava_activity["sport_type"],
        distance_km=strava_activity["distance"] / 1000,
        duration_s=strava_activity["moving_time"],
        average_hr=strava_activity.get("average_heartrate"),
        max_hr=strava_activity.get("max_heartrate"),
        elevation_gain_m=strava_activity.get("total_elevation_gain"),
        source="strava",
        external_id=str(strava_activity["id"]),
    )   