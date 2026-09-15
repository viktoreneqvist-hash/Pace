"""Reviewed synthetic scenarios; no real athlete history or credentials."""

from pace.coach_evaluation.models import CoachEvaluationScenario


def load_scenarios() -> tuple[CoachEvaluationScenario, ...]:
    return (
        _scenario(
            "limited_run_continuity",
            "Low running continuity before an A race must not create verified pace targets.",
            allowed_sports=("run", "ride"),
            allowed_targets=("rpe", "none"),
            facts={"run_recent_activities": 1, "race_priority": "A", "ambition": "ambitious"},
        ),
        _scenario(
            "b_race_in_window",
            "A B race in the detailed window must be visible without becoming a new A goal.",
            allowed_sports=("run", "ride"),
            allowed_targets=("rpe", "none"),
            facts={"race_priority": "B", "resolved_taper": "partial"},
        ),
        _scenario(
            "missed_quality_session",
            "A missed quality session must not be compensated with automatic extra intensity.",
            allowed_sports=("run", "ride"),
            allowed_targets=("rpe", "none"),
            facts={"feedback_outcome": "skipped", "reason_code": "schedule"},
        ),
        _scenario(
            "ride_hr_zone_without_power",
            "Cycling with confirmed zones but no power test must not receive watt or pace targets.",
            allowed_sports=("ride",),
            allowed_targets=("rpe", "none"),
            facts={"ride_hr_zones": [1, 2, 3, 4, 5], "power_evidence": False},
        ),
        _scenario(
            "verified_run_quality",
            "Current verified running evidence may support a structured quality session.",
            allowed_sports=("run",),
            allowed_targets=("rpe", "pace", "none"),
            facts={"run_recent_activities": 4, "run_pace_evidence": True},
        ),
        _scenario(
            "insufficient_feedback_personalization",
            "Sparse feedback must not be presented as a stable personal profile.",
            allowed_sports=("run", "ride"),
            allowed_targets=("rpe", "none"),
            facts={"feedback_records": 2, "personalization_status": "insufficient_data"},
        ),
    )


def _scenario(
    scenario_id: str,
    description: str,
    *,
    allowed_sports: tuple[str, ...],
    allowed_targets: tuple[str, ...],
    facts: dict[str, object],
) -> CoachEvaluationScenario:
    return CoachEvaluationScenario(
        scenario_id=scenario_id,
        description=description,
        context={
            "fact_catalog": {
                "goal": {"provenance": "synthetic_explicit", "value": facts},
                "planning_readiness": {
                    "provenance": "synthetic_python_derived",
                    "value": {"status": "ready"},
                },
                "evaluation_boundary": {
                    "provenance": "synthetic_test_contract",
                    "value": {
                        "allowed_sports": list(allowed_sports),
                        "allowed_target_kinds": list(allowed_targets),
                    },
                },
            },
            "knowledge_briefs": {"library_schema_version": 1, "briefs": []},
        },
        allowed_sports=allowed_sports,
        allowed_target_kinds=allowed_targets,
    )
