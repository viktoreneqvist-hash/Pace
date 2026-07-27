from types import SimpleNamespace
import json

from pace.coach.client import COACH_DIALOGUE_SCHEMA, OpenAICoachDialogueClient
from pace.coach.models import CoachDialogueRequest


class FakeResponses:
    def __init__(self, response) -> None:
        self._response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


def _replacement_payload(*, knowledge_references=None) -> str:
    references = ["progression_continuity"] if knowledge_references is None else knowledge_references
    return json.dumps(
        {
            "answer": "Byt passet i dag.",
            "observations": ["Fakta."],
            "uncertainties": ["Begränsning."],
            "knowledge_references": references,
            "context_event_draft": None,
            "feedback_draft": None,
            "adjustment_draft": {
                "action": "replace",
                "replaces_session_id": 4,
                "rationale": "Passar dagens fakta.",
                "proposed_session": {
                    "scheduled_date": "2026-07-26",
                    "sport_type": "run",
                    "purpose": "Lugn löpning.",
                    "distance_meters": 5000,
                    "duration_seconds": 1800,
                    "heart_rate_zone": None,
                    "target": {
                        "kind": "rpe",
                        "rpe_min": 2,
                        "rpe_max": 3,
                        "pace_seconds_per_km": None,
                        "power_watts": None,
                        "evidence_reference_id": None,
                    },
                    "workout_steps": [
                        {
                            "kind": "steady",
                            "repetitions": 1,
                            "distance_meters": 5000,
                            "duration_seconds": 1800,
                            "target": {
                                "kind": "rpe",
                                "rpe_min": 2,
                                "rpe_max": 3,
                                "pace_seconds_per_km": None,
                                "power_watts": None,
                                "evidence_reference_id": None,
                            },
                            "recovery_distance_meters": None,
                            "recovery_duration_seconds": None,
                            "recovery_target": None,
                            "instruction": "Lugnt och kontrollerat.",
                        }
                    ],
                },
            },
        }
    )


def _request() -> CoachDialogueRequest:
    return CoachDialogueRequest(
        question="Kan jag byta?",
        context={"knowledge_briefs": {"briefs": [{"id": "progression_continuity"}]}},
        conversation=({"role": "athlete", "text": "Tidigare fråga."},),
    )


def test_coach_client_uses_a_stateless_structured_request_and_parses_replacement():
    responses = FakeResponses(SimpleNamespace(output_text=_replacement_payload()))
    client = OpenAICoachDialogueClient(
        api_key="test-key",
        model="test-model",
        client=SimpleNamespace(responses=responses),
    )

    answer = client.answer(_request())

    assert answer.adjustment_draft is not None
    assert answer.adjustment_draft.action == "replace"
    assert answer.adjustment_draft.proposed_session is not None
    assert answer.adjustment_draft.proposed_session.target.rpe_max == 3
    assert responses.kwargs["store"] is False
    assert responses.kwargs["text"]["format"]["schema"] == COACH_DIALOGUE_SCHEMA
    assert len(COACH_DIALOGUE_SCHEMA["required"]) == len(
        set(COACH_DIALOGUE_SCHEMA["required"])
    )
    assert "Tidigare fråga." in responses.kwargs["input"]


def test_coach_client_discards_an_unselected_knowledge_reference():
    responses = FakeResponses(
        SimpleNamespace(output_text=_replacement_payload(knowledge_references=["unknown"]))
    )
    client = OpenAICoachDialogueClient(
        api_key="test-key",
        model="test-model",
        client=SimpleNamespace(responses=responses),
    )

    answer = client.answer(_request())

    assert answer.knowledge_references == ()
