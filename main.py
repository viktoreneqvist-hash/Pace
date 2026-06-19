from pprint import pprint

from running_agent.database import create_database_tables
from running_agent.integrations.strava_importer import import_recent_strava_activities


if __name__ == "__main__":
    create_database_tables()

    imported = import_recent_strava_activities(per_page=100)

    print(f"Imported {len(imported)} new activities")
    pprint(imported[:5])