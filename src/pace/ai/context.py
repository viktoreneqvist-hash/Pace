"""Build the minimized, auditable data contract for Pace AI assistance."""

from dataclasses import asdict
from datetime import date
from typing import Any

from pace.explanations.models import ExplanationSummary
from pace.rules.models import RuleEvaluationSummary
from pace.state.models import AthleteState


AI_CONTEXT_SCHEMA_VERSION = 2


def build_ai_context(
    *,
    athlete_state: AthleteState,
    rule_summary: RuleEvaluationSummary,
    explanation: ExplanationSummary,
    knowledge_briefs: dict[str, object],
) -> dict[str, object]:
    """Return selected Pace facts without provider payloads or context-note text."""

    return {
        "schema_version": AI_CONTEXT_SCHEMA_VERSION,
        "as_of_date": athlete_state.as_of_date.isoformat(),
        "metrics": serialize_pace_facts(asdict(athlete_state.metrics)),
        "relevant_context": {
            "start_date": athlete_state.relevant_context.start_date.isoformat(),
            "end_date": athlete_state.relevant_context.end_date.isoformat(),
            "events": [
                {
                    "event_type": event.event_type,
                    "start_date": event.start_date.isoformat(),
                    "end_date": serialize_pace_facts(event.end_date),
                    "status": event.status,
                }
                for event in athlete_state.relevant_context.events
            ],
        },
        "data_quality": serialize_pace_facts(asdict(athlete_state.data_quality)),
        "garmin_current_facts": serialize_pace_facts(
            [asdict(fact) for fact in athlete_state.garmin_current_facts]
        ),
        "rule_evaluations": serialize_pace_facts(
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
        "knowledge_briefs": knowledge_briefs,
    }


def serialize_pace_facts(value: Any) -> Any:
    """Convert Pace facts to JSON-compatible primitives before an AI boundary."""

    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize_pace_facts(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_pace_facts(item) for item in value]
    return value
