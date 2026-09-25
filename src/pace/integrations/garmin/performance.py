"""Normalize only the Garmin activity-detail facts Pace is allowed to retain."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GarminPerformanceDetail:
    """Provider-neutral scalar detail fields and normalized split summaries."""

    duration_seconds: int | None
    distance_meters: float | None
    average_heart_rate: int | None
    maximum_heart_rate: int | None
    average_speed_mps: float | None
    average_cadence: float | None
    average_power: float | None
    splits: list[dict[str, int | float | None]]
    heart_rate_zones: list[dict[str, int | float]] | None


def _value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Garmin performance detail has invalid {label}.") from error
    if normalized < 0:
        raise ValueError(f"Garmin performance detail has negative {label}.")
    return normalized


def _optional_float(value: Any, label: str) -> float | None:
    if value is None:
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Garmin performance detail has invalid {label}.") from error
    if normalized < 0:
        raise ValueError(f"Garmin performance detail has negative {label}.")
    return normalized


def _detail_summary(detail_payload: dict[str, Any]) -> dict[str, Any]:
    summary = detail_payload.get("activityDetailDTO")
    if summary is None:
        return detail_payload
    if not isinstance(summary, dict):
        raise ValueError("Garmin performance detail has invalid activityDetailDTO.")
    return summary


def _split_items(splits_payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("lapDTOs", "splits", "lapSummaries"):
        splits = splits_payload.get(key)
        if splits is not None:
            if not isinstance(splits, list) or not all(
                isinstance(item, dict) for item in splits
            ):
                raise ValueError("Garmin performance splits have invalid lap entries.")
            return splits
    raise ValueError("Garmin performance splits are missing lap entries.")


def _normalize_splits(splits_payload: dict[str, Any]) -> list[dict[str, int | float | None]]:
    if not isinstance(splits_payload, dict):
        raise ValueError("Garmin performance splits must be an object.")

    normalized_splits: list[dict[str, int | float | None]] = []
    for position, split in enumerate(_split_items(splits_payload), start=1):
        # Deliberately retain only numeric split summaries. Coordinates, chart
        # samples, polyline data, and every unknown provider field are dropped.
        normalized_splits.append(
            {
                "split_number": position,
                "duration_seconds": _optional_int(
                    _value(split, "duration", "movingDuration"), "split duration"
                ),
                "distance_meters": _optional_float(
                    _value(split, "distance"), "split distance"
                ),
                "average_heart_rate": _optional_int(
                    _value(split, "averageHR", "avgHR"), "split average heart rate"
                ),
                "average_speed_mps": _optional_float(
                    _value(split, "averageSpeed", "avgSpeed"), "split average speed"
                ),
                "average_cadence": _optional_float(
                    _value(split, "averageCadence", "avgCadence"), "split average cadence"
                ),
                "average_power": _optional_float(
                    _value(split, "averagePower", "avgPower"), "split average power"
                ),
            }
        )
    return normalized_splits


def normalize_garmin_heart_rate_zones(
    payload: dict[str, Any] | list[dict[str, Any]],
) -> list[dict[str, int | float]]:
    """Normalize Garmin time-in-zone data without retaining provider payloads."""

    seconds_by_zone: dict[int, float] = {}
    if isinstance(payload, dict):
        for zone in range(1, 6):
            value = _value(payload, f"zone{zone}", f"zone_{zone}")
            if value is not None:
                seconds_by_zone[zone] = _optional_float(
                    value, f"heart-rate zone {zone} seconds"
                ) or 0.0
        if not seconds_by_zone:
            nested = _value(payload, "heartRateZones", "timeInZones", "zones")
            if nested is not None:
                payload = nested

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("Garmin heart-rate zones have invalid entries.")
            zone = _optional_int(
                _value(item, "zone", "zoneNumber", "zoneIndex"), "heart-rate zone"
            )
            seconds = _optional_float(
                _value(item, "seconds", "secsInZone", "timeInZone"),
                "heart-rate zone seconds",
            )
            if zone is not None and seconds is not None and 1 <= zone <= 5:
                seconds_by_zone[zone] = seconds

    if not seconds_by_zone:
        raise ValueError("Garmin heart-rate zones are missing zone durations.")

    total_seconds = sum(seconds_by_zone.values())
    return [
        {
            "zone": zone,
            "seconds": round(seconds),
            "percent": 0.0
            if total_seconds <= 0
            else round(seconds / total_seconds * 100, 1),
        }
        for zone, seconds in sorted(seconds_by_zone.items())
    ]


def normalize_garmin_performance_detail(
    detail_payload: dict[str, Any],
    splits_payload: dict[str, Any],
    heart_rate_zones_payload: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> GarminPerformanceDetail:
    """Create Pace's minimal detail contract without retaining provider payloads."""

    if not isinstance(detail_payload, dict):
        raise ValueError("Garmin performance detail must be an object.")
    summary = _detail_summary(detail_payload)
    return GarminPerformanceDetail(
        duration_seconds=_optional_int(
            _value(summary, "duration", "movingDuration"), "duration"
        ),
        distance_meters=_optional_float(_value(summary, "distance"), "distance"),
        average_heart_rate=_optional_int(
            _value(summary, "averageHR", "avgHR"), "average heart rate"
        ),
        maximum_heart_rate=_optional_int(
            _value(summary, "maxHR", "maximumHR"), "maximum heart rate"
        ),
        average_speed_mps=_optional_float(
            _value(summary, "averageSpeed", "avgSpeed"), "average speed"
        ),
        average_cadence=_optional_float(
            _value(summary, "averageCadence", "avgCadence"), "average cadence"
        ),
        average_power=_optional_float(
            _value(summary, "averagePower", "avgPower"), "average power"
        ),
        splits=_normalize_splits(splits_payload),
        heart_rate_zones=(
            None
            if heart_rate_zones_payload is None
            else normalize_garmin_heart_rate_zones(heart_rate_zones_payload)
        ),
    )
