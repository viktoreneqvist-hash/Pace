"""Small OpenAI Responses boundary for Pace's read-only assistant."""

from datetime import date
import json
from typing import Any

from openai import OpenAI

from pace.ai.models import ContextEventDraft, PaceAIAnswer, PaceAIRequest
from pace.services.context_service import SUPPORTED_CONTEXT_EVENT_TYPES


MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 700


class PaceAIError(Exception):
    """Base error for a failed bounded Pace AI request."""


class PaceAIUnavailableError(PaceAIError):
    """The configured AI provider could not return a response."""


class PaceAIResponseError(PaceAIError):
    """The provider response was refused or violated the Pace output contract."""


SYSTEM_INSTRUCTIONS = """You are Pace's Swedish-language assistant for one athlete.
Use only the supplied Pace facts. Do not calculate, invent, or override metrics,
rules, dates, or data quality. Treat correlations as observations, never causes.
Do not diagnose health conditions or give training, medical, or safety advice.
Clearly acknowledge insufficient data. You cannot access Garmin, the local
database, previous conversations, or context-note text.

You may propose context_event_draft only when the athlete explicitly volunteers
new relevant context or explicitly asks to prepare a note. A draft is never
saved automatically and must be presented as requiring confirmation. Otherwise
return null for context_event_draft. Return Swedish JSON matching the schema."""


ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer",
        "observations",
        "uncertainties",
        "context_event_draft",
    ],
    "properties": {
        "answer": {"type": "string"},
        "observations": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "context_event_draft": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "event_type",
                        "start_date",
                        "end_date",
                        "ongoing",
                        "note",
                    ],
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "enum": sorted(SUPPORTED_CONTEXT_EVENT_TYPES),
                        },
                        "start_date": {"type": "string"},
                        "end_date": {"type": ["string", "null"]},
                        "ongoing": {"type": "boolean"},
                        "note": {"type": "string"},
                    },
                },
            ]
        },
    },
}


class OpenAIResponsesClient:
    """Make one stateless Responses API call with no tools or retained history."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = MODEL,
        client: Any | None = None,
    ) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model

    def answer(self, request: PaceAIRequest) -> PaceAIAnswer:
        """Return one validated answer without provider-side response storage."""

        try:
            response = self._client.responses.create(
                model=self._model,
                reasoning={"effort": REASONING_EFFORT},
                store=False,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                instructions=SYSTEM_INSTRUCTIONS,
                input=_render_input(request),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "pace_ai_answer",
                        "strict": True,
                        "schema": ANSWER_SCHEMA,
                    }
                },
            )
        except Exception as error:
            raise PaceAIUnavailableError(
                "AI-tjänsten kunde inte svara. Dina Pace-data har inte ändrats."
            ) from error

        response_text = getattr(response, "output_text", "")
        if not response_text:
            if _find_refusal(response):
                raise PaceAIResponseError(
                    "AI-tjänsten avböjde frågan. Dina Pace-data har inte ändrats."
                )
            raise PaceAIResponseError(
                "AI-tjänsten gav inget användbart svar. Dina Pace-data har inte ändrats."
            )

        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as error:
            raise PaceAIResponseError(
                "AI-tjänsten gav ett ogiltigt svar. Dina Pace-data har inte ändrats."
            ) from error

        return _parse_answer(payload)


def _render_input(request: PaceAIRequest) -> str:
    """Keep each call stateless and make the selected context visible to the model."""

    return (
        "Athlete question:\n"
        f"{request.question}\n\n"
        "Selected Pace facts (JSON):\n"
        f"{json.dumps(request.context, ensure_ascii=False, sort_keys=True)}"
    )


def _find_refusal(response: Any) -> str | None:
    """Extract an SDK refusal without depending on SDK response model classes."""

    for output in getattr(response, "output", ()):
        for content in getattr(output, "content", ()):
            if getattr(content, "type", None) == "refusal":
                return str(getattr(content, "refusal", ""))
    return None


def _parse_answer(payload: object) -> PaceAIAnswer:
    """Validate the provider JSON again before it reaches the Pace CLI."""

    if not isinstance(payload, dict):
        raise PaceAIResponseError("AI-svaret hade fel format.")

    expected_keys = {
        "answer",
        "observations",
        "uncertainties",
        "context_event_draft",
    }
    if set(payload) != expected_keys:
        raise PaceAIResponseError("AI-svaret hade fel fält.")

    answer = payload["answer"]
    observations = payload["observations"]
    uncertainties = payload["uncertainties"]
    if (
        not isinstance(answer, str)
        or not _is_string_list(observations)
        or not _is_string_list(uncertainties)
    ):
        raise PaceAIResponseError("AI-svaret hade ogiltigt innehåll.")

    return PaceAIAnswer(
        answer=answer,
        observations=tuple(observations),
        uncertainties=tuple(uncertainties),
        context_event_draft=_parse_context_event_draft(payload["context_event_draft"]),
    )


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _parse_context_event_draft(value: object) -> ContextEventDraft | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise PaceAIResponseError("Context-utkastet hade fel format.")

    expected_keys = {"event_type", "start_date", "end_date", "ongoing", "note"}
    if set(value) != expected_keys:
        raise PaceAIResponseError("Context-utkastet hade fel fält.")

    event_type = value["event_type"]
    start_date = value["start_date"]
    end_date = value["end_date"]
    ongoing = value["ongoing"]
    note = value["note"]
    if (
        event_type not in SUPPORTED_CONTEXT_EVENT_TYPES
        or not isinstance(start_date, str)
        or not (isinstance(end_date, str) or end_date is None)
        or not isinstance(ongoing, bool)
        or not isinstance(note, str)
        or not note.strip()
    ):
        raise PaceAIResponseError("Context-utkastet hade ogiltigt innehåll.")

    try:
        parsed_start_date = date.fromisoformat(start_date)
        parsed_end_date = None if end_date is None else date.fromisoformat(end_date)
    except ValueError as error:
        raise PaceAIResponseError("Context-utkastet hade ogiltiga datum.") from error

    if ongoing and parsed_end_date is not None:
        raise PaceAIResponseError("Ett pågående context-utkast kan inte ha ett slutdatum.")
    if not ongoing and parsed_end_date is not None and parsed_end_date < parsed_start_date:
        raise PaceAIResponseError("Context-utkastets slutdatum är före startdatumet.")

    return ContextEventDraft(
        event_type=event_type,
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        ongoing=ongoing,
        note=note.strip(),
    )
