from pprint import pprint

from running_agent.integrations.strava_client import get_athlete_activities


if __name__ == "__main__":
    activities = get_athlete_activities(per_page=5)
    pprint(activities)