"""Pure calculations over normalized Pace activity history."""

from datetime import date, timedelta

from pace.capacity.models import ContinuityFact, SportBalanceFact, SportCapacityFact
from pace.database.models import Activity
from pace.timezones import athlete_local_date


INCLUDED_SPORT_TYPES = ("run", "ride")


def summarize_sport_capacity(
    activities: list[Activity],
    *,
    sport_type: str,
    start_date: date,
    end_date: date,
) -> SportCapacityFact:
    """Summarize one sport without turning absent distance into zero."""

    selected = [
        activity
        for activity in activities
        if activity.sport_type == sport_type
        and start_date <= athlete_local_date(activity.start_time) <= end_date
    ]
    distances_complete = all(activity.distance_meters is not None for activity in selected)
    return SportCapacityFact(
        sport_type=sport_type,
        activity_count=len(selected),
        active_days=len({athlete_local_date(activity.start_time) for activity in selected}),
        total_duration_hours=sum(activity.duration_seconds for activity in selected) / 3600,
        total_distance_km=(
            sum(activity.distance_meters or 0 for activity in selected) / 1000
            if distances_complete
            else None
        ),
        longest_duration_hours=(
            None
            if not selected
            else max(activity.duration_seconds for activity in selected) / 3600
        ),
        longest_distance_km=(
            None
            if not selected or not distances_complete
            else max(activity.distance_meters or 0 for activity in selected) / 1000
        ),
    )


def summarize_continuity(
    activities: list[Activity],
    *,
    start_date: date,
    end_date: date,
) -> ContinuityFact:
    """Count active windows and inactive calendar streaks for included sports."""

    active_dates = {
        athlete_local_date(activity.start_time)
        for activity in activities
        if activity.sport_type in INCLUDED_SPORT_TYPES
        and start_date <= athlete_local_date(activity.start_time) <= end_date
    }
    calendar_days = (end_date - start_date).days + 1
    expected_weeks = (calendar_days + 6) // 7
    weeks_with_activity = sum(
        any(
            start_date + timedelta(days=offset) in active_dates
            for offset in range(week_start, min(week_start + 7, calendar_days))
        )
        for week_start in range(0, calendar_days, 7)
    )
    return ContinuityFact(
        calendar_days=calendar_days,
        active_days=len(active_dates),
        expected_weeks=expected_weeks,
        weeks_with_activity=weeks_with_activity,
        weeks_without_activity=expected_weeks - weeks_with_activity,
        longest_inactive_streak_days=_longest_inactive_streak(
            start_date=start_date,
            end_date=end_date,
            active_dates=active_dates,
        ),
    )


def summarize_sport_balance(
    sports: tuple[SportCapacityFact, ...],
) -> SportBalanceFact:
    """Return the observed duration split without comparing incompatible distances."""

    by_sport = {fact.sport_type: fact for fact in sports}
    running_hours = by_sport["run"].total_duration_hours
    cycling_hours = by_sport["ride"].total_duration_hours
    total_hours = running_hours + cycling_hours
    return SportBalanceFact(
        total_duration_hours=total_hours,
        running_duration_share_percent=(
            None if total_hours == 0 else running_hours / total_hours * 100
        ),
        cycling_duration_share_percent=(
            None if total_hours == 0 else cycling_hours / total_hours * 100
        ),
    )


def _longest_inactive_streak(
    *,
    start_date: date,
    end_date: date,
    active_dates: set[date],
) -> int:
    longest_streak = 0
    current_streak = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date in active_dates:
            current_streak = 0
        else:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        current_date += timedelta(days=1)
    return longest_streak
