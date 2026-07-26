from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import Activity
from pace.timezones import as_utc, utc_bounds_for_athlete_dates


ACTIVITY_UPDATE_FIELDS = (
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
)


def _activity_field_changed(
    existing: Activity,
    incoming: Activity,
    field_name: str,
) -> bool:
    """Compare persisted values using Pace's normalized storage semantics."""

    existing_value = getattr(existing, field_name)
    incoming_value = getattr(incoming, field_name)
    if field_name == "start_time":
        return as_utc(existing_value) != as_utc(incoming_value)
    return existing_value != incoming_value


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


def upsert_activity(
    session: Session, activity: Activity
) -> tuple[Activity, bool, bool]:
    """Create or update an activity without creating a duplicate.

    Pace is a local, single-user application. A read-then-write upsert keeps the
    operation explicit while the unique database constraint remains the final
    protection against duplicate provider records. The returned booleans mean
    ``created`` and ``changed`` respectively.
    """

    existing = get_activity_by_provider_id(
        session,
        activity.provider,
        activity.provider_activity_id,
    )

    if existing is None:
        session.add(activity)
        session.flush()
        return activity, True, False

    changed = any(
        _activity_field_changed(existing, activity, field_name)
        for field_name in ACTIVITY_UPDATE_FIELDS
    )

    if changed:
        for field_name in ACTIVITY_UPDATE_FIELDS:
            setattr(existing, field_name, getattr(activity, field_name))
        session.flush()

    return existing, False, changed


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
    """Return activities whose athlete-local calendar date is in the range."""

    start_time, end_time = utc_bounds_for_athlete_dates(start_date, end_date)
    statement = (
        select(Activity)
        .where(Activity.start_time >= start_time, Activity.start_time < end_time)
        .order_by(Activity.start_time)
    )
    return list(session.scalars(statement).all())
