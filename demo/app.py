"""Serve a realistic Pace UI using synthetic facts and no external services.

Run with:

    uv run uvicorn demo.app:app --host 127.0.0.1 --port 8877

This module never opens the athlete database, Garmin, or OpenAI.
"""

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from pace.personalization.models import PersonalizationEvidence
from pace.planning.checkpoint_models import PlanCheckpoint
from pace.planning.plan_models import (
    CoachAssessmentFact,
    PlanSessionFact,
    SessionTargetFact,
    TrainingPlanFact,
    WorkoutStepFact,
)
from pace.state.models import (
    AthleteContextWindow,
    AthleteState,
    AthleteStateDataQuality,
    RecoveryDataQuality,
    RecoveryDayObservation,
    SyncDataQuality,
)
from pace.training_analysis.models import (
    SportWindowAnalysis,
    TransparentTrainingAnalysis,
)
from pace.trends.analysis import build_training_response_trends
from pace.trends.models import FeedbackTrendRecord
from pace.web.app import WebServices, create_app


TODAY = date(2026, 9, 15)
DEMO_DIRECTORY = Path(__file__).resolve().parent


def _rpe(low: int, high: int) -> SessionTargetFact:
    return SessionTargetFact("rpe", low, high, None, None, None)


def _no_target() -> SessionTargetFact:
    return SessionTargetFact("none", None, None, None, None, None)


def _step(
    kind: str,
    *,
    minutes: int | None = None,
    distance_meters: float | None = None,
    repetitions: int = 1,
    target: SessionTargetFact | None = None,
    recovery_seconds: int | None = None,
    recovery_target: SessionTargetFact | None = None,
    instruction: str,
) -> WorkoutStepFact:
    return WorkoutStepFact(
        kind=kind,
        repetitions=repetitions,
        distance_meters=distance_meters,
        duration_seconds=None if minutes is None else minutes * 60,
        target=target or _no_target(),
        recovery_distance_meters=None,
        recovery_duration_seconds=recovery_seconds,
        recovery_target=recovery_target,
        instruction=instruction,
    )


def _session(
    session_id: int,
    day: date,
    sport: str,
    purpose: str,
    minutes: int,
    target_display: str,
    steps: tuple[WorkoutStepFact, ...],
    *,
    distance_km: float | None = None,
    outcome: str | None = None,
    rpe: int | None = None,
) -> PlanSessionFact:
    return PlanSessionFact(
        id=session_id,
        scheduled_date=day,
        sport_type=sport,
        purpose=purpose,
        distance_meters=None if distance_km is None else distance_km * 1_000,
        duration_seconds=minutes * 60,
        heart_rate_zone=2 if sport == "ride" else None,
        target=_rpe(2, 4),
        target_display=target_display,
        feedback_outcome=outcome,
        feedback_perceived_exertion=rpe,
        feedback_reason_code=None,
        workout_steps=steps,
    )


