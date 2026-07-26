from datetime import UTC, date, datetime, timedelta

from pace.timezones import utc_bounds_for_athlete_dates


def test_stockholm_winter_day_uses_utc_plus_one():
    start, end = utc_bounds_for_athlete_dates(
        date(2026, 1, 15),
        date(2026, 1, 15),
    )

    assert start == datetime(2026, 1, 14, 23, tzinfo=UTC)
    assert end == datetime(2026, 1, 15, 23, tzinfo=UTC)


def test_stockholm_dst_days_use_real_calendar_midnights():
    spring_start, spring_end = utc_bounds_for_athlete_dates(
        date(2026, 3, 29),
        date(2026, 3, 29),
    )
    autumn_start, autumn_end = utc_bounds_for_athlete_dates(
        date(2026, 10, 25),
        date(2026, 10, 25),
    )

    assert spring_end - spring_start == timedelta(hours=23)
    assert autumn_end - autumn_start == timedelta(hours=25)
