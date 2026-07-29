import pytest

from pace.services.training_preference_service import (
    TrainingPreferenceInput,
    TrainingPreferenceService,
)


def test_coaching_ambition_is_saved_and_preserved_when_not_reselected():
    service = TrainingPreferenceService()

    created = service.set_preference(
        TrainingPreferenceInput(
            sport_role="ride_primary",
            available_days=("mon:any", "wed:60"),
            coaching_ambition="ambitious",
        )
    )
    updated = service.set_preference(
        TrainingPreferenceInput(
            sport_role="balanced",
            available_days=("tue:any",),
        )
    )

    assert created.coaching_ambition == "ambitious"
    assert updated.coaching_ambition == "ambitious"
    assert updated.sport_role == "balanced"


def test_coaching_ambition_rejects_unknown_values():
    with pytest.raises(ValueError, match="Unsupported coaching ambition"):
        TrainingPreferenceService().set_preference(
            TrainingPreferenceInput(
                sport_role="balanced",
                available_days=("mon:any",),
                coaching_ambition="maximal",
            )
        )


def test_coaching_ambition_can_change_without_reentering_availability():
    service = TrainingPreferenceService()
    service.set_preference(
        TrainingPreferenceInput(
            sport_role="ride_primary",
            available_days=("mon:any", "wed:60"),
        )
    )

    preference = service.set_coaching_ambition(coaching_ambition="cautious")

    assert preference.coaching_ambition == "cautious"
    assert preference.available_days == [
        {"day": "mon", "minutes": None},
        {"day": "wed", "minutes": 60},
    ]


@pytest.mark.parametrize("sport_role", ("run_only", "ride_only"))
def test_only_sport_roles_are_valid_explicit_athlete_boundaries(sport_role):
    preference = TrainingPreferenceService().set_preference(
        TrainingPreferenceInput(
            sport_role=sport_role,
            available_days=("mon:any",),
        )
    )

    assert preference.sport_role == sport_role