PLAN = TrainingPlanFact(
    id=12,
    parent_plan_id=11,
    status="accepted",
    contract_version=6,
    goal_mode="race",
    race_id=4,
    as_of_date=TODAY,
    block_start_date=TODAY,
    block_end_date=date(2026, 10, 11),
    detailed_start_date=TODAY,
    detailed_end_date=date(2026, 9, 28),
    block_outline=(
        {
            "week_start": "2026-09-15",
            "week_end": "2026-09-21",
            "focus": "Re-establish steady frequency and introduce controlled 10 km work.",
        },
        {
            "week_start": "2026-09-22",
            "week_end": "2026-09-28",
            "focus": "Build race-specific endurance while keeping most work aerobic.",
        },
        {
            "week_start": "2026-09-29",
            "week_end": "2026-10-05",
            "focus": "Final specific work supported by the completed training response.",
        },
        {
            "week_start": "2026-10-06",
            "week_end": "2026-10-11",
            "focus": "Full taper into the A-priority 10 km race.",
        },
    ),
    sessions=(
        _session(
            101,
            date(2026, 9, 15),
            "run",
            "Easy aerobic running with relaxed strides.",
            45,
            "RPE 2–4",
            (
                _step(
                    "steady",
                    minutes=38,
                    target=_rpe(2, 3),
                    instruction="Run easily enough to keep breathing controlled.",
                ),
                _step(
                    "interval",
                    minutes=1,
                    repetitions=4,
                    target=_rpe(6, 7),
                    recovery_seconds=60,
                    recovery_target=_rpe(1, 2),
                    instruction="Fast and relaxed, never sprinting.",
                ),
            ),
            distance_km=8.0,
            outcome="completed",
            rpe=3,
        ),
        _session(
            102,
            date(2026, 9, 17),
            "ride",
            "Aerobic cycling that supports running without impact load.",
            75,
            "Z2 (119–138 bpm)",
            (
                _step(
                    "steady",
                    minutes=75,
                    target=_rpe(2, 3),
                    instruction="Keep pressure even and avoid hard surges on climbs.",
                ),
            ),
            distance_km=30.0,
        ),
        _session(
            103,
            date(2026, 9, 19),
            "run",
            "Controlled 10 km-specific cruise intervals.",
            60,
            "RPE 3–7",
            (
                _step(
                    "warmup",
                    minutes=15,
                    target=_rpe(2, 3),
                    instruction="Finish with three relaxed accelerations.",
                ),
                _step(
                    "interval",
                    distance_meters=1_000,
                    repetitions=5,
                    target=_rpe(7, 7),
                    recovery_seconds=90,
                    recovery_target=_rpe(1, 2),
                    instruction="Even repetitions with one controlled gear left.",
                ),
                _step(
                    "cooldown",
                    minutes=12,
                    target=_rpe(2, 2),
                    instruction="Jog until breathing is fully settled.",
                ),
            ),
            distance_km=11.0,
        ),
        _session(
            104,
            date(2026, 9, 21),
            "run",
            "Long easy run for durable aerobic volume.",
            75,
            "RPE 2–3",
            (
                _step(
                    "steady",
                    minutes=75,
                    target=_rpe(2, 3),
                    instruction="Keep the final 20 minutes as patient as the first 20.",
                ),
            ),
            distance_km=13.0,
        ),
        _session(
            105,
            date(2026, 9, 23),
            "run",
            "Easy recovery run between key sessions.",
            40,
            "RPE 2–3",
            (
                _step(
                    "steady",
                    minutes=40,
                    target=_rpe(2, 3),
                    instruction="No progression and no pace target.",
                ),
            ),
            distance_km=7.0,
        ),
        _session(
            106,
            date(2026, 9, 25),
            "ride",
            "Steady aerobic ride with controlled tempo blocks.",
            90,
            "Z2–Z3 (119–158 bpm)",
            (
                _step(
                    "warmup",
                    minutes=15,
                    target=_rpe(2, 3),
                    instruction="Build gradually into Garmin zone 2.",
                ),
                _step(
                    "interval",
                    minutes=10,
                    repetitions=3,
                    target=_rpe(5, 6),
                    recovery_seconds=300,
                    recovery_target=_rpe(2, 3),
                    instruction="Ride in zone 3 without turning it into a threshold test.",
                ),
                _step(
                    "cooldown",
                    minutes=15,
                    target=_rpe(2, 2),
                    instruction="Finish very easily.",
                ),
            ),
            distance_km=38.0,
        ),
        _session(
            107,
            date(2026, 9, 27),
            "run",
            "Progressive aerobic run with a controlled finish.",
            65,
            "RPE 3–6",
            (
                _step(
                    "steady",
                    minutes=45,
                    target=_rpe(3, 4),
                    instruction="Comfortable aerobic running.",
                ),
                _step(
                    "steady",
                    minutes=20,
                    target=_rpe(5, 6),
                    instruction="Progress only if form remains smooth.",
                ),
            ),
            distance_km=12.0,
        ),
    ),
    coach_assessment=CoachAssessmentFact(
        fact_references=(
            "goal",
            "capacity_profile",
            "training_preference",
            "feedback",
            "relevant_context",
        ),
        observed_facts=(
            "Running continuity is established across the multi-horizon history.",
            "The selected goal is an A-priority 10 km race on 11 October.",
        ),
        inferences=(
            "One controlled running-quality session is supported in the first week.",
            "Cycling can add aerobic work without replacing race-specific running.",
        ),
        rationale=(
            "The plan uses the athlete's established frequency rather than one flattering "
            "week. It adds 10 km-specific work gradually, keeps most training controlled, "
            "and preserves cycling as complementary aerobic volume."
        ),
        uncertainties=(
            "No verified current race pace is used; quality is prescribed by RPE.",
        ),
        coaching_principles=(
            "Specificity follows demonstrated continuity.",
            "A high ambition setting permits work that the evidence supports; it does not create capacity.",
        ),
    ),
)


