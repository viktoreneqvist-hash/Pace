"""Run explicit synthetic coach checks without touching local athlete state."""

from pace.coach_evaluation.models import (
    CoachEvaluationReport,
    ScenarioEvaluationResult,
)
from pace.coach_evaluation.scenarios import load_scenarios
from pace.planning.draft_models import PlanGenerationRequest


class CoachEvaluationService:
    def evaluate(self, *, generator) -> CoachEvaluationReport:
        results = []
        for scenario in load_scenarios():
            try:
                generated = generator.generate(
                    PlanGenerationRequest(
                        mode="synthetic_evaluation",
                        context=scenario.context,
                    )
                )
                violations = _violations(scenario=scenario, generated=generated)
            except Exception as error:
                violations = (f"generation_error:{type(error).__name__}",)
            results.append(
                ScenarioEvaluationResult(
                    scenario_id=scenario.scenario_id,
                    status="passed" if not violations else "failed",
                    violations=tuple(violations),
                )
            )
        passed = sum(item.status == "passed" for item in results)
        return CoachEvaluationReport(
            scenario_count=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=tuple(results),
        )


def _violations(*, scenario, generated) -> tuple[str, ...]:
    violations = []
    if not generated.sessions:
        violations.append("no_sessions")
    for session in generated.sessions:
        if session.sport_type not in scenario.allowed_sports:
            violations.append(f"unsupported_sport:{session.sport_type}")
        if session.target.kind not in scenario.allowed_target_kinds:
            violations.append(f"unsupported_target:{session.target.kind}")
        if scenario.require_structured_steps and not session.workout_steps:
            violations.append("missing_workout_steps")
        for step in session.workout_steps:
            if step.target.kind not in scenario.allowed_target_kinds:
                violations.append(f"unsupported_step_target:{step.target.kind}")
            if (
                step.recovery_target is not None
                and step.recovery_target.kind not in scenario.allowed_target_kinds
            ):
                violations.append(
                    f"unsupported_recovery_target:{step.recovery_target.kind}"
                )
    return tuple(sorted(set(violations)))
