from types import SimpleNamespace

import pytest

from pace.ai.client import (
    ANSWER_SCHEMA,
    MAX_OUTPUT_TOKENS,
    REASONING_EFFORT,
    OpenAIResponsesClient,
    PaceAIResponseError,
)
from pace.ai.models import PaceAIRequest


class FakeResponses:
    def __init__(self, response):
        self._response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


def test_responses_client_uses_one_stateless_structured_request_without_tools():
    responses = FakeResponses(
        SimpleNamespace(
            output_text=(
                '{"answer":"Svar.","observations":["Fakta."],'
                '"uncertainties":["Begränsning."],"context_event_draft":null,'
                '"knowledge_references":[]}'
            )
        )
    )
    client = OpenAIResponsesClient(
        api_key="test-key",
        model="test-model",
        client=SimpleNamespace(responses=responses),
    )

    answer = client.answer(
        PaceAIRequest(question="Hur ser läget ut?", context={"as_of_date": "2026-07-25"})
    )

    assert answer.answer == "Svar."
    assert answer.context_event_draft is None
    assert responses.kwargs is not None
    assert responses.kwargs["model"] == "test-model"
    assert responses.kwargs["reasoning"] == {"effort": REASONING_EFFORT}
    assert responses.kwargs["store"] is False
    assert responses.kwargs["max_output_tokens"] == MAX_OUTPUT_TOKENS
    assert responses.kwargs["text"]["format"]["schema"] == ANSWER_SCHEMA
    assert "tools" not in responses.kwargs
    assert "Hur ser läget ut?" in responses.kwargs["input"]


def test_responses_client_rejects_an_invalid_unsaved_context_draft():
    responses = FakeResponses(
        SimpleNamespace(
            output_text=(
                '{"answer":"Svar.","observations":[],"uncertainties":[],'
                '"context_event_draft":{"event_type":"alcohol",'
                '"start_date":"2026-07-25","end_date":"2026-07-24",'
                '"ongoing":false,"note":"Sent."},"knowledge_references":[]}'
            )
        )
    )
    client = OpenAIResponsesClient(
        api_key="test-key",
        client=SimpleNamespace(responses=responses),
    )

    with pytest.raises(PaceAIResponseError, match="end date"):
        client.answer(PaceAIRequest(question="Test", context={}))


def test_responses_client_discards_an_unselected_knowledge_reference():
    responses = FakeResponses(
        SimpleNamespace(
            output_text=(
                '{"answer":"Svar.","observations":[],"uncertainties":[],'
                '"context_event_draft":null,"knowledge_references":["unknown"]}'
            )
        )
    )
    client = OpenAIResponsesClient(
        api_key="test-key",
        client=SimpleNamespace(responses=responses),
    )

    answer = client.answer(
        PaceAIRequest(
            question="Test",
            context={"knowledge_briefs": {"briefs": [{"id": "known"}]}},
        )
    )

    assert answer.knowledge_references == ()