def _activity(day: date, sport: str, minutes: int) -> SimpleNamespace:
    return SimpleNamespace(
        sport_type=sport,
        start_time=datetime.combine(day, time(hour=7), tzinfo=timezone.utc),
        duration_seconds=minutes * 60,
    )


ACTIVITIES = tuple(
    _activity(TODAY - timedelta(days=days_ago), sport, minutes)
    for days_ago, sport, minutes in (
        (27, "run", 42),
        (25, "ride", 70),
        (23, "run", 50),
        (20, "run", 38),
        (18, "ride", 95),
        (16, "run", 64),
        (13, "run", 45),
        (11, "ride", 80),
        (9, "run", 58),
        (7, "run", 72),
        (5, "ride", 60),
        (3, "run", 48),
        (1, "run", 40),
        (0, "run", 45),
    )
)


RECOVERY = tuple(
    RecoveryDayObservation(
        date=TODAY - timedelta(days=27 - index),
        hrv_value=float(86 + (index * 3) % 13),
        resting_heart_rate=float(46 + (index * 2) % 5),
        sleep_duration_hours=round(7.2 + (index % 6) * 0.22, 2),
    )
    for index in range(28)
)


FEEDBACK = (
    FeedbackTrendRecord(TODAY - timedelta(days=23), "run", "completed", 6, None),
    FeedbackTrendRecord(TODAY - timedelta(days=18), "ride", "completed", 3, None),
    FeedbackTrendRecord(TODAY - timedelta(days=13), "run", "completed", 5, None),
    FeedbackTrendRecord(TODAY - timedelta(days=7), "run", "completed_limited", 7, "fatigue"),
    FeedbackTrendRecord(TODAY - timedelta(days=3), "run", "completed", 4, None),
    FeedbackTrendRecord(TODAY, "run", "completed", 3, None),
)


STATE = AthleteState(
    as_of_date=TODAY,
    metrics=SimpleNamespace(),
    relevant_context=AthleteContextWindow(
        TODAY - timedelta(days=6), TODAY, ()
    ),
    data_quality=AthleteStateDataQuality(
        SyncDataQuality(
            provider="garmin",
            completed_at=datetime(2026, 9, 15, 6, 30, tzinfo=timezone.utc),
            status="success",
            requested_start_date=TODAY - timedelta(days=6),
            requested_end_date=TODAY,
        ),
        tuple(
            RecoveryDataQuality(metric, 28, 28, 7, TODAY)
            for metric in ("hrv", "resting_heart_rate", "sleep_duration")
        ),
    ),
    recent_recovery_observations=RECOVERY[-7:],
    garmin_current_facts=(),
)


