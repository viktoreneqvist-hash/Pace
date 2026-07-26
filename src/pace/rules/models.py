"""Typed, auditable outputs from Pace's deterministic rule layer."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    """One transparent rule outcome with its machine-readable evidence."""

    rule_id: str
    status: str
    facts: dict[str, object]
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuleEvaluationSummary:
    """Every first-slice rule evaluated for one athlete-state date."""

    as_of_date: date
    evaluations: tuple[RuleEvaluation, ...]
