from datetime import date, timedelta

from running_agent.models.activity import Activity


def get_total_distance_km(activities: list[Activity]) -> float:
    return sum(activity.distance_km for activity in activities)


def get_distance_last_n_days(
    activities: list[Activity],
    end_date: date,
    days: int,
) -> float:
    start_date = end_date - timedelta(days=days - 1)

    return sum(
        activity.distance_km
        for activity in activities
        if start_date <= activity.date <= end_date
    )


def get_longest_activity(activities: list[Activity]) -> Activity | None:
    if not activities:
        return None

    return max(activities, key=lambda activity: activity.distance_km)

def filter_activities_by_sport_type(activities: list[Activity], sport_type: str) -> list[Activity]:
    return [activity for activity in activities if activity.sport_type == sport_type]