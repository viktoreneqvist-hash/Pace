from pace.models.activity import Activity


def calculate_total_distance_km(activities: list[Activity]) -> float:
    return sum(activity.distance_km for activity in activities)
