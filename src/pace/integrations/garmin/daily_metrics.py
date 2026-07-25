"""Normalize Garmin daily health payloads into Pace recovery metrics."""

from datetime import date
from typing import Any

from pace.database.models import DailyMetric


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
            "summary": summary,
            "sleep": sleep,
            "hrv": hrv,
            "training_readiness": readiness,
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
        sleep_score=_nested_value(sleep, "dailySleepDTO", "sleepScores", "overall", "value"),
        average_stress=summary.get("averageStressLevel"),
        body_battery_high=summary.get("bodyBatteryHighestValue"),
        body_battery_low=summary.get("bodyBatteryLowestValue"),
        training_readiness=readiness_snapshot.get("score") if readiness_snapshot else None,
        recovery_time_hours=recovery_time_hours,
        raw_payload=raw_payload,
    )
