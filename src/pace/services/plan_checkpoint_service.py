"""Determine when the athlete should explicitly request a new short plan revision."""

from datetime import date, timedelta

from pace.planning.checkpoint_models import PlanCheckpoint, RaceCheckpointFact
from pace.services.race_service import RaceService
from pace.services.training_plan_service import TrainingPlanService


REVISION_NOTICE_DAYS = 3
RACE_LOOKAHEAD_DAYS = 21
RECOMMENDED_REVISION_DAYS = 14


class PlanCheckpointService:
    """Recommend an action without creating or changing a plan."""

    def get_checkpoint(self, *, as_of_date: date) -> PlanCheckpoint:
        plans = TrainingPlanService().list_plans()
        active = next(
            (
                plan
                for plan in plans
                if plan.status == "accepted"
                and plan.block_start_date <= as_of_date <= plan.block_end_date
            ),
            None,
        )
        races = RaceService().list_upcoming_races(as_of_date=as_of_date)
        if active is None:
            return PlanCheckpoint(
                as_of_date=as_of_date,
                status="no_active_plan",
                active_plan_id=None,
                detailed_end_date=None,
                detailed_days_remaining=None,
                upcoming_races=_race_facts(races, as_of_date=as_of_date, detailed_end=None),
                reasons=("no_active_accepted_plan",),
                recommended_command="uv run pace plan draft --days 14",
            )

        remaining = (active.detailed_end_date - as_of_date).days
        race_facts = _race_facts(
            races,
            as_of_date=as_of_date,
            detailed_end=active.detailed_end_date,
        )
        reasons: list[str] = []
        status = "current"
        if remaining < 0:
            status = "revision_due"
            reasons.append("detailed_window_expired")
        elif remaining <= REVISION_NOTICE_DAYS:
            status = "revision_due"
            reasons.append("detailed_window_ending")
        if any(item.inside_detailed_window for item in race_facts):
            reasons.append("race_inside_detailed_window")
        if any(
            0 <= item.days_until_race < RECOMMENDED_REVISION_DAYS
            and not item.inside_detailed_window
            for item in race_facts
        ):
            status = "revision_due"
            reasons.append("race_approaching_next_window")
        return PlanCheckpoint(
            as_of_date=as_of_date,
            status=status,
            active_plan_id=active.id,
            detailed_end_date=active.detailed_end_date,
            detailed_days_remaining=max(remaining, 0),
            upcoming_races=race_facts,
            reasons=tuple(reasons) or ("detailed_window_current",),
            recommended_command=(
                f"uv run pace plan revise --id {active.id} --days 14"
                if status == "revision_due"
                else None
            ),
        )


def _race_facts(races, *, as_of_date: date, detailed_end: date | None):
    limit = as_of_date + timedelta(days=RACE_LOOKAHEAD_DAYS)
    return tuple(
        RaceCheckpointFact(
            race_id=race.id,
            name=race.name,
            race_date=race.race_date,
            priority=race.priority,
            days_until_race=(race.race_date - as_of_date).days,
            inside_detailed_window=(
                detailed_end is not None and race.race_date <= detailed_end
            ),
        )
        for race in races
        if race.race_date <= limit
    )
