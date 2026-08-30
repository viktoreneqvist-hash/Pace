"""Build a bounded, privacy-minimized training history for explicit coach calls."""

from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Any

from pace.database.session import session_scope
from pace.repositories.activity_repository import get_activities_in_date_range
from pace.repositories.context_event_repository import get_context_events_in_date_range
from pace.repositories.daily_metric_repository import get_daily_metrics_in_date_range
from pace.repositories.training_plan_repository import list_feedback_trend_records
from pace.timezones import athlete_local_date


RECENT_ACTIVITY_DAYS = 3
DAILY_HISTORY_DAYS = 28
WEEKLY_HISTORY_DAYS = 84
WEEKLY_WINDOW_DAYS = 7
ESTABLISHED_BASELINE_WEEKS = 6
RECENT_BASELINE_EXCLUDED_WEEKS = 2
INCLUDED_SPORTS = ("run", "ride")


class CoachTrainingHistoryService:
    """Expose selected normalized facts, never Garmin payloads or note text."""

    def get_history(self, *, end_date: date) -> dict[str, object]:
        """Return 3/28/84-day facts for one explicit coach interaction."""

        weekly_start = end_date - timedelta(days=WEEKLY_HISTORY_DAYS - 1)
        daily_start = end_date - timedelta(days=DAILY_HISTORY_DAYS - 1)
        recent_start = end_date - timedelta(days=RECENT_ACTIVITY_DAYS - 1)
        with session_scope() as session:
            activities = tuple(
                activity
                for activity in get_activities_in_date_range(
                    session, start_date=weekly_start, end_date=end_date
                )
                if activity.sport_type in INCLUDED_SPORTS
            )
            daily_metrics = get_daily_metrics_in_date_range(
                session, start_date=daily_start, end_date=end_date
            )
            feedback = list_feedback_trend_records(
                session, start_date=daily_start, end_date=end_date
            )
            context_events = get_context_events_in_date_range(
                session, start_date=daily_start, end_date=end_date
            )

        return build_coach_training_history(
            end_date=end_date,
            activities=activities,
            daily_metrics=daily_metrics,
            feedback=feedback,
            context_events=context_events,
            recent_start=recent_start,
            daily_start=daily_start,
            weekly_start=weekly_start,
        )


def build_coach_training_history(
    *,
    end_date: date,
    activities,
    daily_metrics,
    feedback,
    context_events,
    recent_start: date | None = None,
    daily_start: date | None = None,
    weekly_start: date | None = None,
) -> dict[str, object]:
    """Create an inspectable model input from already-normalized local records."""

    recent_start = recent_start or end_date - timedelta(days=RECENT_ACTIVITY_DAYS - 1)
    daily_start = daily_start or end_date - timedelta(days=DAILY_HISTORY_DAYS - 1)
    weekly_start = weekly_start or end_date - timedelta(days=WEEKLY_HISTORY_DAYS - 1)
    activity_by_date: dict[date, list[Any]] = defaultdict(list)
    for activity in activities:
        activity_by_date[athlete_local_date(activity.start_time)].append(activity)
    metric_by_date = {metric.date: metric for metric in daily_metrics}
    feedback_by_date: dict[date, list[Any]] = defaultdict(list)
    for item in feedback:
        feedback_by_date[item.scheduled_date].append(item)
    context_by_date: dict[date, list[Any]] = defaultdict(list)
    for event in context_events:
        overlap_start = max(event.start_date, daily_start)
        overlap_end = min(event.end_date or end_date, end_date)
        for offset in range((overlap_end - overlap_start).days + 1):
            context_by_date[overlap_start + timedelta(days=offset)].append(event)

    recent_activities = [
        _detailed_activity(activity)
        for day in _date_range(recent_start, end_date)
        for activity in activity_by_date[day]
    ]
    daily_history = [
        _daily_fact(
            target_date=day,
            activities=activity_by_date[day],
            metric=metric_by_date.get(day),
            feedback=feedback_by_date[day],
            context_events=context_by_date[day],
        )
        for day in _date_range(daily_start, end_date)
    ]
    weekly_history = [
        _weekly_fact(
            start_date=window_end - timedelta(days=WEEKLY_WINDOW_DAYS - 1),
            end_date=window_end,
            activities=[
                activity
                for day in _date_range(
                    window_end - timedelta(days=WEEKLY_WINDOW_DAYS - 1), window_end
                )
                for activity in activity_by_date[day]
            ],
            feedback=[
                item
                for day in _date_range(
                    window_end - timedelta(days=WEEKLY_WINDOW_DAYS - 1), window_end
                )
                for item in feedback_by_date[day]
            ],
        )
        for window_end in _rolling_week_end_dates(end_date)
    ]
    return {
        "recent_detailed_activities": recent_activities,
        "daily_history": daily_history,
        "weekly_history": weekly_history,
        "limits": {
            "recent_activity_days": RECENT_ACTIVITY_DAYS,
            "daily_history_days": DAILY_HISTORY_DAYS,
            "weekly_history_days": WEEKLY_HISTORY_DAYS,
            "raw_garmin_payloads_included": False,
            "private_note_text_included": False,
            "historical_garmin_statuses_included": False,
        },
    }


