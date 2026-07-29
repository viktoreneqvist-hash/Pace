from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from pace.database.session import SessionFactory, session_scope
from pace.performance.models import (
    IntensityEvidenceFact,
    PerformanceReadiness,
    SportPerformanceReadiness,
)
from pace.planning.draft_models import (
    BlockOutlineItem,
    CoachAssessmentDraft,
    GeneratedPlanDraft,
    PlanGenerationRequest,
    PlannedSessionDraft,
    SessionTargetDraft,
)
from pace.planning.models import HistoryCoverage, PlanReadiness
from pace.repositories.training_plan_repository import get_training_plan, list_training_plans
from pace.services.training_plan_service import (
    TrainingPlanService,
    _validate_races_in_detailed_window,
)
from pace.services.race_service import RaceInput, RaceService
from pace.services.training_preference_service import _parse_available_days


class StubGenerator:
    def __init__(self, generated: GeneratedPlanDraft) -> None:
        self.generated = generated
        self.requests: list[PlanGenerationRequest] = []

    def generate(self, request: PlanGenerationRequest) -> GeneratedPlanDraft:
        self.requests.append(request)
        return self.generated


class SequenceGenerator:
    def __init__(self, generated: list[GeneratedPlanDraft]) -> None:
        self.generated = generated
        self.requests: list[PlanGenerationRequest] = []

    def generate(self, request: PlanGenerationRequest) -> GeneratedPlanDraft:
        self.requests.append(request)
        return self.generated.pop(0)


class StubPlanReadinessService:
    def get_readiness(self, *, as_of_date: date) -> PlanReadiness:
        return PlanReadiness(
            as_of_date=as_of_date,
            status="ready",
            history=HistoryCoverage(
                28,
                28,
                date(2026, 6, 28),
                date(2026, 6, 28),
                date(2026, 7, 25),
                True,
            ),
            upcoming_races=(),
            blockers=(),
            limitations=(),
        )


@dataclass
class StubCapacity:
    as_of_date: date
    source: str


class StubCapacityService:
    def get_profile(self, *, end_date: date):
        return StubCapacity(as_of_date=end_date, source="synthetic")


class StubPreferenceService:
    def __init__(self, available_days=None) -> None:
        self.available_days = available_days or [{"day": "mon", "minutes": None}]

    def get_preference(self):
        return SimpleNamespace(
            sport_role="run_primary",
            available_days=self.available_days,
        )


class StubPerformanceService:
    def __init__(self, *, run_intensity_allowed: bool) -> None:
        self.run_intensity_allowed = run_intensity_allowed

    def get_readiness(self, *, end_date: date) -> PerformanceReadiness:
        run_evidence = (
            IntensityEvidenceFact(
                reference_id="performance.run.benchmark.run-evidence",
                sport_type="run",
                evidence_type="benchmark",
                protocol="run_5k_time_trial",
                activity_date=date(2026, 7, 1),
                duration_seconds=1_500,
                distance_meters=5_000,
                average_speed_mps=3.33,
                qualifying_power_watts=None,
            ),
        ) if self.run_intensity_allowed else ()
        return PerformanceReadiness(
            as_of_date=end_date,
            evidence_start_date=date(2026, 5, 4),
            history=HistoryCoverage(
                28,
                28,
                date(2026, 6, 28),
                date(2026, 6, 28),
                date(2026, 7, 25),
                True,
            ),
            planning_blockers=(),
            sports=(
                SportPerformanceReadiness(
                    sport_type="run",
                    status=(
                        "ready_for_intensity_target"
                        if self.run_intensity_allowed
                        else "general_plan_only"
                    ),
                    verified_evidence_count=1,
                    latest_evidence_date=date(2026, 7, 1),
                    recent_activity_count=2,
                    required_recent_activity_count=2,
                    can_propose_intensity_target=self.run_intensity_allowed,
                    limitations=(),
                    allowed_intensity_types=(
                        ("none", "pace", "rpe")
                        if self.run_intensity_allowed
                        else ("none", "rpe")
                    ),
                    intensity_evidence=run_evidence,
                ),
                SportPerformanceReadiness(
                    sport_type="ride",
                    status="general_plan_only",
                    verified_evidence_count=0,
                    latest_evidence_date=None,
                    recent_activity_count=0,
                    required_recent_activity_count=2,
                    can_propose_intensity_target=False,
                    limitations=("no_verified_evidence_in_last_12_weeks",),
                ),
            ),
        )


