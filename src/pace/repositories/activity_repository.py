from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import Activity


def get_activity_by_provider_id(
    session: Session,
    provider: str,
    provider_activity_id: str,
) -> Activity | None:
    """Find an activity by its provider-owned identifier."""

    statement = select(Activity).where(
        Activity.provider == provider,
        Activity.provider_activity_id == provider_activity_id,
    )
    return session.scalar(statement)


def upsert_activity(session: Session, activity: Activity) -> tuple[Activity, bool]:
    """Create or update an activity without creating a duplicate.

    Pace is a local, single-user application. A read-then-write upsert keeps the
    operation explicit while the unique database constraint remains the final
    protection against duplicate provider records.
    """

    existing = get_activity_by_provider_id(
        session,
        activity.provider,
        activity.provider_activity_id,
    )

    if existing is None:
        session.add(activity)
        session.flush()
        return activity, True

    for field_name in (
        "name",
        "sport_type",
        "start_time",
        "duration_seconds",
        "distance_meters",
        "elevation_gain_meters",
        "average_heart_rate",
        "maximum_heart_rate",
        "average_speed_mps",
        "average_cadence",
        "average_power",
        "training_effect_aerobic",
        "training_effect_anaerobic",
        "raw_payload",
    ):
        setattr(existing, field_name, getattr(activity, field_name))

    session.flush()
    return existing, False

    return activity


def get_all_activities(session: Session) -> list[Activity]:
    statement = select(Activity).order_by(Activity.start_time)
    activities = session.scalars(statement).all()

    return list(activities)


def get_activities_in_date_range(
    session: Session,
    *,
    start_date: date,
    end_date: date,
) -> list[Activity]:
    """Return activities whose local calendar date falls inside a range."""

    start_time = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_time = datetime.combine(end_date, time.max, tzinfo=UTC)
    statement = (
        select(Activity)
        .where(Activity.start_time >= start_time, Activity.start_time <= end_time)
        .order_by(Activity.start_time)
    )
    return list(session.scalars(statement).all())
