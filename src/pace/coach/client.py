"""Stateless OpenAI boundary for Pace's plan-aware coach dialogue."""

import json
from datetime import date
from typing import Any

from openai import OpenAI

from pace.ai.client import PaceAIResponseError, PaceAIUnavailableError
from pace.ai.models import ContextEventDraft
from pace.ai.plan_client import _WORKOUT_STEP_SCHEMA, _parse_session
from pace.coach.models import (
    CoachDialogueAnswer,
    CoachDialogueRequest,
    PlanAdjustmentDraft,
    SessionFeedbackDraft,
)
from pace.services.context_service import SUPPORTED_CONTEXT_EVENT_TYPES
from pace.services.training_plan_service import (
    SUPPORTED_FEEDBACK_OUTCOMES,
    SUPPORTED_FEEDBACK_REASON_CODES,
)


REASONING_EFFORT = "medium"
MAX_OUTPUT_TOKENS = 1_200

SYSTEM_INSTRUCTIONS = """You are Pace's Swedish-language endurance coach.
Supplied Pace facts and the active accepted plan are the complete factual
contract about this athlete. You may apply general endurance-coaching knowledge
to form a coach assessment, but must not present that knowledge as a Pace fact,
study, or specific external source. You cannot access Garmin, the local
database, private context-note text, or prior conversations outside this
request. Do not invent capacity, recovery, dates, targets, completed training,
or causes. Do not diagnose or provide medical advice.

training_response_trends is deterministic aggregation of explicit athlete
feedback only. It is not a measure of unreported sessions and cannot establish
why outcomes or RPE changed. Use it only when its status is ready, and name
its data limitation when it matters to your recommendation.

personalization_evidence is a fresh deterministic observation, not a causal
profile. Use its observed_patterns only when ready; they describe reported
sessions, not silence or causality. Athlete-confirmed coach principles may guide
you only when supplied as active facts; do not invent or persist new ones.

The supplied coaching ambition is athlete intent, not a command. It may affect
how assertively you recommend progression, volume, or quality only when the
selected facts support that recommendation. It never permits bypassing facts,
availability, target eligibility, or a need to reduce or skip a session.

Answer directly and without praise, therapy language, generic wellness text,
or routine care-provider referrals. State what the facts support, what is
unknown, and give a concrete recommendation. Do not turn toughness into
recklessness: if supplied facts support reducing or skipping a session, say so
plainly and do not compensate with extra intensity.

You may return an adjustment_draft only for one planned session on the current
as-of date. It is never saved or applied. Use action keep_plan when no change
is justified, skip when the referenced planned session should not be done, or
replace when a same-day replacement session is justified. A replacement must
use the exact structured session fields. Never prescribe cycling pace. Use a
cycling heart-rate zone only when it is present in the supplied allowed facts.
For pace or power, use only an eligible evidence_reference_id supplied in the
facts. Curated knowledge briefs are optional local support: cite only supplied
brief IDs when one actually supports the answer, otherwise return an empty
knowledge_references list.

When the athlete explicitly reports the outcome of a planned session, you may
return one feedback_draft. It must describe only the stated outcome, never infer
that a session happened from Garmin. When the athlete volunteers relevant life
context, you may return one context_event_draft. Both drafts are unsaved and
require a visible athlete confirmation in the interface. Otherwise return null.
Return Swedish JSON matching the schema."""


_SESSION_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "scheduled_date",
        "sport_type",
        "purpose",
        "distance_meters",
        "duration_seconds",
        "heart_rate_zone",
        "target",
        "workout_steps",
    ],
    "properties": {
        "scheduled_date": {"type": "string"},
        "sport_type": {"type": "string", "enum": ["run", "ride"]},
        "purpose": {"type": "string", "minLength": 1},
        "distance_meters": {"type": ["number", "null"]},
        "duration_seconds": {"type": ["integer", "null"]},
        "heart_rate_zone": {"type": ["integer", "null"]},
        "target": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "kind",
                "rpe_min",
                "rpe_max",
                "pace_seconds_per_km",
                "power_watts",
                "evidence_reference_id",
            ],
            "properties": {
                "kind": {"type": "string", "enum": ["rpe", "pace", "power", "none"]},
                "rpe_min": {"type": ["integer", "null"]},
                "rpe_max": {"type": ["integer", "null"]},
                "pace_seconds_per_km": {"type": ["integer", "null"]},
                "power_watts": {"type": ["integer", "null"]},
                "evidence_reference_id": {"type": ["string", "null"]},
            },
        },
        "workout_steps": {
            "type": "array",
            "minItems": 1,
            "items": _WORKOUT_STEP_SCHEMA,
        },
    },
}

