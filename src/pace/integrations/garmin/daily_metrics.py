"""Normalize Garmin daily health payloads into Pace recovery metrics."""

from collections.abc import Collection
from datetime import date
from typing import Any

from pace.database.models import DailyMetric


SUMMARY_SOURCE = "summary"
SLEEP_SOURCE = "sleep"
HRV_SOURCE = "hrv"
TRAINING_READINESS_SOURCE = "training_readiness"

DAILY_METRIC_FIELDS_BY_SOURCE = {
    SUMMARY_SOURCE: frozenset(
        {
            "resting_heart_rate",
            "average_stress",
            "body_battery_high",
            "body_battery_low",
        }
    ),
    SLEEP_SOURCE: frozenset({"sleep_duration_seconds", "sleep_score"}),
    HRV_SOURCE: frozenset({"hrv_value", "hrv_status"}),
    TRAINING_READINESS_SOURCE: frozenset({"training_readiness", "recovery_time_hours"}),
}


def _require_optional_mapping(
    payload: dict[str, Any],
    key: str,
    *,
    source: str,
) -> dict[str, Any] | None:
    """Validate an optional nested object without requiring optional data."""

    value = payload.get(key)
    if value is not None and not isinstance(value, dict):
        raise ValueError(f"Garmin {source} payload has invalid {key}.")
    return value


def validate_garmin_daily_payload(source: str, payload: Any) -> None:
    """Reject malformed endpoint shapes before they can replace known facts."""

    if source not in DAILY_METRIC_FIELDS_BY_SOURCE:
        raise ValueError(f"Unknown Garmin daily source: {source}.")
    if source in {SUMMARY_SOURCE, SLEEP_SOURCE} and not isinstance(payload, dict):
        raise ValueError(f"Garmin {source} payload must be an object.")
    if source == HRV_SOURCE and payload is not None and not isinstance(payload, dict):
        raise ValueError("Garmin hrv payload must be an object or null.")
    if source == TRAINING_READINESS_SOURCE:
        if payload is not None and not isinstance(payload, (dict, list)):
            raise ValueError(
                "Garmin training_readiness payload must be an object, list, or null."
            )
        if isinstance(payload, list) and any(
            not isinstance(snapshot, dict) for snapshot in payload
        ):
            raise ValueError(
                "Garmin training_readiness payload contains an invalid snapshot."
            )

    if source == SLEEP_SOURCE and isinstance(payload, dict):
        daily_sleep = _require_optional_mapping(
            payload,
            "dailySleepDTO",
            source=source,
        )
        if daily_sleep is not None:
            sleep_scores = _require_optional_mapping(
                daily_sleep,
                "sleepScores",
                source=source,
            )
            if sleep_scores is not None:
                _require_optional_mapping(
                    sleep_scores,
                    "overall",
                    source=source,
                )

    if source == HRV_SOURCE and isinstance(payload, dict):
        _require_optional_mapping(payload, "hrvSummary", source=source)


def fields_for_successful_sources(sources: Collection[str]) -> frozenset[str]:
    """Return normalized fields owned by provider endpoints that succeeded."""

    return frozenset(
        field_name
        for source in sources
        for field_name in DAILY_METRIC_FIELDS_BY_SOURCE[source]
    )


def _nested_value(payload: dict[str, Any], *keys: str) -> Any:
    """Return a nested value, or ``None`` when any level is absent."""

    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _morning_readiness(
    readiness_payload: list[dict[str, Any]] | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Choose Garmin's wake-up readiness snapshot when it is available.

    That value represents the day's baseline before a new workout changes the
    recovery clock. If Garmin provides no wake-up context, its latest timestamp
    is the least surprising fallback.
    """

    if isinstance(readiness_payload, dict):
        return readiness_payload
    if not isinstance(readiness_payload, list) or not readiness_payload:
        return None

    wake_up_snapshot = next(
        (
            snapshot
            for snapshot in readiness_payload
            if snapshot.get("inputContext") == "AFTER_WAKEUP_RESET"
        ),
        None,
    )
    if wake_up_snapshot is not None:
        return wake_up_snapshot

    return max(readiness_payload, key=lambda snapshot: snapshot.get("timestamp") or "")


def normalize_garmin_daily_metric(
    *,
    metric_date: date,
    summary: dict[str, Any] | None,
    sleep: dict[str, Any] | None,
    hrv: dict[str, Any] | None,
    readiness: list[dict[str, Any]] | dict[str, Any] | None,
) -> DailyMetric:
    """Build one normalized metric record from Garmin's daily endpoints."""

    summary = summary or {}
    sleep = sleep or {}
    hrv = hrv or {}
    readiness_snapshot = _morning_readiness(readiness)

    recovery_time_minutes = (
        readiness_snapshot.get("recoveryTime") if readiness_snapshot else None
    )
    recovery_time_hours = (
        0.0
        if readiness_snapshot
        and readiness_snapshot.get("recoveryTimeChangePhrase") == "REACHED_ZERO"
        else recovery_time_minutes / 60
        if recovery_time_minutes is not None
        else None
    )

    raw_payload = {
        name: payload
        for name, payload in {
            SUMMARY_SOURCE: summary,
            SLEEP_SOURCE: sleep,
            HRV_SOURCE: hrv,
            TRAINING_READINESS_SOURCE: readiness,
        }.items()
        if payload
    }

    return DailyMetric(
        date=metric_date,
        hrv_value=_nested_value(hrv, "hrvSummary", "lastNightAvg"),
        hrv_status=_nested_value(hrv, "hrvSummary", "status"),
        resting_heart_rate=summary.get("restingHeartRate"),
        sleep_duration_seconds=_nested_value(
            sleep,
            "dailySleepDTO",
            "sleepTimeSeconds",
        ),
        sleep_score=_nested_value(
            sleep, "dailySleepDTO", "sleepScores", "overall", "value"
        ),
        average_stress=summary.get("averageStressLevel"),
        body_battery_high=summary.get("bodyBatteryHighestValue"),
        body_battery_low=summary.get("bodyBatteryLowestValue"),
        training_readiness=readiness_snapshot.get("score")
        if readiness_snapshot
        else None,
        recovery_time_hours=recovery_time_hours,
        raw_payload=raw_payload,
    )
