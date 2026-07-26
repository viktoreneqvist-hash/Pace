"""Calendar-day helpers for Pace's single athlete timezone."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pace.config.settings import settings


ATHLETE_TIMEZONE = ZoneInfo(settings.athlete_timezone)


def as_utc(value: datetime) -> datetime:
    """Return an explicit UTC datetime.

    SQLite may return a stored UTC timestamp without ``tzinfo``. Pace treats
    such values as UTC because Garmin normalization converts them before write.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def athlete_local_date(value: datetime) -> date:
    """Return the activity date in Pace's fixed athlete timezone."""

    return as_utc(value).astimezone(ATHLETE_TIMEZONE).date()


def utc_bounds_for_athlete_dates(
    start_date: date,
    end_date: date,
) -> tuple[datetime, datetime]:
    """Return inclusive-start/exclusive-end UTC bounds for local dates."""

    if end_date < start_date:
        raise ValueError("end_date cannot be earlier than start_date.")

    local_start = datetime.combine(start_date, time.min, tzinfo=ATHLETE_TIMEZONE)
    local_end = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=ATHLETE_TIMEZONE,
    )
    return local_start.astimezone(UTC), local_end.astimezone(UTC)
