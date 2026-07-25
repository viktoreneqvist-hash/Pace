from datetime import UTC, datetime
from typing import Any

from pace.database.models import Activity


SPORT_TYPE_MAP = {
    "running": "run",
    "cycling": "ride",
    "road_biking": "ride",
    "mountain_biking": "ride",
    "nordic_skiing": "nordic_ski",
    "alpine_skiing": "alpine_ski",
    "strength_training": "strength",
    "rowing": "rowing",
}


def _parse_garmin_timestamp(value: str) -> datetime:
    """Parse a Garmin timestamp as an explicit UTC datetime."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def _value(payload: dict[str, Any], *keys: str) -> Any:
    """Return the first non-null value found under the supplied keys."""

    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value

    return None


def normalize_garmin_activity(garmin_activity: dict[str, Any]) -> Activity:
    """Convert a Garmin activity payload into Pace's internal activity model."""

    summary = garmin_activity.get("summaryDTO") or {}
    activity_type = garmin_activity.get("activityType") or {}
    provider_sport_type = _value(activity_type, "typeKey", "type") or "other"

    return Activity(
        provider="garmin",
        provider_activity_id=str(garmin_activity["activityId"]),
        name=garmin_activity.get("activityName"),
        sport_type=SPORT_TYPE_MAP.get(provider_sport_type, "other"),
        start_time=_parse_garmin_timestamp(garmin_activity["startTimeGMT"]),
        duration_seconds=int(_value(summary, "duration", "movingDuration") or 0),
        distance_meters=_value(summary, "distance"),
        elevation_gain_meters=_value(summary, "elevationGain", "elevationGainMeters"),
        average_heart_rate=_value(summary, "averageHR", "avgHR"),
        maximum_heart_rate=_value(summary, "maxHR", "maximumHR"),
        average_speed_mps=_value(summary, "averageSpeed", "avgSpeed"),
        average_cadence=_value(summary, "averageCadence", "avgCadence"),
        average_power=_value(summary, "averagePower", "avgPower"),
        training_effect_aerobic=_value(summary, "aerobicTrainingEffect"),
        training_effect_anaerobic=_value(summary, "anaerobicTrainingEffect"),
        raw_payload=garmin_activity,
    )
