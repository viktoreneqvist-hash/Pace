from datetime import UTC, date, datetime
import json

from pace.ai.context import AI_CONTEXT_SCHEMA_VERSION, build_ai_context
from pace.database.models import Activity, ContextEvent, DailyMetric
from pace.database.session import session_scope
from pace.services.athlete_state_service import AthleteStateService
from pace.services.explanation_service import ExplanationService
from pace.services.rule_service import RuleService


def test_ai_context_contains_selected_facts_but_never_context_note_text_or_raw_payloads():
    with session_scope() as session:
        session.add_all(
            [
                Activity(
                    provider="test",
                    provider_activity_id="run-1",
                    sport_type="run",
                    start_time=datetime(2026, 7, 25, 7, tzinfo=UTC),
                    distance_meters=10_000,
                    duration_seconds=3_600,
                    raw_payload={"private_provider_value": "never send this"},
                ),
                DailyMetric(
                    date=date(2026, 7, 25),
                    hrv_value=55,
                    raw_payload={"private_daily_value": "never send this"},
                ),
                ContextEvent(
                    event_type="travel",
                    start_date=date(2026, 7, 25),
                    end_date=date(2026, 7, 25),
                    note="Private context note that must never leave Pace.",
                    affected_metrics=[],
                    status="closed",
                ),
            ]
        )

    athlete_state = AthleteStateService().get_state(end_date=date(2026, 7, 25))
    rule_summary = RuleService().evaluate_state(athlete_state)
    explanation = ExplanationService().explain_state(
        athlete_state=athlete_state,
        rule_summary=rule_summary,
    )

    context = build_ai_context(
        athlete_state=athlete_state,
        rule_summary=rule_summary,
        explanation=explanation,
    )
    serialized_context = json.dumps(context)

    assert context["schema_version"] == AI_CONTEXT_SCHEMA_VERSION
    assert context["as_of_date"] == "2026-07-25"
    assert context["relevant_context"]["events"] == [
        {
            "event_type": "travel",
            "start_date": "2026-07-25",
            "end_date": "2026-07-25",
            "status": "closed",
        }
    ]
    assert "Private context note" not in serialized_context
    assert "private_provider_value" not in serialized_context
    assert "private_daily_value" not in serialized_context