def _assessment(*, fact_references: tuple[str, ...] = ("planning_readiness",)):
    return CoachAssessmentDraft(
        fact_references=fact_references,
        inferences=("Lugn löpning är rimlig i utkastet.",),
        rationale="Förslaget prioriterar kontinuitet.",
        uncertainties=("Underlaget är syntetiskt i detta test.",),
        coaching_principles=("Gradvis progression.",),
        knowledge_references=(),
    )


def _target(kind: str = "rpe") -> SessionTargetDraft:
    if kind == "pace":
        return SessionTargetDraft(
            kind="pace",
            rpe_min=None,
            rpe_max=None,
            pace_seconds_per_km=300,
            power_watts=None,
            evidence_reference_id="performance.run.benchmark.run-evidence",
        )
    return SessionTargetDraft(
        kind="rpe",
        rpe_min=2,
        rpe_max=3,
        pace_seconds_per_km=None,
        power_watts=None,
        evidence_reference_id=None,
    )


def _outline() -> tuple[BlockOutlineItem, ...]:
    return (
        BlockOutlineItem(date(2026, 7, 26), date(2026, 8, 1), "Lugn återgång."),
        BlockOutlineItem(date(2026, 8, 2), date(2026, 8, 8), "Bygg rytm."),
        BlockOutlineItem(date(2026, 8, 9), date(2026, 8, 15), "Behåll kontinuitet."),
        BlockOutlineItem(date(2026, 8, 16), date(2026, 8, 22), "Konsolidera."),
    )


def _generated_plan(*, target_kind: str = "rpe") -> GeneratedPlanDraft:
    return GeneratedPlanDraft(
        block_outline=_outline(),
        sessions=(
            PlannedSessionDraft(
                scheduled_date=date(2026, 7, 27),
                sport_type="run",
                purpose="Lugn kontinuitet.",
                distance_meters=5_000,
                duration_seconds=None,
                heart_rate_zone=None,
                target=_target(target_kind),
            ),
            PlannedSessionDraft(
                scheduled_date=date(2026, 8, 3),
                sport_type="run",
                purpose="Lugn kontinuitet.",
                distance_meters=5_000,
                duration_seconds=None,
                heart_rate_zone=None,
                target=_target(target_kind),
            ),
        ),
        coach_assessment=_assessment(),
    )


def _service(
    generator: StubGenerator,
    *,
    run_intensity_allowed: bool = False,
    available_days=None,
    performance_service=None,
):
    return TrainingPlanService(
        generator=generator,
        plan_readiness_service=StubPlanReadinessService(),
        capacity_service=StubCapacityService(),
        performance_service=performance_service
        or StubPerformanceService(run_intensity_allowed=run_intensity_allowed),
        preference_service=StubPreferenceService(available_days),
    )


def test_initial_plan_is_activated_after_validation_with_selected_fact_catalog_only():
    generator = StubGenerator(_generated_plan())

    plan = _service(generator).generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )

    assert plan.status == "accepted"
    assert plan.contract_version == 3
    assert plan.goal_mode == "general"
    assert plan.sessions[0].target.kind == "rpe"
    assert plan.sessions[0].target_display == "RPE 2–3"
    assert generator.requests[0].mode == "initial_draft"
    catalog = generator.requests[0].context["fact_catalog"]
    assert catalog["training_preference"]["value"]["sport_role"] == "run_primary"
    assert catalog["training_preference"]["value"]["coaching_ambition"] == "balanced"
    assert "note" not in str(catalog["relevant_context"])


def test_initial_plan_retries_one_python_rejected_ai_candidate():
    complete = _generated_plan()
    incomplete_outline = GeneratedPlanDraft(
        block_outline=(complete.block_outline[0],),
        sessions=complete.sessions,
        coach_assessment=complete.coach_assessment,
    )
    generator = SequenceGenerator([incomplete_outline, complete])

    plan = _service(generator).generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )

    assert plan.status == "accepted"
    assert len(generator.requests) == 2
    assert generator.requests[0].repair_instruction is None
    assert "block outline must cover" in generator.requests[1].repair_instruction


def test_plan_rejects_pace_without_python_intensity_eligibility_and_persists_nothing():
    generator = StubGenerator(_generated_plan(target_kind="pace"))

    with pytest.raises(ValueError, match="without run eligibility"):
        _service(generator).generate_draft(
            as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
        )

    with SessionFactory() as session:
        assert list_training_plans(session) == []