COACH_DIALOGUE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer",
        "observations",
        "uncertainties",
        "knowledge_references",
        "adjustment_draft",
        "context_event_draft",
        "feedback_draft",
    ],
    "properties": {
        "answer": {"type": "string", "minLength": 1},
        "observations": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "knowledge_references": {"type": "array", "items": {"type": "string"}},
        "adjustment_draft": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "action",
                        "replaces_session_id",
                        "rationale",
                        "proposed_session",
                    ],
                    "properties": {
                        "action": {"type": "string", "enum": ["keep_plan", "skip", "replace"]},
                        "replaces_session_id": {"type": ["integer", "null"]},
                        "rationale": {"type": "string", "minLength": 1},
                        "proposed_session": {"anyOf": [{"type": "null"}, _SESSION_SCHEMA]},
                    },
                },
            ]
        },
        "context_event_draft": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["event_type", "start_date", "end_date", "ongoing", "note"],
                    "properties": {
                        "event_type": {"type": "string", "enum": sorted(SUPPORTED_CONTEXT_EVENT_TYPES)},
                        "start_date": {"type": "string"},
                        "end_date": {"type": ["string", "null"]},
                        "ongoing": {"type": "boolean"},
                        "note": {"type": "string", "minLength": 1},
                    },
                },
            ]
        },
        "feedback_draft": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["planned_session_id", "outcome", "perceived_exertion", "reason_code", "note"],
                    "properties": {
                        "planned_session_id": {"type": "integer"},
                        "outcome": {"type": "string", "enum": sorted(SUPPORTED_FEEDBACK_OUTCOMES)},
                        "perceived_exertion": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
                        "reason_code": {"type": ["string", "null"], "enum": [*sorted(SUPPORTED_FEEDBACK_REASON_CODES), None]},
                        "note": {"type": ["string", "null"]},
                    },
                },
            ]
        },
    },
}


class OpenAICoachDialogueClient:
    """Make one stateless model call; dialogue history stays only in caller RAM."""

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model

    def answer(self, request: CoachDialogueRequest) -> CoachDialogueAnswer:
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
                        "name": "pace_coach_dialogue_answer",
                        "strict": True,
                        "schema": COACH_DIALOGUE_SCHEMA,
                    }
                },
            )
        except Exception as error:
            raise PaceAIUnavailableError(_provider_error_message(error)) from error
        response_text = getattr(response, "output_text", "")
        if not response_text:
            raise PaceAIResponseError(
                "AI-coachen gav inget användbart svar. Din plan har inte ändrats."
            )
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as error:
            raise PaceAIResponseError("AI-coachen gav ett ogiltigt svar.") from error
        return _parse_answer(payload, context=request.context)


def _render_input(request: CoachDialogueRequest) -> str:
    return (
        "Athlete question:\n"
        f"{request.question}\n\n"
        "In-memory dialogue history (not stored by Pace):\n"
        f"{json.dumps(request.conversation, ensure_ascii=False, default=_json_default)}\n\n"
        "Selected Pace facts and active plan (JSON):\n"
        f"{json.dumps(request.context, ensure_ascii=False, sort_keys=True, default=_json_default)}"
    )


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _provider_error_message(error: Exception) -> str:
    """Explain provider failure without exposing credentials or Pace facts."""

    status_code = getattr(error, "status_code", None)
    if status_code == 401:
        reason = "OpenAI avvisade API-nyckeln (HTTP 401)."
    elif status_code == 403:
        reason = "OpenAI-nyckeln saknar behörighet för den valda modellen (HTTP 403)."
    elif status_code == 429:
        reason = "OpenAI begränsade begäran (HTTP 429): kontrollera saldo eller rate limit."
    elif isinstance(status_code, int) and 400 <= status_code < 500:
        reason = f"OpenAI avvisade coachens begäran (HTTP {status_code})."
    elif isinstance(status_code, int) and status_code >= 500:
        reason = f"OpenAI-tjänsten hade ett tillfälligt fel (HTTP {status_code})."
    else:
        reason = f"AI-tjänsten kunde inte nås ({type(error).__name__})."
    return f"{reason} Din plan har inte ändrats."


def _parse_answer(payload: object, *, context: dict[str, object]) -> CoachDialogueAnswer:
    if not isinstance(payload, dict) or set(payload) != {
        "answer",
        "observations",
        "uncertainties",
        "knowledge_references",
        "adjustment_draft",
        "context_event_draft",
        "feedback_draft",
    }:
        raise PaceAIResponseError("AI-coachen hade fel svarsfält.")
    answer = payload["answer"]
    observations = _text_tuple(payload["observations"])
    uncertainties = _text_tuple(payload["uncertainties"])
    if not isinstance(answer, str) or not answer.strip():
        raise PaceAIResponseError("AI-coachen hade ogiltigt svarsinnehåll.")
    references = _text_tuple(payload["knowledge_references"])
    selected_ids = _selected_knowledge_ids(context)
    references = tuple(item for item in references if item in selected_ids)
    return CoachDialogueAnswer(
        answer=answer.strip(),
        observations=observations,
        uncertainties=uncertainties,
        knowledge_references=references,
        adjustment_draft=_parse_adjustment(payload["adjustment_draft"]),
        context_event_draft=_parse_context_draft(payload["context_event_draft"]),
        feedback_draft=_parse_feedback_draft(payload["feedback_draft"]),
    )


