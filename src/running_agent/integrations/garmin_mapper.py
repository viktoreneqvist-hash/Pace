from datetime import date

from running_agent.models.activity import Activity


def map_garmin_activity_to_activity(garmin_activity: dict) -> Activity:
    return Activity(
        date=date.fromisoformat(garmin_activity["date"]),
        sport_type=garmin_activity["sport_type"],
        distance_km=garmin_activity["distance_m"] / 1000,
        duration_s=garmin_activity["duration_s"],
        average_hr=garmin_activity.get("average_hr"),
        max_hr=garmin_activity.get("max_hr"),
        elevation_gain_m=garmin_activity.get("elevation_gain_m"),
        source="garmin",
        external_id=garmin_activity.get("external_id"),
    ) 