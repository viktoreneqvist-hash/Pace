"""Pure, deterministic calculations over normalized Pace activities."""

from datetime import date, timedelta

from pace.analysis.models import TrainingSummary, TrainingWindowSummary
from pace.database.models import Activity


WEEK_DAYS = 7


def _activities_in_window(
    activities: list[Activity],
    *,
    start_date: date,
    end_date: date,
) -> list[Activity]:
    return [
        activity
        for activity in activities
        if start_date <= activity.start_time.date() <= end_date
    ]


def _distance_km(activity: Activity) -> float:
    return (activity.distance_meters or 0) / 1000


def _percentage_change(current: float, previous: float) -> float | None:
    """Return percentage change only when the comparison window is non-zero."""

    if previous == 0:
        return None
    return (current - previous) / previous * 100


def summarize_training_window(
    activities: list[Activity],
    *,
    start_date: date,
    end_date: date,
) -> TrainingWindowSummary:
    """Calculate factual activity totals for one inclusive date window."""

    window_activities = _activities_in_window(
        activities,
        start_date=start_date,
        end_date=end_date,
    )
    runs = [activity for activity in window_activities if activity.sport_type == "run"]
    rides = [activity for activity in window_activities if activity.sport_type == "ride"]

    return TrainingWindowSummary(
        start_date=start_date,
        end_date=end_date,
        activity_count=len(window_activities),
        active_days=len({activity.start_time.date() for activity in window_activities}),
        running_distance_km=sum(_distance_km(activity) for activity in runs),
        cycling_duration_hours=sum(activity.duration_seconds for activity in rides) / 3600,
        total_duration_hours=sum(activity.duration_seconds for activity in window_activities)
        / 3600,
        longest_run_km=max(map(_distance_km, runs), default=None),
        longest_ride_km=max(map(_distance_km, rides), default=None),
    )


def summarize_weekly_training(
    activities: list[Activity],
    *,
    end_date: date,
) -> TrainingSummary:
    """Compare the current seven days with the preceding seven days."""

    current_start_date = end_date - timedelta(days=WEEK_DAYS - 1)
    previous_end_date = current_start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=WEEK_DAYS - 1)

    current = summarize_training_window(
        activities,
        start_date=current_start_date,
        end_date=end_date,
    )
    previous = summarize_training_window(
        activities,
        start_date=previous_start_date,
        end_date=previous_end_date,
    )

    return TrainingSummary(
        current=current,
        previous=previous,
        running_distance_change_percent=_percentage_change(
            current.running_distance_km,
            previous.running_distance_km,
        ),
        cycling_duration_change_percent=_percentage_change(
            current.cycling_duration_hours,
            previous.cycling_duration_hours,
        ),
    )
