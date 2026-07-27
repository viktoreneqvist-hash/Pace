"""Typed results for explicit synthetic coach evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CoachEvaluationScenario:
    scenario_id: str
    description: str
    context: dict[str, object]
    allowed_sports: tuple[str, ...]
    allowed_target_kinds: tuple[str, ...]
    require_structured_steps: bool = True


@dataclass(frozen=True, slots=True)
class ScenarioEvaluationResult:
    scenario_id: str
    status: str
    violations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CoachEvaluationReport:
    scenario_count: int
    passed: int
    failed: int
    results: tuple[ScenarioEvaluationResult, ...]