TRENDS = build_training_response_trends(as_of_date=TODAY, records=FEEDBACK)
ANALYSIS = TransparentTrainingAnalysis(
    start_date=TODAY - timedelta(days=27),
    end_date=TODAY,
    sports=(
        SportWindowAnalysis("run", 10, 10, 8.37, 91.4, 0),
        SportWindowAnalysis("ride", 4, 4, 5.08, 126.2, 0),
    ),
    total_duration_hours=13.45,
    total_active_days=14,
    feedback_records=6,
    reported_rpe_average=4.6,
    recovery_coverage=(
        ("hrv", 28, 28),
        ("resting_heart_rate", 28, 28),
        ("sleep_duration", 28, 28),
    ),
    limitations=("no_proprietary_training_load_score",),
)


class _PlanService:
    def list_plans(self):
        return (PLAN,)


def _read_only_demo(*_args, **_kwargs):
    raise ValueError("The synthetic product demo is read-only.")


SERVICES = WebServices(
    plan_service=_PlanService(),
    checkpoint_service=SimpleNamespace(
        get_checkpoint=lambda **_kwargs: PlanCheckpoint(
            as_of_date=TODAY,
            status="on_track",
            active_plan_id=PLAN.id,
            detailed_end_date=PLAN.detailed_end_date,
            detailed_days_remaining=(PLAN.detailed_end_date - TODAY).days,
            upcoming_races=(),
            reasons=(),
            recommended_command=None,
        )
    ),
    preference_service=SimpleNamespace(
        get_preference=lambda: SimpleNamespace(
            sport_role="run_primary",
            coaching_ambition="ambitious",
            available_days=[
                {"day": day, "minutes": None}
                for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
            ],
        )
    ),
    zone_service=SimpleNamespace(
        get_profile=lambda **_kwargs: SimpleNamespace(
            zones=[
                {"zone": 1, "lower_bpm": 99, "upper_bpm": 118},
                {"zone": 2, "lower_bpm": 119, "upper_bpm": 138},
                {"zone": 3, "lower_bpm": 139, "upper_bpm": 158},
                {"zone": 4, "lower_bpm": 159, "upper_bpm": 177},
                {"zone": 5, "lower_bpm": 178, "upper_bpm": 197},
            ]
        )
    ),
    personalization_service=SimpleNamespace(
        get_evidence=lambda **_kwargs: PersonalizationEvidence(
            as_of_date=TODAY,
            start_date=TODAY - timedelta(days=55),
            feedback_records=14,
            required_feedback_records=12,
            sport_feedback_records=(("run", 10), ("ride", 4)),
            sport_required_feedback_records=4,
            status="ready",
            limitations=("explicit_feedback_only",),
        )
    ),
    race_service=SimpleNamespace(
        list_upcoming_races=lambda **_kwargs: (
            SimpleNamespace(
                id=4,
                name="Autumn 10K",
                race_date=date(2026, 10, 11),
                sport_type="run",
                priority="A",
                taper_override=None,
                distance_meters=10_000,
            ),
        )
    ),
    analysis_service=SimpleNamespace(get_analysis=lambda **_kwargs: ANALYSIS),
    dashboard_service=SimpleNamespace(
        get_dashboard_data=lambda **_kwargs: SimpleNamespace(
            state=STATE,
            trends=TRENDS,
            plan=PLAN,
            activities=ACTIVITIES,
            recovery_observations=RECOVERY,
        )
    ),
    context_service=SimpleNamespace(add_event=_read_only_demo),
    reports_directory=DEMO_DIRECTORY,
    coach_service_factory=lambda: SimpleNamespace(ask=_read_only_demo),
    sync_service_factory=lambda: SimpleNamespace(sync=_read_only_demo),
    weekly_review_service_factory=lambda: SimpleNamespace(create=_read_only_demo),
    plan_generation_service_factory=lambda: SimpleNamespace(
        generate_draft=_read_only_demo,
        generate_revision=_read_only_demo,
    ),
    today=lambda: TODAY,
)

app = create_app(
    services=SERVICES,
    allowed_hosts=("127.0.0.1", "localhost", "testserver"),
)
