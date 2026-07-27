"""Stateless, schema-validated AI boundary for reviewable Pace plan drafts."""

from copy import deepcopy
from datetime import date
import json
from typing import Any

from openai import OpenAI

from pace.ai.client import PaceAIResponseError, PaceAIUnavailableError
from pace.planning.draft_models import (
    BlockOutlineItem,
    CoachAssessmentDraft,
    GeneratedPlanDraft,
    PlanGenerationRequest,
    PlannedSessionDraft,
    SessionTargetDraft,
)


REASONING_EFFORT = "medium"
MAX_OUTPUT_TOKENS = 4800
MAX_GENERATION_ATTEMPTS = 2
TARGET_KINDS = ("rpe", "pace", "power", "none")

SYSTEM_INSTRUCTIONS = """You are Pace's Swedish-language plan-drafting assistant.
Use only the supplied selected Pace facts. Return a conservative, reviewable
plan draft, never medical advice. Use only the supplied selected Pace facts;
do not invent capacity, prior volume, dates, recovery facts, races,
availability, or targets. The athlete's sport role is a preference, not a
fixed session ratio: decide the run/ride mix and intensity from the selected
facts. Coaching ambition (cautious, balanced, ambitious) is also a preference,
not permission to ignore facts: it may affect the proposed progression, volume,
or quality only when the selected facts support it. State plainly in the coach
assessment how it affected the draft, or why it did not. Python gates define whether pace or power targets are permitted per
sport. Never prescribe cycling pace. A cycling heart-rate target is a separate
heart_rate_zone and must use an explicitly permitted Garmin zone. Every ride
must include a concise purpose, distance, duration, and zone target. The
primary target object is structured: use its target kind and numeric field,
never hide pace or watts in free text. Pace and power targets must cite one
eligible evidence_reference_id from the fact catalog.
Availability null means no supplied time ceiling; it is never permission to
prescribe unlimited training. Return a coach_assessment with fact_references
as exact ID strings selected only from the supplied fact_catalog, then your inferences, rationale,
uncertainties, and general coaching_principles. The principles are not source
citations unless you list selected knowledge brief IDs in knowledge_references.
You cannot access Garmin, the local database, private context-note text, or
prior conversations. Do not cite a knowledge brief that was not supplied, and
do not claim that a brief supports more than its supported_claims permit.

Tone: write like a direct, unsentimental Swedish endurance coach. Be concrete
about what the athlete should do, what the facts support, and what is unknown.
Do not praise, soothe, use therapy language, pad the answer with generic
wellness phrases, or add routine care-provider referrals for ordinary fatigue,
poor sleep, or discomfort. Do not turn toughness into recklessness: when the
facts justify backing off, say to skip or reduce the session plainly and do not
try to compensate with extra intensity later. Do not diagnose or give medical
advice. Return only JSON matching the schema."""

PLAN_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["coach_assessment", "block_outline", "sessions"],
    "properties": {
        "coach_assessment": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "fact_references",
                "inferences",
                "rationale",
                "uncertainties",
                "coaching_principles",
                "knowledge_references",
            ],
            "properties": {
                "fact_references": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "inferences": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "rationale": {"type": "string", "minLength": 1},
                "uncertainties": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "coaching_principles": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
                "knowledge_references": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "block_outline": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["week_start", "week_end", "focus"],
                "properties": {
                    "week_start": {"type": "string"},
                    "week_end": {"type": "string"},
                    "focus": {"type": "string"},
                },
            },
        },
        "sessions": {
            "type": "array",
            "items": {
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
                ],
                "properties": {
                    "scheduled_date": {"type": "string"},
                    "sport_type": {"type": "string", "enum": ["run", "ride"]},
                    "purpose": {"type": "string"},
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
                            "kind": {"type": "string", "enum": list(TARGET_KINDS)},
                            "rpe_min": {"type": ["integer", "null"]},
                            "rpe_max": {"type": ["integer", "null"]},
                            "pace_seconds_per_km": {"type": ["integer", "null"]},
                            "power_watts": {"type": ["integer", "null"]},
                            "evidence_reference_id": {"type": ["string", "null"]},
                        },
                    },
                },
            },
        },
    },
}


