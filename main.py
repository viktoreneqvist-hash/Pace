from collections import Counter
from datetime import date
from pprint import pprint

from running_agent.analysis.volume_analysis import (
    filter_activities_by_sport_type,
    get_distance_last_n_days,
    get_longest_activity,
    get_total_distance_km,
)
from running_agent.services.activity_service import get_all_activities


def build_sport_summary(activities, sport_type: str) -> dict:
    sport_activities = filter_activities_by_sport_type(activities, sport_type)
    longest = get_longest_activity(sport_activities)

    return {
        "sport_type": sport_type,
        "activities": len(sport_activities),
        "total_distance_km": round(get_total_distance_km(sport_activities), 1),
        "distance_last_7_days_km": round(
            get_distance_last_n_days(sport_activities, date.today(), 7),
            1,
        ),
        "distance_last_30_days_km": round(
            get_distance_last_n_days(sport_activities, date.today(), 30),
            1,
        ),
        "longest_activity_km": round(longest.distance_km, 1) if longest else None,
        "longest_activity_date": longest.date if longest else None,
    }


if __name__ == "__main__":
    activities = get_all_activities()

    print("Sport types in database:")
    for sport_type, count in Counter(activity.sport_type for activity in activities).most_common():
        print(f"{sport_type}: {count}")

    print()

    pprint(build_sport_summary(activities, "Run"))
    pprint(build_sport_summary(activities, "Ride"))