def test_plan_persists_a_complete_coach_assessment_separately_from_pace_facts():
    generated = _generated_plan()
    generator = StubGenerator(generated)

    plan = _service(generator).generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )

    assert plan.coach_assessment.rationale == "Förslaget prioriterar kontinuitet."
    assert plan.coach_assessment.fact_references == ("planning_readiness",)
    assert plan.coach_assessment.inferences == ("Lugn löpning är rimlig i utkastet.",)
    assert plan.coach_assessment.observed_facts[0].startswith('{"provenance"')


def test_plan_rejects_an_incomplete_or_unreferenced_assessment_before_persistence():
    generated = _generated_plan()
    incomplete = GeneratedPlanDraft(
        block_outline=generated.block_outline,
        sessions=generated.sessions,
        coach_assessment=CoachAssessmentDraft(fact_references=("planning_readiness",)),
    )
    with pytest.raises(ValueError, match="complete coach assessment"):
        _service(StubGenerator(incomplete)).generate_draft(
            as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
        )

    unknown_reference = GeneratedPlanDraft(
        block_outline=generated.block_outline,
        sessions=generated.sessions,
        coach_assessment=_assessment(fact_references=("not_a_pace_fact",)),
    )
    with pytest.raises(ValueError, match="outside the selected Pace fact catalog"):
        _service(StubGenerator(unknown_reference)).generate_draft(
            as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
        )

    unknown_knowledge_reference = GeneratedPlanDraft(
        block_outline=generated.block_outline,
        sessions=generated.sessions,
        coach_assessment=CoachAssessmentDraft(
            fact_references=("planning_readiness",),
            inferences=("En slutsats.",),
            rationale="En motivering.",
            uncertainties=("En osäkerhet.",),
            coaching_principles=("En princip.",),
            knowledge_references=("not_selected",),
        ),
    )
    with pytest.raises(ValueError, match="outside the selected knowledge briefs"):
        _service(StubGenerator(unknown_knowledge_reference)).generate_draft(
            as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
        )


def test_legacy_draft_cannot_be_accepted():
    service = _service(StubGenerator(_generated_plan()))
    plan = service.generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )
    with session_scope() as session:
        stored = get_training_plan(session, plan_id=plan.id)
        assert stored is not None
        stored.status = "draft"
        stored.contract_version = 1

    with pytest.raises(ValueError, match="Legacy draft"):
        service.accept_plan(plan_id=plan.id)


def test_feedback_creates_a_bounded_revision_without_overwriting_parent():
    generator = StubGenerator(_generated_plan())
    service = _service(generator)
    accepted = service.generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )
    service.add_feedback(
        session_id=accepted.sessions[0].id,
        outcome="completed_limited",
        perceived_exertion=7,
        reason_code="fatigue",
        note="Privat notering.",
        share_note_with_ai=False,
    )

    revision = service.generate_revision(
        plan_id=accepted.id,
        as_of_date=date(2026, 7, 26),
        detailed_days=14,
    )

    assert revision.status == "accepted"
    assert revision.parent_plan_id == accepted.id
    assert revision.block_start_date == accepted.block_start_date
    assert revision.block_end_date == accepted.block_end_date
    assert revision.block_outline == accepted.block_outline
    assert service.get_plan(plan_id=accepted.id).status == "superseded"
    assert generator.requests[-1].mode == "revision_draft"
    revision_catalog = generator.requests[-1].context["fact_catalog"]
    assert revision_catalog["feedback"]["value"][0]["note"] is None
    assert revision_catalog["feedback"]["value"][0]["perceived_exertion"] == 7
    assert revision_catalog["feedback"]["value"][0]["reason_code"] == "fatigue"
    assert revision_catalog["feedback"]["value"][0]["workout_steps"]
    assert revision_catalog["training_response_trends"]["value"]["status"] == "insufficient_data"
    assert "target" in revision_catalog["parent_plan"]["value"]["sessions"][0]


def test_feedback_rejects_rpe_or_reason_for_an_incompatible_outcome():
    service = _service(StubGenerator(_generated_plan()))
    accepted = service.generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )

    with pytest.raises(ValueError, match="RPE can only"):
        service.add_feedback(
            session_id=accepted.sessions[0].id,
            outcome="skipped",
            perceived_exertion=5,
        )
    with pytest.raises(ValueError, match="structured reason"):
        service.add_feedback(
            session_id=accepted.sessions[0].id,
            outcome="completed",
            reason_code="fatigue",
        )


def test_revision_replaces_its_parent_and_blocks_a_second_sibling_revision():
    service = _service(StubGenerator(_generated_plan()))
    accepted = service.generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )
    first = service.generate_revision(
        plan_id=accepted.id, as_of_date=date(2026, 7, 26), detailed_days=14
    )
    with pytest.raises(ValueError, match="Only an accepted"):
        service.generate_revision(
            plan_id=accepted.id, as_of_date=date(2026, 7, 26), detailed_days=14
        )
    assert service.get_plan(plan_id=accepted.id).status == "superseded"
    assert first.status == "accepted"


