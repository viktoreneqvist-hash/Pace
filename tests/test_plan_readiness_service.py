from datetime import UTC, date, datetime

from pace.database.models import ContextEvent, SyncRun
from pace.database.session import session_scope
from pace.services.plan_readiness_service import PlanReadinessService
from pace.services.race_service import RaceInput, RaceService


def _completed_sync(*, start_date: date, end_date: date, status: str = "success") -> SyncRun:
    return SyncRun(
        provider="garmin",
        completed_at=datetime(2026, 7, 26, 8, tzinfo=UTC),
        status=status,
        requested_start_date=start_date,
        requested_end_date=end_date,
    )


def _add_four_contiguous_weeks() -> None:
    with session_scope() as session:
        session.add_all(
            [
                _completed_sync(start_date=date(2026, 6, 28), end_date=date(2026, 7, 4)),
                _completed_sync(start_date=date(2026, 7, 5), end_date=date(2026, 7, 11)),
                _completed_sync(start_date=date(2026, 7, 12), end_date=date(2026, 7, 18)),
                _completed_sync(start_date=date(2026, 7, 19), end_date=date(2026, 7, 25), status="partial"),
            ]
        )


def test_plan_readiness_accepts_four_contiguous_garmin_weeks_and_general_goal():
    _add_four_contiguous_weeks()

    readiness = PlanReadinessService().get_readiness(as_of_date=date(2026, 7, 26))

    assert readiness.status == "ready"
    assert readiness.history.covered_calendar_days == 28
    assert readiness.history.covered_start_date == date(2026, 6, 28)
    assert readiness.history.covered_end_date == date(2026, 7, 25)
    assert readiness.upcoming_races == ()
    assert readiness.limitations == ("no_upcoming_race_uses_general_goal",)


def test_plan_readiness_blocks_short_history_and_exposes_no_private_note_text():
    with session_scope() as session:
        session.add(
            _completed_sync(start_date=date(2026, 7, 19), end_date=date(2026, 7, 25))
        )

    readiness = PlanReadinessService().get_readiness(as_of_date=date(2026, 7, 26))

    assert readiness.status == "blocked"
    assert readiness.blockers[0].code == "insufficient_garmin_history"
    assert readiness.history.covered_calendar_days == 7


def test_plan_readiness_blocks_history_that_is_more_than_one_day_stale():
    _add_four_contiguous_weeks()

    readiness = PlanReadinessService().get_readiness(as_of_date=date(2026, 7, 27))

    assert readiness.status == "blocked"
    assert [blocker.code for blocker in readiness.blockers] == ["stale_garmin_history"]
    assert "garmin_history_is_stale" in readiness.limitations


def test_plan_readiness_blocks_an_active_pain_or_illness_event():
    _add_four_contiguous_weeks()
    with session_scope() as session:
        session.add(
            ContextEvent(
                event_type="pain",
                start_date=date(2026, 7, 20),
                end_date=None,
                note="Private pain note.",
                affected_metrics=[],
                status="active",
            )
        )

    readiness = PlanReadinessService().get_readiness(as_of_date=date(2026, 7, 26))

    assert readiness.status == "blocked"
    assert readiness.blockers[0].code == "active_pain"
    assert readiness.blockers[0].event_type == "pain"
    assert not hasattr(readiness.blockers[0], "note")


def test_plan_readiness_includes_multiple_upcoming_races_and_their_taper_policy():
    _add_four_contiguous_weeks()
    races = RaceService()
    races.add_race(
        RaceInput(
            name="Main race",
            sport_type="run",
            race_date=date(2026, 10, 10),
            distance_meters=42_195,
            priority="A",
        )
    )
    races.add_race(
        RaceInput(
            name="Tune-up",
            sport_type="run",
            race_date=date(2026, 9, 1),
            distance_meters=10_000,
            priority="B",
            taper_override="none",
        )
    )

    readiness = PlanReadinessService().get_readiness(as_of_date=date(2026, 7, 26))

    assert readiness.status == "ready"
    assert [race.name for race in readiness.upcoming_races] == ["Tune-up", "Main race"]
    assert [race.taper for race in readiness.upcoming_races] == ["none", "full"]
