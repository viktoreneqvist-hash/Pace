from datetime import date

from pace.database.models import Race, TrainingPlan
from pace.database.session import session_scope
from pace.services.plan_checkpoint_service import PlanCheckpointService


def test_checkpoint_recommends_an_explicit_revision_for_an_approaching_race():
    with session_scope() as session:
        plan = TrainingPlan(
            status="accepted",
            contract_version=3,
            goal_mode="race",
            race_id=None,
            as_of_date=date(2026, 7, 27),
            block_start_date=date(2026, 7, 27),
            block_end_date=date(2026, 10, 11),
            detailed_start_date=date(2026, 7, 27),
            detailed_end_date=date(2026, 8, 9),
            block_outline=[],
            context_snapshot={},
            coach_assessment={},
        )
        session.add(plan)
        session.add(
            Race(
                name="B-lopp",
                sport_type="run",
                race_date=date(2026, 8, 15),
                distance_meters=10_000,
                priority="B",
                desired_time_seconds=None,
                taper_override=None,
                status="active",
            )
        )
        session.flush()
        plan_id = plan.id

    checkpoint = PlanCheckpointService().get_checkpoint(as_of_date=date(2026, 8, 7))

    assert checkpoint.status == "revision_due"
    assert checkpoint.active_plan_id == plan_id
    assert "race_approaching_next_window" in checkpoint.reasons
    assert checkpoint.recommended_command == (
        f"uv run pace plan revise --id {plan_id} --days 14"
    )


def test_checkpoint_never_creates_a_plan_when_no_active_plan_exists():
    checkpoint = PlanCheckpointService().get_checkpoint(as_of_date=date(2026, 7, 27))

    assert checkpoint.status == "no_active_plan"
    assert checkpoint.active_plan_id is None
    assert checkpoint.recommended_command == "uv run pace plan draft --days 14"


def test_checkpoint_does_not_recommend_a_revision_before_it_can_include_the_race():
    with session_scope() as session:
        session.add(
            TrainingPlan(
                status="accepted",
                contract_version=3,
                goal_mode="race",
                race_id=None,
                as_of_date=date(2026, 7, 27),
                block_start_date=date(2026, 7, 27),
                block_end_date=date(2026, 10, 11),
                detailed_start_date=date(2026, 7, 27),
                detailed_end_date=date(2026, 8, 9),
                block_outline=[],
                context_snapshot={},
                coach_assessment={},
            )
        )
        session.add(
            Race(
                name="B-lopp",
                sport_type="run",
                race_date=date(2026, 8, 15),
                distance_meters=10_000,
                priority="B",
                desired_time_seconds=None,
                taper_override=None,
                status="active",
            )
        )

    checkpoint = PlanCheckpointService().get_checkpoint(as_of_date=date(2026, 7, 27))

    assert checkpoint.status == "current"
    assert checkpoint.upcoming_races[0].days_until_race == 19
    assert checkpoint.reasons == ("detailed_window_current",)
    assert checkpoint.recommended_command is None


def test_checkpoint_waits_when_race_is_exactly_fourteen_calendar_days_away():
    with session_scope() as session:
        session.add(
            TrainingPlan(
                status="accepted",
                contract_version=3,
                goal_mode="race",
                race_id=None,
                as_of_date=date(2026, 8, 1),
                block_start_date=date(2026, 8, 1),
                block_end_date=date(2026, 10, 11),
                detailed_start_date=date(2026, 8, 1),
                detailed_end_date=date(2026, 8, 9),
                block_outline=[],
                context_snapshot={},
                coach_assessment={},
            )
        )
        session.add(
            Race(
                name="B-lopp",
                sport_type="run",
                race_date=date(2026, 8, 15),
                distance_meters=10_000,
                priority="B",
                desired_time_seconds=None,
                taper_override=None,
                status="active",
            )
        )

    checkpoint = PlanCheckpointService().get_checkpoint(as_of_date=date(2026, 8, 1))

    assert checkpoint.status == "current"
    assert checkpoint.upcoming_races[0].days_until_race == 14
    assert checkpoint.recommended_command is None
