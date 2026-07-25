"""Persistence operations for daily recovery metrics."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import DailyMetric


def get_daily_metric_by_date(session: Session, metric_date) -> DailyMetric | None:
    """Find a daily metric record for one calendar date."""

    return session.scalar(select(DailyMetric).where(DailyMetric.date == metric_date))


def upsert_daily_metric(
    session: Session,
    daily_metric: DailyMetric,
) -> tuple[DailyMetric, bool]:
    """Create or update the recovery metrics for one calendar day."""

    existing = get_daily_metric_by_date(session, daily_metric.date)

    if existing is None:
        session.add(daily_metric)
        session.flush()
        return daily_metric, True

    for field_name in (
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
        "raw_payload",
    ):
        setattr(existing, field_name, getattr(daily_metric, field_name))

    session.flush()
    return existing, False
