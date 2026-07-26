"""Build the minimized, auditable data contract for Pace AI assistance."""

from dataclasses import asdict
from datetime import date
from typing import Any

from pace.explanations.models import ExplanationSummary
from pace.rules.models import RuleEvaluationSummary
from pace.state.models import AthleteState


AI_CONTEXT_SCHEMA_VERSION = 1


def build_ai_context(
    *,
    athlete_state: AthleteState,
    rule_summary: RuleEvaluationSummary,
    explanation: ExplanationSummary,
) -> dict[str, object]:
    """Return selected Pace facts without provider payloads or context-note text."""

    return {
        "schema_version": AI_CONTEXT_SCHEMA_VERSION,
        "as_of_date": athlete_state.as_of_date.isoformat(),
        "metrics": _serialize(asdict(athlete_state.metrics)),
        "relevant_context": {
            "start_date": athlete_state.relevant_context.start_date.isoformat(),
            "end_date": athlete_state.relevant_context.end_date.isoformat(),
            "events": [
                {
                    "event_type": event.event_type,
                    "start_date": event.start_date.isoformat(),
                    "end_date": _serialize(event.end_date),
                    "status": event.status,
                }
                for event in athlete_state.relevant_context.events
            ],
        },
        "data_quality": _serialize(asdict(athlete_state.data_quality)),
        "garmin_current_facts": _serialize(
            [asdict(fact) for fact in athlete_state.garmin_current_facts]
        ),
        "rule_evaluations": _serialize(
            [asdict(evaluation) for evaluation in rule_summary.evaluations]
        ),
        "deterministic_explanations": {
            "items": [item.text for item in explanation.items],
            "context_check_in": (
                None
                if explanation.context_check_in is None
                else {
                    "question": explanation.context_check_in.question,
                    "suggested_event_types": list(
                        explanation.context_check_in.suggested_event_types
                    ),
                }
            ),
        },
    }


def _serialize(value: Any) -> Any:
    """Convert dataclass-shaped Pace facts to JSON-compatible primitives."""

    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value
