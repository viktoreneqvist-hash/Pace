"""Validate Garmin-configured heart-rate zones without physiology inference."""

from dataclasses import dataclass

from pace.database.models import HeartRateZoneProfile
from pace.database.session import session_scope
from pace.repositories.heart_rate_zone_repository import (
    get_heart_rate_zone_profile,
    upsert_heart_rate_zone_profile,
)


SUPPORTED_ZONE_SPORTS = frozenset({"ride"})


@dataclass(frozen=True, slots=True)
class HeartRateZoneInput:
    sport_type: str
    zones: tuple[str, ...]


class HeartRateZoneService:
    """Store a locally confirmed copy of Garmin zone boundaries."""

    def set_profile(self, zone_input: HeartRateZoneInput) -> HeartRateZoneProfile:
        sport_type = zone_input.sport_type.strip().lower()
        if sport_type not in SUPPORTED_ZONE_SPORTS:
            raise ValueError("Only ride heart-rate zones are configured in this Pace slice.")
        zones = _parse_zones(zone_input.zones)
        with session_scope() as session:
            return upsert_heart_rate_zone_profile(
                session,
                sport_type=sport_type,
                zones=zones,
            )

    def get_profile(self, *, sport_type: str) -> HeartRateZoneProfile | None:
        with session_scope() as session:
            return get_heart_rate_zone_profile(session, sport_type=sport_type)


def _parse_zones(values: tuple[str, ...]) -> list[dict[str, int]]:
    if len(values) != 5:
        raise ValueError("Provide exactly five --zone values, for example 1:100-120.")
    parsed: list[dict[str, int]] = []
    for value in values:
        zone_text, separator, bounds = value.strip().partition(":")
        lower_text, dash, upper_text = bounds.partition("-")
        if not separator or not dash:
            raise ValueError("Each --zone must have format 1:100-120.")
        try:
            zone = int(zone_text)
            lower = int(lower_text)
            upper = int(upper_text)
        except ValueError as error:
            raise ValueError("Zone numbers and bpm bounds must be whole numbers.") from error
        if zone != len(parsed) + 1 or lower <= 0 or upper < lower:
            raise ValueError("Zones must be Z1–Z5 with positive ascending bpm bounds.")
        if parsed and lower > parsed[-1]["upper_bpm"] + 1:
            raise ValueError("Heart-rate zones cannot contain gaps.")
        if parsed and lower <= parsed[-1]["upper_bpm"]:
            raise ValueError("Heart-rate zones cannot overlap.")
        parsed.append({"zone": zone, "lower_bpm": lower, "upper_bpm": upper})
    return parsed