def _parse_adjustment(value: object) -> PlanAdjustmentDraft | None:
    if value is None:
        return None
    expected = {"action", "replaces_session_id", "rationale", "proposed_session"}
    if not isinstance(value, dict) or set(value) != expected:
        raise PaceAIResponseError("Planjusteringsutkastet hade fel fält.")
    action = value["action"]
    session_id = value["replaces_session_id"]
    rationale = value["rationale"]
    proposed = value["proposed_session"]
    if action not in {"keep_plan", "skip", "replace"}:
        raise PaceAIResponseError("Planjusteringsutkastet hade ogiltig åtgärd.")
    if not isinstance(rationale, str) or not rationale.strip():
        raise PaceAIResponseError("Planjusteringsutkastet saknar motivering.")
    if action == "keep_plan":
        if session_id is not None or proposed is not None:
            raise PaceAIResponseError("Behåll-plan-utkastet får inte ändra ett pass.")
        return PlanAdjustmentDraft(action, None, rationale.strip(), None)
    if not isinstance(session_id, int) or isinstance(session_id, bool):
        raise PaceAIResponseError("Planjusteringsutkastet saknar ett giltigt pass-id.")
    if action == "skip":
        if proposed is not None:
            raise PaceAIResponseError("Ett hoppa-över-utkast får inte innehålla ersättningspass.")
        return PlanAdjustmentDraft(action, session_id, rationale.strip(), None)
    if proposed is None:
        raise PaceAIResponseError("Ett ersättningsutkast måste innehålla ett pass.")
    try:
        planned_session = _parse_session(proposed)
    except (KeyError, TypeError, ValueError, PaceAIResponseError) as error:
        raise PaceAIResponseError("Planjusteringsutkastet hade ogiltigt ersättningspass.") from error
    return PlanAdjustmentDraft(action, session_id, rationale.strip(), planned_session)


def _parse_context_draft(value: object) -> ContextEventDraft | None:
    if value is None:
        return None
    expected = {"event_type", "start_date", "end_date", "ongoing", "note"}
    if not isinstance(value, dict) or set(value) != expected:
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
        parsed_start = date.fromisoformat(start_date)
        parsed_end = None if end_date is None else date.fromisoformat(end_date)
    except ValueError as error:
        raise PaceAIResponseError("Context-utkastet hade ogiltiga datum.") from error
    if ongoing and parsed_end is not None:
        raise PaceAIResponseError("Ett pågående context-utkast kan inte ha slutdatum.")
    if not ongoing and parsed_end is not None and parsed_end < parsed_start:
        raise PaceAIResponseError("Context-utkastets slutdatum är före startdatumet.")
    return ContextEventDraft(event_type, parsed_start, parsed_end, ongoing, note.strip())


def _parse_feedback_draft(value: object) -> SessionFeedbackDraft | None:
    if value is None:
        return None
    expected = {"planned_session_id", "outcome", "perceived_exertion", "reason_code", "note"}
    if not isinstance(value, dict) or set(value) != expected:
        raise PaceAIResponseError("Feedback-utkastet hade fel fält.")
    session_id = value["planned_session_id"]
    outcome = value["outcome"]
    rpe = value["perceived_exertion"]
    reason = value["reason_code"]
    note = value["note"]
    valid_rpe = isinstance(rpe, int) and not isinstance(rpe, bool) and 1 <= rpe <= 10
    if (
        not isinstance(session_id, int)
        or isinstance(session_id, bool)
        or outcome not in SUPPORTED_FEEDBACK_OUTCOMES
        or not (rpe is None or valid_rpe)
        or not (reason is None or reason in SUPPORTED_FEEDBACK_REASON_CODES)
        or not (note is None or isinstance(note, str))
    ):
        raise PaceAIResponseError("Feedback-utkastet hade ogiltigt innehåll.")
    if outcome not in {"completed", "completed_limited"} and rpe is not None:
        raise PaceAIResponseError("Feedback-utkastet har RPE för fel utfall.")
    if outcome not in {"completed_limited", "skipped"} and reason is not None:
        raise PaceAIResponseError("Feedback-utkastet har orsak för fel utfall.")
    clean_note = note.strip() if isinstance(note, str) and note.strip() else None
    return SessionFeedbackDraft(session_id, outcome, rpe, reason, clean_note)


def _selected_knowledge_ids(context: dict[str, object]) -> frozenset[str]:
    knowledge = context.get("knowledge_briefs")
    if not isinstance(knowledge, dict) or not isinstance(knowledge.get("briefs"), list):
        return frozenset()
    return frozenset(
        item["id"]
        for item in knowledge["briefs"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    )


def _text_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise PaceAIResponseError("AI-coachen hade ogiltiga textfält.")
    return tuple(item.strip() for item in value)
