"""Read-only gates for future Pace plan generation."""

from datetime import date, timedelta

from pace.database.session import session_scope
from pace.planning.models import (
    HistoryCoverage,
    PlanReadiness,
    PlanningBlocker,
    RacePlanningFact,
)
from pace.repositories.context_event_repository import get_context_events_for_date
from pace.repositories.race_repository import get_upcoming_races
from pace.repositories.sync_run_repository import get_completed_sync_runs_through_date
from pace.services.race_service import resolved_taper


REQUIRED_HISTORY_DAYS = 28
MAX_HISTORY_STALENESS_DAYS = 1
PLANNING_BLOCKER_EVENT_TYPES = frozenset({"illness", "pain"})


class PlanReadinessService:
    """Expose planning prerequisites without generating advice or workouts."""

    def get_readiness(self, *, as_of_date: date) -> PlanReadiness:
        """Return explicit history and health gates for one planning date."""

        with session_scope() as session:
            sync_runs = get_completed_sync_runs_through_date(
                session,
                provider="garmin",
                end_date=as_of_date,
            )
            active_events = get_context_events_for_date(session, as_of_date)
            races = get_upcoming_races(session, as_of_date=as_of_date)

        history = _summarize_history_coverage(sync_runs)
        health_blockers = tuple(
            PlanningBlocker(
                code=f"active_{event.event_type}",
                event_type=event.event_type,
                start_date=event.start_date,
            )
            for event in active_events
            if event.status == "active"
            and event.event_type in PLANNING_BLOCKER_EVENT_TYPES
        )
        blockers = list(health_blockers)
        limitations: list[str] = []
        if not history.is_contiguous:
            blockers.append(PlanningBlocker(code="insufficient_garmin_history"))
            limitations.append("requires_28_contiguous_garmin_history_days")
        elif (
            history.covered_end_date is None
            or (as_of_date - history.covered_end_date).days > MAX_HISTORY_STALENESS_DAYS
        ):
            blockers.append(PlanningBlocker(code="stale_garmin_history"))
            limitations.append("garmin_history_is_stale")
        if not races:
            limitations.append("no_upcoming_race_uses_general_goal")

        return PlanReadiness(
            as_of_date=as_of_date,
            status="blocked" if blockers else "ready",
            history=history,
            upcoming_races=tuple(
                RacePlanningFact(
                    id=race.id,
                    name=race.name,
                    sport_type=race.sport_type,
                    race_date=race.race_date,
                    distance_meters=race.distance_meters,
                    priority=race.priority,
                    desired_time_seconds=race.desired_time_seconds,
                    taper=resolved_taper(race),
                )
                for race in races
            ),
            blockers=tuple(blockers),
            limitations=tuple(limitations),
        )


def _summarize_history_coverage(sync_runs) -> HistoryCoverage:
    """Measure the newest contiguous Garmin-sync window without inferring data."""

    ranges = sorted(
        (
            (sync_run.requested_start_date, sync_run.requested_end_date)
            for sync_run in sync_runs
            if sync_run.requested_start_date is not None
            and sync_run.requested_end_date is not None
        ),
        key=lambda item: (item[0], item[1]),
    )
    if not ranges:
        return HistoryCoverage(
            required_calendar_days=REQUIRED_HISTORY_DAYS,
            covered_calendar_days=0,
            required_start_date=None,
            covered_start_date=None,
            covered_end_date=None,
            is_contiguous=False,
        )

    contiguous_start, contiguous_end = ranges[0]
    for start_date, end_date in ranges[1:]:
        if start_date > contiguous_end + timedelta(days=1):
            contiguous_start, contiguous_end = start_date, end_date
        else:
            contiguous_end = max(contiguous_end, end_date)

    covered_calendar_days = (contiguous_end - contiguous_start).days + 1
    required_start_date = contiguous_end - timedelta(days=REQUIRED_HISTORY_DAYS - 1)
    return HistoryCoverage(
        required_calendar_days=REQUIRED_HISTORY_DAYS,
        covered_calendar_days=covered_calendar_days,
        required_start_date=required_start_date,
        covered_start_date=contiguous_start,
        covered_end_date=contiguous_end,
        is_contiguous=covered_calendar_days >= REQUIRED_HISTORY_DAYS,
    )