def build_planning_continuity_facts(
    history: dict[str, object],
) -> dict[str, object]:
    """Select chronological training facts for an explicit plan decision.

    The plan model needs the shape of recent training, not only an aggregate
    capacity total. Keep this deliberately narrower than the coach-dialogue
    history: recovery, feedback, context, private notes, and detailed activity
    fields already have dedicated planning facts elsewhere in the catalog.
    """

    daily_history = history.get("daily_history")
    weekly_history = history.get("weekly_history")
    limits = history.get("limits")
    daily_training = (
        [
            {
                "date": item["date"],
                "training": item["training"],
            }
            for item in daily_history
            if isinstance(item, dict)
            and isinstance(item.get("date"), str)
            and isinstance(item.get("training"), dict)
        ]
        if isinstance(daily_history, list)
        else []
    )
    weekly_training = (
        [
            {
                "start_date": item["start_date"],
                "end_date": item["end_date"],
                "training": item["training"],
                "active_days": item["active_days"],
            }
            for item in weekly_history
            if isinstance(item, dict)
            and isinstance(item.get("start_date"), str)
            and isinstance(item.get("end_date"), str)
            and isinstance(item.get("training"), dict)
            and isinstance(item.get("active_days"), int)
        ]
        if isinstance(weekly_history, list)
        else []
    )
    return {
        "daily_training": daily_training,
        "recent_windows": _recent_training_windows(daily_training),
        "weekly_training": weekly_training,
        "established_baseline": _established_training_baseline(weekly_training),
        "limits": {
            "daily_training_days": (
                limits.get("daily_history_days") if isinstance(limits, dict) else None
            ),
            "weekly_training_days": (
                limits.get("weekly_history_days") if isinstance(limits, dict) else None
            ),
            "weekly_window_days": WEEKLY_WINDOW_DAYS,
            "raw_garmin_payloads_included": False,
            "private_note_text_included": False,
        },
    }


