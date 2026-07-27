from datetime import date, datetime, timezone

from pace.database.models import Activity, PlannedSession, SessionFeedback, TrainingPlan
from pace.database.session import session_scope
from pace.services.workout_evaluation_service import WorkoutEvaluationService


def _target() -> dict[str, object]:
    return {
        "kind": "rpe",
        "rpe_min": 7,
        "rpe_max": 8,
        "pace_seconds_per_km": None,
        "power_watts": None,
        "evidence_reference_id": None,
    }


def test_workout_evaluation_keeps_feedback_authoritative_and_garmin_only_a_candidate():
    with session_scope() as session:
        plan = TrainingPlan(
            status="accepted",
            contract_version=3,
            goal_mode="general",
            race_id=None,
            as_of_date=date(2026, 7, 26),
            block_start_date=date(2026, 7, 26),
            block_end_date=date(2026, 8, 22),
            detailed_start_date=date(2026, 7, 26),
            detailed_end_date=date(2026, 8, 8),
            block_outline=[],
            context_snapshot={},
            coach_assessment={},
        )
        session.add(plan)
        session.flush()
        planned = PlannedSession(
            plan_id=plan.id,
            scheduled_date=date(2026, 7, 27),
            sport_type="run",
            purpose="10 × 1 km.",
            distance_meters=14_000,
            duration_seconds=4_800,
            intensity_type="rpe",
            intensity_zone=None,
            intensity_target="RPE 7–8",
            heart_rate_zone=None,
            target=_target(),
            workout_steps=[
                {
                    "kind": "interval",
                    "repetitions": 10,
                    "distance_meters": 1_000,
                    "duration_seconds": None,
                    "target": _target(),
                    "recovery_distance_meters": None,
                    "recovery_duration_seconds": 90,
                    "recovery_target": {
                        "kind": "rpe",
                        "rpe_min": 2,
                        "rpe_max": 3,
                        "pace_seconds_per_km": None,
                        "power_watts": None,
                        "evidence_reference_id": None,
                    },
                    "instruction": "Jämnt och kontrollerat.",
                }
            ],
        )
        session.add(planned)
        session.flush()
        session.add(
            SessionFeedback(
                planned_session_id=planned.id,
                outcome="completed_limited",
                perceived_exertion=9,
                reason_code="fatigue",
                note="Privat.",
                share_note_with_ai=False,
            )
        )
        session.add(
            Activity(
                provider="garmin",
                provider_activity_id="candidate-1",
                name="Löpning",
                sport_type="run",
                start_time=datetime(2026, 7, 27, 8, tzinfo=timezone.utc),
                duration_seconds=4_000,
                distance_meters=12_000,
                elevation_gain_meters=None,
                average_heart_rate=None,
                maximum_heart_rate=None,
                average_speed_mps=None,
                average_cadence=None,
                average_power=None,
                training_effect_aerobic=None,
                training_effect_anaerobic=None,
                raw_payload={},
            )
        )
        session_id = planned.id

    evaluation = WorkoutEvaluationService().evaluate(session_id=session_id)

    assert evaluation.feedback_outcome == "completed_limited"
    assert evaluation.feedback_perceived_exertion == 9
    assert evaluation.planned_steps[0].repetitions == 10
    assert evaluation.matching_activities[0].provider_activity_id == "candidate-1"
    assert "garmin_match_is_not_proof_of_step_completion" in evaluation.limitations
    assert "explicit_feedback_missing" not in evaluation.limitations