def test_new_validated_plan_supersedes_an_overlapping_active_plan_only_after_persistence():
    service = _service(StubGenerator(_generated_plan()))
    first = service.generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )
    second = service.generate_draft(
        as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
    )

    assert second.status == "accepted"
    assert service.get_plan(plan_id=first.id).status == "superseded"


def test_plan_rejects_an_outline_that_does_not_cover_the_entire_block():
    generated = _generated_plan()
    short_outline = GeneratedPlanDraft(
        block_outline=(generated.block_outline[0],),
        sessions=generated.sessions,
        coach_assessment=generated.coach_assessment,
    )
    with pytest.raises(ValueError, match="cover the full plan block"):
        _service(StubGenerator(short_outline)).generate_draft(
            as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
        )


def test_plan_requires_the_selected_target_race_inside_the_detailed_window():
    context = {
        "fact_catalog": {
            "detailed_window": {
                "provenance": "python_derived",
                "value": {
                    "start_date": "2026-07-26",
                    "end_date": "2026-08-08",
                },
            },
            "goal": {
                "provenance": "explicit_athlete_preference",
                "value": {
                    "race": {
                        "id": 7,
                        "name": "B-lopp",
                        "sport_type": "run",
                        "race_date": "2026-08-01",
                        "priority": "B",
                    }
                },
            },
        }
    }

    with pytest.raises(ValueError, match="omitted the selected target race"):
        _validate_races_in_detailed_window(
            generated=_generated_plan(),
            context=context,
        )


def test_general_plan_ignores_unselected_races_inside_the_detailed_window():
    context = {
        "fact_catalog": {
            "detailed_window": {
                "provenance": "python_derived",
                "value": {
                    "start_date": "2026-07-26",
                    "end_date": "2026-08-08",
                },
            },
            "goal": {
                "provenance": "explicit_athlete_preference",
                "value": {"goal_mode": "general", "race": None},
            },
            "planning_readiness": {
                "provenance": "python_derived",
                "value": {
                    "upcoming_races": [
                        {
                            "id": 7,
                            "name": "Lopp användaren inte valt",
                            "sport_type": "run",
                            "race_date": "2026-08-01",
                            "priority": "A",
                        }
                    ]
                },
            },
        }
    }

    _validate_races_in_detailed_window(generated=_generated_plan(), context=context)


@pytest.mark.parametrize(
    ("priority", "expected_taper"),
    (("B", "partial"), ("C", "none")),
)
def test_any_active_race_priority_can_be_an_explicit_plan_target(priority, expected_taper):
    race = RaceService().add_race(
        RaceInput(
            name=f"{priority}-lopp",
            sport_type="run",
            race_date=date(2026, 9, 1),
            distance_meters=10_000,
            priority=priority,
        )
    )

    goal = _service(StubGenerator(_generated_plan()))._resolve_goal(
        as_of_date=date(2026, 7, 26), race_id=race.id
    )

    assert goal["goal_mode"] == "race"
    assert goal["race_id"] == race.id
    assert goal["race"]["priority"] == priority
    assert goal["race"]["taper"] == expected_taper


def test_plan_enforces_available_days_and_time_caps_in_python():
    generated = _generated_plan()
    off_day_sessions = GeneratedPlanDraft(
        block_outline=generated.block_outline,
        sessions=(
            PlannedSessionDraft(
                scheduled_date=date(2026, 7, 28),
                sport_type="run",
                purpose="Otillgänglig dag.",
                distance_meters=5_000,
                duration_seconds=1_800,
                heart_rate_zone=None,
                target=_target(),
            ),
        ),
        coach_assessment=generated.coach_assessment,
    )
    with pytest.raises(ValueError, match="outside athlete availability"):
        _service(StubGenerator(off_day_sessions)).generate_draft(
            as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
        )

    capped_sessions = GeneratedPlanDraft(
        block_outline=generated.block_outline,
        sessions=(
            PlannedSessionDraft(
                scheduled_date=date(2026, 7, 27),
                sport_type="run",
                purpose="För långt för den valda dagen.",
                distance_meters=5_000,
                duration_seconds=1_860,
                heart_rate_zone=None,
                target=_target(),
            ),
        ),
        coach_assessment=generated.coach_assessment,
    )
    with pytest.raises(ValueError, match="exceeds athlete availability"):
        _service(
            StubGenerator(capped_sessions), available_days=[{"day": "mon", "minutes": 30}]
        ).generate_draft(as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None)


