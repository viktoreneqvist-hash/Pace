from pace.database.models import Activity


def calculate_total_distance_km(activities: list[Activity]) -> float:
    return sum((activity.distance_meters or 0) / 1000 for activity in activities)