class OpenAIPlanClient:
    """One explicit, stateless Responses call that cannot write Pace state."""

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        self._client = client or OpenAI(api_key=api_key)
        self._model = model

    def generate(self, request: PlanGenerationRequest) -> GeneratedPlanDraft:
        schema = _schema_for_request(request)
        last_error: PaceAIResponseError | None = None
        for _attempt in range(MAX_GENERATION_ATTEMPTS):
            try:
                response = self._client.responses.create(
                    model=self._model,
                    reasoning={"effort": REASONING_EFFORT},
                    store=False,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    instructions=SYSTEM_INSTRUCTIONS,
                    input=(
                        f"Plan mode: {request.mode}\n\n"
                        "Selected Pace facts (JSON):\n"
                        f"{json.dumps(request.context, ensure_ascii=False, sort_keys=True)}"
                    ),
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "pace_plan_draft",
                            "strict": True,
                            "schema": schema,
                        }
                    },
                )
            except Exception as error:
                raise PaceAIUnavailableError(
                    "AI-tjänsten kunde inte skapa ett planutkast. Dina Pace-data har inte ändrats."
                ) from error
            try:
                return _parse_response(response)
            except PaceAIResponseError as error:
                last_error = error

        raise PaceAIResponseError(
            "AI-tjänsten kunde inte leverera ett komplett planutkast efter två försök. "
            "Dina Pace-data har inte ändrats."
        ) from last_error


def _schema_for_request(request: PlanGenerationRequest) -> dict[str, object]:
    """Bind citations to the identifiers selected for this local request."""

    fact_catalog = request.context.get("fact_catalog")
    if not isinstance(fact_catalog, dict) or not fact_catalog:
        raise PaceAIResponseError("Planutkastet saknar en giltig Pace-faktakatalog.")
    knowledge_briefs = request.context.get("knowledge_briefs")
    briefs = knowledge_briefs.get("briefs") if isinstance(knowledge_briefs, dict) else None
    knowledge_ids = (
        sorted(
            item["id"]
            for item in briefs
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )
        if isinstance(briefs, list)
        else []
    )
    if not knowledge_ids:
        raise PaceAIResponseError("Planutkastet saknar valda kunskapsbriefar.")

    schema = deepcopy(PLAN_SCHEMA)
    assessment = schema["properties"]["coach_assessment"]
    assert isinstance(assessment, dict)
    properties = assessment["properties"]
    assert isinstance(properties, dict)
    properties["fact_references"] = {
        "type": "array",
        "minItems": 1,
        "items": {"type": "string", "enum": sorted(fact_catalog)},
    }
    properties["knowledge_references"] = {
        "type": "array",
        "minItems": 1,
        "items": {"type": "string", "enum": knowledge_ids},
    }
    return schema


def _parse_response(response: object) -> GeneratedPlanDraft:
    response_text = getattr(response, "output_text", "")
    if not response_text:
        raise PaceAIResponseError("AI-tjänsten gav inget användbart planutkast.")
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise PaceAIResponseError("AI-planen hade fel format.") from error
    return _parse_plan(payload)


def _parse_plan(payload: object) -> GeneratedPlanDraft:
    if not isinstance(payload, dict) or set(payload) != {
        "coach_assessment",
        "block_outline",
        "sessions",
    }:
        raise PaceAIResponseError("AI-planen hade fel fält.")
    if not isinstance(payload["block_outline"], list) or not isinstance(payload["sessions"], list):
        raise PaceAIResponseError("AI-planen hade fel innehåll.")
    try:
        block_outline = tuple(
            BlockOutlineItem(
                week_start=date.fromisoformat(item["week_start"]),
                week_end=date.fromisoformat(item["week_end"]),
                focus=_required_text(item, "focus"),
            )
            for item in payload["block_outline"]
            if isinstance(item, dict) and set(item) == {"week_start", "week_end", "focus"}
        )
        sessions = tuple(_parse_session(item) for item in payload["sessions"])
        coach_assessment = _parse_coach_assessment(payload["coach_assessment"])
    except (KeyError, TypeError, ValueError) as error:
        raise PaceAIResponseError("AI-planen hade ogiltigt innehåll.") from error
    if len(block_outline) != len(payload["block_outline"]):
        raise PaceAIResponseError("AI-planen hade ogiltig blocköversikt.")
    return GeneratedPlanDraft(
        block_outline=block_outline,
        sessions=sessions,
        coach_assessment=coach_assessment,
    )


