"""Persistence for athlete-confirmed Garmin heart-rate zone profiles."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import HeartRateZoneProfile


def get_heart_rate_zone_profile(
    session: Session, *, sport_type: str
) -> HeartRateZoneProfile | None:
    return session.scalar(
        select(HeartRateZoneProfile).where(HeartRateZoneProfile.sport_type == sport_type)
    )


def upsert_heart_rate_zone_profile(
    session: Session,
    *,
    sport_type: str,
    zones: list[dict[str, int]],
) -> HeartRateZoneProfile:
    profile = get_heart_rate_zone_profile(session, sport_type=sport_type)
    if profile is None:
        profile = HeartRateZoneProfile(sport_type=sport_type, zones=zones)
        session.add(profile)
    else:
        profile.zones = zones
    session.flush()
    return profile
