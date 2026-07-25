import json
from pathlib import Path

from pace.integrations.garmin.importer import import_activity
from pace.services.activity_service import get_all_activities


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "garmin"


def test_importing_the_same_garmin_activity_twice_does_not_create_a_duplicate():
    mock_activity = json.loads(
        (FIXTURES_PATH / "running_activity.json").read_text(encoding="utf-8")
    )

    first_import = import_activity(mock_activity)
    second_import = import_activity(mock_activity)
    activities = get_all_activities()

    assert first_import.id is not None
    assert second_import.id == first_import.id
    assert len(activities) == 1
    assert activities[0].provider == "garmin"
    assert activities[0].provider_activity_id == "mock-garmin-1"
    assert activities[0].distance_meters == 10_000