def test_availability_any_means_no_supplied_time_ceiling_not_a_numeric_limit():
    available_days = _parse_available_days(("mon:any", "sun:120"))

    assert available_days == [
        {"day": "mon", "minutes": None},
        {"day": "sun", "minutes": 120},
    ]


def test_plan_rejects_a_cycling_session_without_a_distance_target():
    generated = _generated_plan()
    generator = StubGenerator(
        GeneratedPlanDraft(
            block_outline=generated.block_outline,
            sessions=generated.sessions
            + (
                PlannedSessionDraft(
                    scheduled_date=date(2026, 7, 27),
                    sport_type="ride",
                    purpose="Cykelpass utan distans.",
                    distance_meters=None,
                    duration_seconds=3_600,
                    heart_rate_zone=1,
                    target=_target(),
                ),
            ),
            coach_assessment=generated.coach_assessment,
        )
    )

    with pytest.raises(ValueError, match="cycling plan session needs a distance"):
        _service(generator).generate_draft(
            as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None
        )


def test_cycle_power_and_a_configured_heart_rate_zone_can_be_combined():
    class RidePowerPerformanceService:
        def get_readiness(self, *, end_date: date) -> PerformanceReadiness:
            return PerformanceReadiness(
                as_of_date=end_date,
                evidence_start_date=date(2026, 5, 4),
                history=HistoryCoverage(
                    28,
                    28,
                    date(2026, 6, 28),
                    date(2026, 6, 28),
                    date(2026, 7, 25),
                    True,
                ),
                planning_blockers=(),
                sports=(
                    SportPerformanceReadiness(
                        sport_type="run",
                        status="general_plan_only",
                        verified_evidence_count=0,
                        latest_evidence_date=None,
                        recent_activity_count=0,
                        required_recent_activity_count=2,
                        can_propose_intensity_target=False,
                        limitations=(),
                    ),
                    SportPerformanceReadiness(
                        sport_type="ride",
                        status="ready_for_power_and_hr_zone_targets",
                        verified_evidence_count=1,
                        latest_evidence_date=date(2026, 7, 20),
                        recent_activity_count=2,
                        required_recent_activity_count=2,
                        can_propose_intensity_target=True,
                        limitations=(),
                        allowed_intensity_types=("hr_zone", "none", "power", "rpe"),
                        heart_rate_zones=(
                            {"zone": 1, "lower_bpm": 100, "upper_bpm": 120},
                            {"zone": 2, "lower_bpm": 121, "upper_bpm": 140},
                            {"zone": 3, "lower_bpm": 141, "upper_bpm": 155},
                            {"zone": 4, "lower_bpm": 156, "upper_bpm": 170},
                            {"zone": 5, "lower_bpm": 171, "upper_bpm": 190},
                        ),
                        intensity_evidence=(
                            IntensityEvidenceFact(
                                reference_id="performance.ride.benchmark.ride-power",
                                sport_type="ride",
                                evidence_type="benchmark",
                                protocol="ride_20min_power_test",
                                activity_date=date(2026, 7, 20),
                                duration_seconds=1_200,
                                distance_meters=9_000,
                                average_speed_mps=7.5,
                                qualifying_power_watts=250,
                            ),
                        ),
                    ),
                ),
            )

    power_target = SessionTargetDraft(
        kind="power",
        rpe_min=None,
        rpe_max=None,
        pace_seconds_per_km=None,
        power_watts=230,
        evidence_reference_id="performance.ride.benchmark.ride-power",
    )
    generated = GeneratedPlanDraft(
        block_outline=_outline(),
        sessions=(
            PlannedSessionDraft(
                scheduled_date=date(2026, 7, 27),
                sport_type="ride",
                purpose="Kontrollerat cykelpass med kvalitet.",
                distance_meters=30_000,
                duration_seconds=4_500,
                heart_rate_zone=3,
                target=power_target,
            ),
        ),
        coach_assessment=_assessment(fact_references=("performance_readiness",)),
    )

    plan = _service(
        StubGenerator(generated), performance_service=RidePowerPerformanceService()
    ).generate_draft(as_of_date=date(2026, 7, 26), detailed_days=14, race_id=None)

    assert plan.sessions[0].heart_rate_zone == 3
    assert plan.sessions[0].target.power_watts == 230
    assert plan.sessions[0].target_display == "Z3 (141–155 bpm) | 230 W"
