"""Stateless OpenAI boundary for one explicit weekly review."""

import json
from typing import Any

from openai import OpenAI

from pace.ai.client import PaceAIResponseError, PaceAIUnavailableError
from pace.weekly_review.models import WeeklyReviewAnswer, WeeklyReviewRequest


SYSTEM_INSTRUCTIONS = """You are Pace's Swedish endurance coach writing one weekly review.
The supplied Pace facts are the complete factual contract about this athlete.
Python already calculated all numbers: do not invent, recalculate, or override
metrics, dates, training history, data quality, or causes. Treat correlations as
observations, never causes. You may use general endurance-coaching knowledge to
form coach assessments and recommendations, but never present that knowledge as
a Pace fact, a study, or a specific external source. Do not diagnose or provide
medical advice.

Keep the sections distinct: observations contain direct Pace facts only;
coach_assessment contains clearly framed coaching inferences; recommendations
contain direct actions for the coming week; uncertainties state what Pace or
the coach cannot establish. Do not create, accept, or change a plan. Use a
direct, unsentimental tone without generic care-provider language.

Selected local knowledge briefs are optional support, not a complete allowlist
of coaching knowledge. Cite only supplied brief IDs when one actually supports
the review. Return an empty knowledge_references list when your assessment uses
general coaching knowledge. Return Swedish JSON matching the schema."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "observations",
        "coach_assessment",
        "recommendations",
        "uncertainties",
        "knowledge_references",
    ],
    "properties": {
        "summary": {"type": "string", "minLength": 1},
        "observations": {"type": "array", "items": {"type": "string"}},
        "coach_assessment": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "knowledge_references": {"type": "array", "items": {"type": "string"}},
    },
}


class WeeklyReviewClient:
    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model

    def review(self, request: WeeklyReviewRequest) -> WeeklyReviewAnswer:
        try:
            response = self._client.responses.create(
                model=self._model,
                reasoning={"effort": "medium"},
                store=False,
                max_output_tokens=1_400,
                instructions=SYSTEM_INSTRUCTIONS,
                input=json.dumps(request.context, ensure_ascii=False, sort_keys=True),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "pace_weekly_review",
                        "strict": True,
                        "schema": SCHEMA,
                    }
                },
            )
        except Exception as error:
            raise PaceAIUnavailableError(_provider_error_message(error)) from error
        try:
            payload = json.loads(getattr(response, "output_text", ""))
        except json.JSONDecodeError as error:
            raise PaceAIResponseError("AI-tjänsten gav en ogiltig veckoreview.") from error
        if not isinstance(payload, dict) or set(payload) != set(SCHEMA["required"]):
            raise PaceAIResponseError("AI-tjänsten gav fel veckoreview-format.")
        lists = (
            "observations",
            "coach_assessment",
            "recommendations",
            "uncertainties",
            "knowledge_references",
        )
        if not isinstance(payload["summary"], str) or any(
            not isinstance(payload[key], list)
            or any(not isinstance(item, str) for item in payload[key])
            for key in lists
        ):
            raise PaceAIResponseError("AI-tjänsten gav ogiltigt veckoreview-innehåll.")
        selected = {
            item["id"]
            for item in request.context.get("knowledge_briefs", {}).get("briefs", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        references = tuple(
            item for item in payload["knowledge_references"] if item in selected
        )
        return WeeklyReviewAnswer(
            summary=payload["summary"],
            observations=tuple(payload["observations"]),
            coach_assessment=tuple(payload["coach_assessment"]),
            recommendations=tuple(payload["recommendations"]),
            uncertainties=tuple(payload["uncertainties"]),
            knowledge_references=references,
        )


def _provider_error_message(error: Exception) -> str:
    """Explain a provider failure without including credentials or request data."""

    status_code = getattr(error, "status_code", None)
    if status_code == 401:
        reason = "OpenAI avvisade API-nyckeln (HTTP 401)."
    elif status_code == 403:
        reason = "OpenAI-nyckeln saknar behörighet för den valda modellen (HTTP 403)."
    elif status_code == 429:
        reason = "OpenAI begränsade begäran (HTTP 429): kontrollera saldo eller rate limit."
    elif isinstance(status_code, int) and 400 <= status_code < 500:
        reason = f"OpenAI avvisade veckoreviewens begäran (HTTP {status_code})."
    elif isinstance(status_code, int) and status_code >= 500:
        reason = f"OpenAI-tjänsten hade ett tillfälligt fel (HTTP {status_code})."
    else:
        reason = f"AI-tjänsten kunde inte nås ({type(error).__name__})."

    return f"{reason} Dina Pace-data har inte ändrats."
