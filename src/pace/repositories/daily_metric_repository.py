"""Persistence operations for daily recovery metrics."""

from collections.abc import Collection
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import DailyMetric


DAILY_METRIC_UPDATE_FIELDS = (
    "hrv_value",
    "hrv_status",
    "resting_heart_rate",
    "sleep_duration_seconds",
    "sleep_score",
    "average_stress",
    "body_battery_high",
    "body_battery_low",
    "training_readiness",
    "recovery_time_hours",
)

GARMIN_STATUS_FIELDS = (
    "training_readiness",
    "body_battery_high",
    "body_battery_low",
    "average_stress",
    "recovery_time_hours",
)


def get_daily_metric_by_date(session: Session, metric_date) -> DailyMetric | None:
    """Find a daily metric record for one calendar date."""

    return session.scalar(select(DailyMetric).where(DailyMetric.date == metric_date))


def upsert_daily_metric(
    session: Session,
    daily_metric: DailyMetric,
    *,
    fields_to_update: Collection[str] | None = None,
    raw_payload_keys_to_update: Collection[str] | None = None,
) -> tuple[DailyMetric, bool, bool]:
    """Create or update recovery metrics without erasing failed endpoints.

    ``fields_to_update`` and ``raw_payload_keys_to_update`` describe provider
    sources that completed successfully. Omitting them preserves the original
    full-replacement behavior for non-provider callers. The returned booleans
    mean ``created`` and ``changed`` respectively.
    """

    existing = get_daily_metric_by_date(session, daily_metric.date)

    if existing is None:
        session.add(daily_metric)
        session.flush()
        return daily_metric, True, False

    selected_fields = (
        DAILY_METRIC_UPDATE_FIELDS
        if fields_to_update is None
        else tuple(fields_to_update)
    )
    unknown_fields = set(selected_fields) - set(DAILY_METRIC_UPDATE_FIELDS)
    if unknown_fields:
        raise ValueError(f"Unknown daily metric fields: {sorted(unknown_fields)}")

    changed = False
    for field_name in selected_fields:
        incoming_value = getattr(daily_metric, field_name)
        if getattr(existing, field_name) != incoming_value:
            setattr(existing, field_name, incoming_value)
            changed = True

    if raw_payload_keys_to_update is None:
        merged_raw_payload = dict(daily_metric.raw_payload)
    else:
        merged_raw_payload = dict(existing.raw_payload)
        for payload_key in raw_payload_keys_to_update:
            if payload_key in daily_metric.raw_payload:
                merged_raw_payload[payload_key] = daily_metric.raw_payload[payload_key]
            else:
                merged_raw_payload.pop(payload_key, None)

    if existing.raw_payload != merged_raw_payload:
        existing.raw_payload = merged_raw_payload
        changed = True

    if changed:
        session.flush()

    return existing, False, changed


def get_daily_metrics_in_date_range(
    session: Session,
    *,
    start_date: date,
    end_date: date,
) -> list[DailyMetric]:
    """Return daily metrics in ascending calendar-date order."""

    statement = (
        select(DailyMetric)
        .where(DailyMetric.date >= start_date, DailyMetric.date <= end_date)
        .order_by(DailyMetric.date)
    )
    return list(session.scalars(statement).all())


def get_latest_daily_metric_with_value(
    session: Session,
    *,
    field_name: str,
    end_date: date,
) -> DailyMetric | None:
    """Return the latest record with one Garmin-owned status value by date."""

    if field_name not in GARMIN_STATUS_FIELDS:
        raise ValueError(f"Unsupported Garmin status field: {field_name}.")

    field = getattr(DailyMetric, field_name)
    statement = (
        select(DailyMetric)
        .where(DailyMetric.date <= end_date, field.is_not(None))
        .order_by(DailyMetric.date.desc(), DailyMetric.id.desc())
        .limit(1)
    )
    return session.scalar(statement)
