from datetime import date

import pytest

from pace.services.race_service import RaceInput, RaceService, resolved_taper
from pace.database.models import TrainingPlan
from pace.database.session import session_scope


def test_race_service_stores_an_explicit_goal_without_treating_goal_time_as_capacity():
    race = RaceService().add_race(
        RaceInput(
            name="Stockholm Marathon",
            sport_type="run",
            race_date=date(2026, 10, 10),
            distance_meters=42_195,
            priority="A",
            desired_time_seconds=10_800,
        )
    )

    assert race.name == "Stockholm Marathon"
    assert race.priority == "A"
    assert race.desired_time_seconds == 10_800
    assert race.taper_override is None
    assert resolved_taper(race) == "full"


def test_race_service_lists_upcoming_races_and_applies_overrides_per_race():
    service = RaceService()
    first_race = service.add_race(
        RaceInput(
            name="B-race",
            sport_type="run",
            race_date=date(2026, 9, 1),
            distance_meters=10_000,
            priority="B",
            taper_override="none",
        )
    )
    service.add_race(
        RaceInput(
            name="Past race",
            sport_type="ride",
            race_date=date(2026, 7, 1),
            distance_meters=40_000,
            priority="C",
        )
    )

    races = service.list_upcoming_races(as_of_date=date(2026, 7, 26))

    assert [race.id for race in races] == [first_race.id]
    assert resolved_taper(races[0]) == "none"


def test_race_service_updates_priority_or_taper_without_changing_race_facts():
    service = RaceService()
    race = service.add_race(
        RaceInput(
            name="Autumn half",
            sport_type="run",
            race_date=date(2026, 10, 10),
            distance_meters=21_097.5,
            priority="B",
        )
    )

    updated = service.update_race(race_id=race.id, priority="A", taper_override="partial")

    assert updated.name == "Autumn half"
    assert updated.priority == "A"
    assert updated.taper_override == "partial"
    assert resolved_taper(updated) == "partial"

    restored_default = service.update_race(race_id=race.id, taper_override="default")

    assert restored_default.taper_override is None
    assert resolved_taper(restored_default) == "full"


def test_race_service_rejects_invalid_sport_priority_distance_or_taper():
    service = RaceService()
    base_input = dict(
        name="Test race",
        race_date=date(2026, 10, 10),
        distance_meters=10_000,
        priority="A",
    )

    with pytest.raises(ValueError, match="sport"):
        service.add_race(RaceInput(sport_type="swim", **base_input))
    with pytest.raises(ValueError, match="priority"):
        service.add_race(RaceInput(sport_type="run", priority="D", **{key: value for key, value in base_input.items() if key != "priority"}))
    with pytest.raises(ValueError, match="greater than zero"):
        service.add_race(RaceInput(sport_type="run", distance_meters=0, **{key: value for key, value in base_input.items() if key != "distance_meters"}))
    with pytest.raises(ValueError, match="taper"):
        service.add_race(RaceInput(sport_type="run", taper_override="auto", **base_input))


def test_unused_future_race_can_correct_all_facts_or_be_removed():
    service = RaceService()
    race = service.add_race(
        RaceInput(
            name="Wrong date",
            sport_type="run",
            race_date=date(2026, 10, 10),
            distance_meters=10_000,
            priority="A",
        )
    )

    updated = service.update_race(
        race_id=race.id,
        name="Correct race",
        sport_type="ride",
        race_date=date(2026, 11, 1),
        distance_meters=80_000,
        desired_time_seconds=10_800,
    )
    service.remove_race(race_id=race.id, as_of_date=date(2026, 7, 27))

    assert updated.name == "Correct race"
    assert updated.sport_type == "ride"
    assert updated.race_date == date(2026, 11, 1)
    assert service.list_races(as_of_date=date(2026, 7, 27), include_past=False) == []


def test_cancelled_race_is_hidden_from_upcoming_planning_but_remains_auditable():
    service = RaceService()
    race = service.add_race(
        RaceInput(
            name="Cancelled race",
            sport_type="run",
            race_date=date(2026, 10, 10),
            distance_meters=10_000,
            priority="A",
        )
    )

    cancelled = service.cancel_race(race_id=race.id, as_of_date=date(2026, 7, 27))

    assert cancelled.status == "cancelled"
    assert service.list_upcoming_races(as_of_date=date(2026, 7, 27)) == []
    assert service.list_races(
        as_of_date=date(2026, 7, 27), include_past=False, include_cancelled=True
    )[0].id == race.id


def test_linked_race_facts_and_removal_are_protected():
    service = RaceService()
    race = service.add_race(
        RaceInput(
            name="Linked race",
            sport_type="run",
            race_date=date(2026, 10, 10),
            distance_meters=10_000,
            priority="A",
        )
    )
    with session_scope() as session:
        session.add(
            TrainingPlan(
                status="draft",
                contract_version=2,
                goal_mode="race",
                race_id=race.id,
                as_of_date=date(2026, 7, 27),
                block_start_date=date(2026, 7, 27),
                block_end_date=date(2026, 10, 10),
                detailed_start_date=date(2026, 7, 27),
                detailed_end_date=date(2026, 8, 9),
                block_outline=[],
                context_snapshot={},
                coach_assessment={},
            )
        )

    with pytest.raises(ValueError, match="cannot change"):
        service.update_race(race_id=race.id, race_date=date(2026, 10, 11))
    with pytest.raises(ValueError, match="cannot be removed"):
        service.remove_race(race_id=race.id, as_of_date=date(2026, 7, 27))
