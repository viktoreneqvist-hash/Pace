import pytest

from pace.services.heart_rate_zone_service import (
    HeartRateZoneInput,
    HeartRateZoneService,
)


def test_confirmed_garmin_ride_zones_are_saved_without_physiology_inference():
    profile = HeartRateZoneService().set_profile(
        HeartRateZoneInput(
            sport_type="ride",
            zones=("1:100-120", "2:121-140", "3:141-155", "4:156-170", "5:171-190"),
        )
    )

    assert profile.sport_type == "ride"
    assert profile.zones[1] == {"zone": 2, "lower_bpm": 121, "upper_bpm": 140}


def test_heart_rate_zone_configuration_rejects_a_gap():
    with pytest.raises(ValueError, match="gaps"):
        HeartRateZoneService().set_profile(
            HeartRateZoneInput(
                sport_type="ride",
                zones=("1:100-120", "2:125-140", "3:141-155", "4:156-170", "5:171-190"),
            )
        )
