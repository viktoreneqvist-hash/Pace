from datetime import date, datetime, timedelta
from types import SimpleNamespace

from pace.services.pace_light_service import (
    _select_recent_activities,
    _serialize_plan,
)
from scripts.pace_light_sync import KEYCHAIN_ACCOUNT, KEYCHAIN_SERVICE


def test_snapshot_plan_excludes_private_and_provider_fields():
    target = SimpleNamespace(
        kind="rpe", rpe_min=2, rpe_max=3, pace_seconds_per_km=None, power_watts=None
    )
    step = SimpleNamespace(
        kind="steady", repetitions=1, duration_seconds=3600,
        distance_meters=None, target=target, recovery_distance_meters=None,
        recovery_duration_seconds=None, recovery_target=None, instruction="Easy.",
    )
    session = SimpleNamespace(
        scheduled_date=date(2026, 10, 24), sport_type="run", purpose="Easy run",
        duration_seconds=3600, distance_meters=10000, target_display="RPE 2–3",
        workout_steps=(step,),
    )
    plan = SimpleNamespace(
        detailed_start_date=date(2026, 10, 24), detailed_end_date=date(2026, 10, 30),
        goal_mode="general", as_of_date=date(2026, 10, 23), sessions=(session,),
    )
    payload = _serialize_plan(plan)
    serialized = str(payload)
    assert "provider" not in serialized
    assert "raw_payload" not in serialized
    assert "Easy run" in serialized


def test_uploader_uses_dedicated_keychain_identity():
    assert KEYCHAIN_ACCOUNT == "pace-light"
    assert KEYCHAIN_SERVICE == "chatgpt.site.pace-light-private.uploader"


def test_recent_activities_use_28_days_ending_at_latest_stored_activity():
    as_of_date = date(2026, 10, 23)
    activities = [
        SimpleNamespace(
            sport_type="run",
            start_time=datetime(2026, 1, 1) + timedelta(days=index),
        )
        for index in range(100)
    ]
    activities.extend(
        [
            SimpleNamespace(sport_type="other", start_time=datetime(2026, 10, 1)),
            SimpleNamespace(sport_type="ride", start_time=datetime(2026, 10, 24)),
        ]
    )

    selected = _select_recent_activities(activities, as_of_date=as_of_date)

    assert len(selected) == 28
    assert selected[0] is activities[72]
    assert selected[-1] is activities[99]