def _parse_coach_assessment(item: object) -> CoachAssessmentDraft:
    required_fields = {
        "fact_references",
        "inferences",
        "rationale",
        "uncertainties",
        "coaching_principles",
        "knowledge_references",
    }
    if not isinstance(item, dict) or set(item) != required_fields:
        raise PaceAIResponseError("AI-planen hade fel coachbedömning.")
    return CoachAssessmentDraft(
        fact_references=_text_tuple(item["fact_references"], require_nonempty=True),
        inferences=_text_tuple(item["inferences"], require_nonempty=True),
        rationale=_required_text(item, "rationale"),
        uncertainties=_text_tuple(item["uncertainties"], require_nonempty=True),
        coaching_principles=_text_tuple(
            item["coaching_principles"], require_nonempty=True
        ),
        knowledge_references=_text_tuple(item["knowledge_references"]),
    )


def _parse_session(item: object) -> PlannedSessionDraft:
    if not isinstance(item, dict) or set(item) != {
        "scheduled_date", "sport_type", "purpose", "distance_meters", "duration_seconds", "heart_rate_zone", "target"
    }:
        raise PaceAIResponseError("AI-planen hade ogiltiga passfält.")
    distance = item["distance_meters"]
    duration = item["duration_seconds"]
    if distance is not None and (not isinstance(distance, (int, float)) or distance <= 0):
        raise PaceAIResponseError("AI-planen hade ogiltig passdistans.")
    if duration is not None and (not isinstance(duration, int) or duration <= 0):
        raise PaceAIResponseError("AI-planen hade ogiltig passtid.")
    if item["sport_type"] not in {"run", "ride"}:
        raise PaceAIResponseError("AI-planen hade ogiltig sport.")
    heart_rate_zone = item["heart_rate_zone"]
    if heart_rate_zone is not None and (
        not isinstance(heart_rate_zone, int) or isinstance(heart_rate_zone, bool)
    ):
        raise PaceAIResponseError("AI-planen hade ogiltig pulszon.")
    return PlannedSessionDraft(
        scheduled_date=date.fromisoformat(item["scheduled_date"]),
        sport_type=item["sport_type"],
        purpose=_required_text(item, "purpose"),
        distance_meters=None if distance is None else float(distance),
        duration_seconds=duration,
        heart_rate_zone=heart_rate_zone,
        target=_parse_target(item["target"]),
    )


def _parse_target(item: object) -> SessionTargetDraft:
    required_fields = {
        "kind",
        "rpe_min",
        "rpe_max",
        "pace_seconds_per_km",
        "power_watts",
        "evidence_reference_id",
    }
    if not isinstance(item, dict) or set(item) != required_fields:
        raise PaceAIResponseError("AI-planen hade ogiltigt målfält.")
    kind = item["kind"]
    if kind not in TARGET_KINDS:
        raise PaceAIResponseError("AI-planen hade ogiltig måltyp.")
    values = {
        field_name: item[field_name]
        for field_name in ("rpe_min", "rpe_max", "pace_seconds_per_km", "power_watts")
    }
    for value in values.values():
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            raise PaceAIResponseError("AI-planen hade ogiltigt numeriskt mål.")
    evidence_reference_id = item["evidence_reference_id"]
    if evidence_reference_id is not None and (
        not isinstance(evidence_reference_id, str) or not evidence_reference_id.strip()
    ):
        raise PaceAIResponseError("AI-planen hade ogiltig faktareferens.")
    return SessionTargetDraft(
        kind=kind,
        rpe_min=values["rpe_min"],
        rpe_max=values["rpe_max"],
        pace_seconds_per_km=values["pace_seconds_per_km"],
        power_watts=values["power_watts"],
        evidence_reference_id=evidence_reference_id,
    )


def _required_text(item: dict[str, object], key: str) -> str:
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key)
    return value.strip()


def _text_tuple(value: object, *, require_nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("Expected a text list.")
    texts = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if len(texts) != len(value):
        raise ValueError("Expected non-empty text items.")
    if require_nonempty and not texts:
        raise ValueError("Expected at least one text item.")
    return texts