def _recent_training_windows(
    daily_training: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Calculate short current windows so the model never totals daily rows."""

    return [
        _summarize_daily_training_window(daily_training[-days:], expected_days=days)
        for days in (7, 14)
    ]


def _established_training_baseline(
    weekly_training: list[dict[str, object]],
) -> dict[str, object]:
    """Describe prior repeated training without converting it into a plan cap."""

    baseline_weeks = weekly_training[
        -(ESTABLISHED_BASELINE_WEEKS + RECENT_BASELINE_EXCLUDED_WEEKS) : -RECENT_BASELINE_EXCLUDED_WEEKS
    ]
    return {
        "excluded_most_recent_days": RECENT_BASELINE_EXCLUDED_WEEKS
        * WEEKLY_WINDOW_DAYS,
        "calendar_weeks": len(baseline_weeks),
        "start_date": baseline_weeks[0]["start_date"] if baseline_weeks else None,
        "end_date": baseline_weeks[-1]["end_date"] if baseline_weeks else None,
        "sports": {
            sport_type: _summarize_established_sport(
                baseline_weeks, sport_type=sport_type
            )
            for sport_type in INCLUDED_SPORTS
        },
    }


def _summarize_established_sport(
    weekly_training: list[dict[str, object]], *, sport_type: str
) -> dict[str, object]:
    activity_counts: list[int] = []
    durations: list[int] = []
    active_days: list[int] = []
    for week in weekly_training:
        summaries = week.get("training")
        summary = summaries.get(sport_type) if isinstance(summaries, dict) else None
        activity_count = _nonnegative_int(
            summary.get("activity_count") if isinstance(summary, dict) else None
        )
        activity_counts.append(activity_count)
        durations.append(
            _nonnegative_int(
                summary.get("duration_seconds") if isinstance(summary, dict) else None
            )
        )
        active_days.append(int(activity_count > 0))
    return {
        "weeks_with_activity": sum(day > 0 for day in active_days),
        "activity_count_total": sum(activity_counts),
        "activity_count_weekly_mean": _mean(activity_counts),
        "activity_count_weekly_median": _median(activity_counts),
        "duration_seconds_total": sum(durations),
        "duration_seconds_weekly_mean": _mean(durations),
        "duration_seconds_weekly_median": _median(durations),
        "duration_seconds_highest_week": max(durations, default=0),
    }


def _mean(values: list[int]) -> float | None:
    return None if not values else round(sum(values) / len(values), 1)


def _median(values: list[int]) -> float | int | None:
    return None if not values else median(values)


def _summarize_daily_training_window(
    daily_training: list[dict[str, object]], *, expected_days: int
) -> dict[str, object]:
    training = {
        sport_type: {
            "activity_count": 0,
            "active_days": 0,
            "duration_seconds": 0,
            "known_distance_meters": 0,
            "missing_distance_activity_count": 0,
        }
        for sport_type in INCLUDED_SPORTS
    }
    for item in daily_training:
        summaries = item.get("training")
        if not isinstance(summaries, dict):
            continue
        for sport_type in INCLUDED_SPORTS:
            summary = summaries.get(sport_type)
            if not isinstance(summary, dict):
                continue
            activity_count = _nonnegative_int(summary.get("activity_count"))
            target = training[sport_type]
            target["activity_count"] += activity_count
            target["active_days"] += int(activity_count > 0)
            target["duration_seconds"] += _nonnegative_int(summary.get("duration_seconds"))
            target["known_distance_meters"] += _nonnegative_number(
                summary.get("known_distance_meters")
            )
            target["missing_distance_activity_count"] += _nonnegative_int(
                summary.get("missing_distance_activity_count")
            )
    return {
        "calendar_days": expected_days,
        "observed_daily_rows": len(daily_training),
        "start_date": daily_training[0]["date"] if daily_training else None,
        "end_date": daily_training[-1]["date"] if daily_training else None,
        "training": training,
    }


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _nonnegative_number(value: object) -> float | int:
    return value if isinstance(value, (int, float)) and value >= 0 else 0


def _detailed_activity(activity) -> dict[str, object]:
    """Use summary columns only; omit provider ID, name, GPS, and raw data."""

    return {
        "activity_date": athlete_local_date(activity.start_time).isoformat(),
        "sport_type": activity.sport_type,
        "duration_seconds": activity.duration_seconds,
        "distance_meters": activity.distance_meters,
        "elevation_gain_meters": activity.elevation_gain_meters,
        "average_heart_rate": activity.average_heart_rate,
        "maximum_heart_rate": activity.maximum_heart_rate,
        "average_speed_mps": (
            activity.average_speed_mps if activity.sport_type == "run" else None
        ),
        "average_power": activity.average_power if activity.sport_type == "ride" else None,
        "training_effect_aerobic": activity.training_effect_aerobic,
        "training_effect_anaerobic": activity.training_effect_anaerobic,
    }


def _daily_fact(*, target_date, activities, metric, feedback, context_events) -> dict[str, object]:
    return {
        "date": target_date.isoformat(),
        "training": _sport_summaries(activities),
        "recovery": {
            "hrv_value": None if metric is None else metric.hrv_value,
            "resting_heart_rate": None if metric is None else metric.resting_heart_rate,
            "sleep_duration_seconds": (
                None if metric is None else metric.sleep_duration_seconds
            ),
        },
        "explicit_feedback": [_feedback_fact(item) for item in feedback],
        "context_event_types": sorted({event.event_type for event in context_events}),
    }


def _weekly_fact(*, start_date, end_date, activities, feedback) -> dict[str, object]:
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "training": _sport_summaries(activities, include_longest=True),
        "active_days": len({athlete_local_date(item.start_time) for item in activities}),
        "explicit_feedback": _weekly_feedback_summary(feedback),
    }


def _sport_summaries(activities, *, include_longest: bool = False) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for sport_type in INCLUDED_SPORTS:
        sport_activities = [item for item in activities if item.sport_type == sport_type]
        known_distances = [
            item.distance_meters
            for item in sport_activities
            if item.distance_meters is not None
        ]
        summary: dict[str, object] = {
            "activity_count": len(sport_activities),
            "duration_seconds": sum(item.duration_seconds for item in sport_activities),
            "known_distance_meters": sum(known_distances),
            "missing_distance_activity_count": len(sport_activities) - len(known_distances),
        }
        if include_longest:
            summary["longest_duration_seconds"] = max(
                (item.duration_seconds for item in sport_activities), default=None
            )
            summary["longest_known_distance_meters"] = max(known_distances, default=None)
        result[sport_type] = summary
    return result


def _feedback_fact(item) -> dict[str, object]:
    return {
        "sport_type": item.sport_type,
        "outcome": item.outcome,
        "perceived_exertion": item.perceived_exertion,
        "reason_code": item.reason_code,
    }


def _weekly_feedback_summary(feedback) -> dict[str, object]:
    reported_rpe = [
        item.perceived_exertion for item in feedback if item.perceived_exertion is not None
    ]
    return {
        "feedback_count": len(feedback),
        "completed_count": sum(item.outcome == "completed" for item in feedback),
        "limited_count": sum(item.outcome == "completed_limited" for item in feedback),
        "skipped_count": sum(item.outcome == "skipped" for item in feedback),
        "reported_rpe_average": (
            None if not reported_rpe else sum(reported_rpe) / len(reported_rpe)
        ),
    }


def _date_range(start_date: date, end_date: date):
    for offset in range((end_date - start_date).days + 1):
        yield start_date + timedelta(days=offset)


def _rolling_week_end_dates(end_date: date):
    for index in range(WEEKLY_HISTORY_DAYS // WEEKLY_WINDOW_DAYS - 1, -1, -1):
        yield end_date - timedelta(days=index * WEEKLY_WINDOW_DAYS)
