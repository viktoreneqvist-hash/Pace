from datetime import UTC, datetime
from typing import Any

from pace.database.models import Activity


RUN_TYPE_KEYS = frozenset(
    {
        "running",
        "run",
        "street_running",
        "trail_running",
        "trail_run",
        "treadmill_running",
        "treadmill",
        "track_running",
        "track_run",
        "indoor_running",
        "indoor_track_running",
        "virtual_running",
        "virtual_run",
        "ultra_run",
        "obstacle_run",
        "obstacle_racing",
    }
)

RIDE_TYPE_KEYS = frozenset(
    {
        "cycling",
        "bike",
        "road_biking",
        "road_bike",
        "mountain_biking",
        "mountain_bike",
        "indoor_cycling",
        "bike_indoor",
        "gravel_cycling",
        "gravel_bike",
        "cyclocross",
        "bmx",
        "virtual_ride",
        "bike_commute",
        "bike_tour",
        "recumbent_cycling",
        "hand_cycling",
        "downhill_biking",
        "enduro_mtb",
        "e_biking",
        "ebike",
        "e_bike_fitness",
        "e_bike_mountain",
        "e_mountain_biking",
        "emtb",
    }
)


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


def _activity_value(
    summary: dict[str, Any],
    activity: dict[str, Any],
    *keys: str,
) -> Any:
    """Prefer a detailed summary value, then fall back to the list payload."""

    summary_value = _value(summary, *keys)
    return summary_value if summary_value is not None else _value(activity, *keys)


def _normalize_sport_type(provider_sport_type: Any) -> str:
    """Collapse only recognized running and cycling profiles into Pace facts."""

    if not isinstance(provider_sport_type, str):
        return "other"

    normalized_key = provider_sport_type.strip().lower()
    if normalized_key in RUN_TYPE_KEYS:
        return "run"
    if normalized_key in RIDE_TYPE_KEYS:
        return "ride"
    return "other"


def normalize_garmin_activity(garmin_activity: dict[str, Any]) -> Activity:
    """Convert a Garmin activity payload into Pace's internal activity model."""

    # Garmin's activity-list endpoint returns summary fields at the top level.
    # Some older or detailed payloads nest the same fields under ``summaryDTO``.
    # Supporting both shapes keeps Pace's normalized contract stable.
    summary = garmin_activity.get("summaryDTO")
    if not isinstance(summary, dict):
        summary = {}

    activity_type = garmin_activity.get("activityType")
    provider_sport_type = (
        _value(activity_type, "typeKey", "type")
        if isinstance(activity_type, dict)
        else activity_type
    )

    provider_activity_id = garmin_activity.get("activityId")
    if provider_activity_id is None or not str(provider_activity_id).strip():
        raise ValueError("Garmin activity is missing activityId.")

    start_time = garmin_activity.get("startTimeGMT")
    if not isinstance(start_time, str) or not start_time.strip():
        raise ValueError("Garmin activity is missing startTimeGMT.")

    duration = _activity_value(summary, garmin_activity, "duration", "movingDuration")
    if duration is None:
        raise ValueError("Garmin activity is missing duration.")

    duration_seconds = int(duration)
    if duration_seconds < 0:
        raise ValueError("Garmin activity duration cannot be negative.")

    return Activity(
        provider="garmin",
        provider_activity_id=str(provider_activity_id),
        name=garmin_activity.get("activityName"),
        sport_type=_normalize_sport_type(provider_sport_type),
        start_time=_parse_garmin_timestamp(start_time),
        duration_seconds=duration_seconds,
        distance_meters=_activity_value(summary, garmin_activity, "distance"),
        elevation_gain_meters=_activity_value(
            summary,
            garmin_activity,
            "elevationGain",
            "elevationGainMeters",
        ),
        average_heart_rate=_activity_value(
            summary,
            garmin_activity,
            "averageHR",
            "avgHR",
        ),
        maximum_heart_rate=_activity_value(
            summary,
            garmin_activity,
            "maxHR",
            "maximumHR",
        ),
        average_speed_mps=_activity_value(
            summary,
            garmin_activity,
            "averageSpeed",
            "avgSpeed",
        ),
        average_cadence=_activity_value(
            summary,
            garmin_activity,
            "averageCadence",
            "avgCadence",
        ),
        average_power=_activity_value(
            summary,
            garmin_activity,
            "averagePower",
            "avgPower",
        ),
        training_effect_aerobic=_activity_value(
            summary,
            garmin_activity,
            "aerobicTrainingEffect",
        ),
        training_effect_anaerobic=_activity_value(
            summary,
            garmin_activity,
            "anaerobicTrainingEffect",
        ),
        raw_payload=garmin_activity,
    )
