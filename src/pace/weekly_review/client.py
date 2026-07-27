"""Stateless OpenAI boundary for one explicit weekly review."""

import json
from typing import Any

from openai import OpenAI

from pace.ai.client import PaceAIResponseError, PaceAIUnavailableError
from pace.weekly_review.models import WeeklyReviewAnswer, WeeklyReviewRequest


SYSTEM_INSTRUCTIONS = """You are Pace's Swedish endurance coach writing one weekly review.
Use only supplied Pace facts and selected local knowledge briefs. Python already
calculated all numbers: do not invent, recalculate, diagnose, or claim cause.
State facts, coach inferences, and uncertainty separately. Give direct,
unsentimental recommendations for the coming week, but do not create, accept,
or change a plan. Do not add generic care-provider language. Return Swedish
JSON matching the schema."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["summary", "observations", "recommendations", "uncertainties", "knowledge_references"], "properties": {"summary": {"type": "string", "minLength": 1}, "observations": {"type": "array", "items": {"type": "string"}}, "recommendations": {"type": "array", "items": {"type": "string"}}, "uncertainties": {"type": "array", "items": {"type": "string"}}, "knowledge_references": {"type": "array", "items": {"type": "string"}}}}


class WeeklyReviewClient:
    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model

    def review(self, request: WeeklyReviewRequest) -> WeeklyReviewAnswer:
        try:
            response = self._client.responses.create(model=self._model, reasoning={"effort": "medium"}, store=False, max_output_tokens=1_400, instructions=SYSTEM_INSTRUCTIONS, input=json.dumps(request.context, ensure_ascii=False, sort_keys=True), text={"format": {"type": "json_schema", "name": "pace_weekly_review", "strict": True, "schema": SCHEMA}})
        except Exception as error:
            raise PaceAIUnavailableError("AI-tjänsten kunde inte skapa veckoreviewen. Dina Pace-data har inte ändrats.") from error
        try:
            payload = json.loads(getattr(response, "output_text", ""))
        except json.JSONDecodeError as error:
            raise PaceAIResponseError("AI-tjänsten gav en ogiltig veckoreview.") from error
        if not isinstance(payload, dict) or set(payload) != set(SCHEMA["required"]):
            raise PaceAIResponseError("AI-tjänsten gav fel veckoreview-format.")
        lists = ("observations", "recommendations", "uncertainties", "knowledge_references")
        if not isinstance(payload["summary"], str) or any(not isinstance(payload[key], list) or any(not isinstance(item, str) for item in payload[key]) for key in lists):
            raise PaceAIResponseError("AI-tjänsten gav ogiltigt veckoreview-innehåll.")
        selected = {item["id"] for item in request.context.get("knowledge_briefs", {}).get("briefs", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}
        if set(payload["knowledge_references"]).difference(selected):
            raise PaceAIResponseError("AI-tjänsten citerade kunskap som inte valts av Pace.")
        return WeeklyReviewAnswer(payload["summary"], tuple(payload["observations"]), tuple(payload["recommendations"]), tuple(payload["uncertainties"]), tuple(payload["knowledge_references"]))
