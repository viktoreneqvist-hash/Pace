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
    WorkoutStepDraft,
)


REASONING_EFFORT = "medium"
MAX_OUTPUT_TOKENS = 4800
MAX_GENERATION_ATTEMPTS = 2
TARGET_KINDS = ("rpe", "pace", "power", "none")
WORKOUT_STEP_KINDS = ("warmup", "steady", "interval", "cooldown")

_TARGET_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "kind", "rpe_min", "rpe_max", "pace_seconds_per_km", "power_watts",
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
}

_WORKOUT_STEP_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "kind", "repetitions", "distance_meters", "duration_seconds", "target",
        "recovery_distance_meters", "recovery_duration_seconds", "recovery_target",
        "instruction",
    ],
    "properties": {
        "kind": {"type": "string", "enum": list(WORKOUT_STEP_KINDS)},
        "repetitions": {"type": "integer", "minimum": 1},
        "distance_meters": {"type": ["number", "null"]},
        "duration_seconds": {"type": ["integer", "null"]},
        "target": _TARGET_SCHEMA,
        "recovery_distance_meters": {"type": ["number", "null"]},
        "recovery_duration_seconds": {"type": ["integer", "null"]},
        "recovery_target": {"anyOf": [{"type": "null"}, _TARGET_SCHEMA]},
        "instruction": {"type": "string", "minLength": 1},
    },
}

SYSTEM_INSTRUCTIONS = """You are Pace's Swedish-language plan-drafting assistant.
Return a reviewable plan draft, never medical advice. Treat the supplied Pace
facts as the complete factual contract about this athlete: do not invent
capacity, prior volume, dates, recovery facts, races, availability, or targets.
You may apply general endurance-coaching knowledge to choose the session mix,
progression, and workout purpose, but never present that knowledge as an
athlete fact, a study, or a specific external source. The athlete's sport role is a preference, not a
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
Every session must include ordered workout_steps, but do not use a fixed
warmup/steady/cooldown template. A simple continuous session such as 50 minutes
in zone 2 must be one steady block and nothing else. Add warmup and cooldown
only when they have a specific coaching purpose, normally for a quality,
technical, or deliberately transition-focused session. A quality workout must
put its repetitions, work distance or duration, recovery, and recovery target
in an interval block; never hide that structure in purpose or instruction text.
Use the smallest set of blocks that makes the intended session executable. The
detailed blocks must respect the same pace, power, RPE, and cycling zone
eligibility as the session.
Choose the workout form from the athlete's documented continuity, current
block purpose, upcoming race priorities, recent feedback, and recovery facts.
The training_continuity fact is the chronological record of actual run and
ride training: it contains Python-calculated latest-7 and latest-14-day
summaries, the most recent 28 daily training rows, and 84 days of seven-day
summaries. Use those calculated values to compare the current pattern with
preceding weeks separately for each sport. A single high week is not
sustainable-capacity evidence by itself. When the latest training is materially
lower after a short high week, treat that as an observed continuity
interruption: begin from the current return pattern instead of escalating
frequency or quality from the peak. State the factual pattern and its
consequence in the assessment. Do not call the interruption illness, injury, or
recovery unless a separate supplied Pace fact supports that claim.
Do not rotate workout types merely for variety, and do not repeat generic easy
sessions merely because they are easy to generate. When facts support quality,
you may choose continuous tempo, progressive work, hills, threshold blocks, or
short/long intervals with an appropriate recovery structure. The session
purpose must state why that workout belongs at that point in the block. A
desired race time is intent, never capacity evidence.
For a target race, use its supplied sport, distance, date, and priority to make
the block race-specific. The goal does not erase documented continuity: do not
force a number of sessions, consecutive training days, or an every-other-day
schedule from a template. Choose frequency and placement from the complete
selected Pace facts, then explain the material reasoning in the assessment.
Only goal.race is the athlete-selected plan target. Do not turn another stored
or upcoming race into a plan objective, taper, race session, or coaching
constraint unless it is supplied as goal.race. If the selected target's date
falls inside the detailed window, it must appear as a same-date, same-sport
session. Respect its supplied A/B/C priority and resolved taper: A is the
primary performance target, B is a hard secondary race with a partial
compromise, and C is treated as a hard training session. Do not silently
promote a B/C target into an A target.
Availability null means no supplied time ceiling; it is never permission to
prescribe unlimited training. Return a coach_assessment with fact_references
as exact ID strings selected only from the supplied fact_catalog, then your inferences, rationale,
uncertainties, and general coaching_principles. The principles are not source
citations. Curated knowledge briefs are optional local support: cite only
supplied brief IDs when one actually supports the assessment, otherwise return
an empty knowledge_references list.
You cannot access Garmin, the local database, private context-note text, or
prior conversations. Do not cite a knowledge brief that was not supplied, and
do not claim that a brief supports more than its supported_claims permit.

training_response_trends is deterministic aggregation of explicit athlete
feedback only. It is not a measure of unreported sessions and cannot establish
why outcomes or RPE changed. Use it only when its status is ready; state its
data limitation plainly when it materially affects the draft.

personalization_evidence is a fresh, deterministic 56-day feedback summary.
Use it only when ready and never turn it into a causal claim. Athlete-confirmed
observed_patterns describe only explicit feedback counts, reported RPE, and
sport-scoped completion among reported sessions. They do not describe
unreported sessions and do not prove why a pattern occurred. Athlete-confirmed
coach principles are explicit preferences with an expiry review; follow only
those supplied as active facts and explain any material effect.

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
                    "workout_steps",
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
                    "workout_steps": {
                        "type": "array",
                        "minItems": 1,
                        "items": _WORKOUT_STEP_SCHEMA,
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
                        + (
                            "\n\nPython rejected the previous candidate. Return a complete new "
                            "JSON plan that corrects this exact validation failure:\n"
                            f"{request.repair_instruction}"
                            if request.repair_instruction is not None
                            else ""
                        )
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
        "scheduled_date", "sport_type", "purpose", "distance_meters", "duration_seconds", "heart_rate_zone", "target", "workout_steps"
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
        workout_steps=tuple(_parse_workout_step(step) for step in item["workout_steps"]),
    )


def _parse_workout_step(item: object) -> WorkoutStepDraft:
    required_fields = {
        "kind", "repetitions", "distance_meters", "duration_seconds", "target",
        "recovery_distance_meters", "recovery_duration_seconds", "recovery_target",
        "instruction",
    }
    if not isinstance(item, dict) or set(item) != required_fields:
        raise PaceAIResponseError("AI-planen hade ogiltiga passblocks-fält.")
    kind = item["kind"]
    repetitions = item["repetitions"]
    if kind not in WORKOUT_STEP_KINDS or not isinstance(repetitions, int) or isinstance(repetitions, bool):
        raise PaceAIResponseError("AI-planen hade ogiltigt passblock.")
    distance = item["distance_meters"]
    duration = item["duration_seconds"]
    recovery_distance = item["recovery_distance_meters"]
    recovery_duration = item["recovery_duration_seconds"]
    for value in (distance, recovery_distance):
        if value is not None and (not isinstance(value, (int, float)) or value <= 0):
            raise PaceAIResponseError("AI-planen hade ogiltig blockdistans.")
    for value in (duration, recovery_duration):
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
            raise PaceAIResponseError("AI-planen hade ogiltig blocktid.")
    if distance is None and duration is None:
        raise PaceAIResponseError("AI-planen hade ett block utan omfattning.")
    recovery_target = item["recovery_target"]
    if kind == "interval":
        if repetitions < 2 or (recovery_distance is None and recovery_duration is None) or recovery_target is None:
            raise PaceAIResponseError("AI-planens intervallblock saknar återhämtning.")
    elif repetitions != 1 or any(value is not None for value in (recovery_distance, recovery_duration, recovery_target)):
        raise PaceAIResponseError("AI-planens vanliga block har ogiltig återhämtning.")
    instruction = item["instruction"]
    if not isinstance(instruction, str) or not instruction.strip():
        raise PaceAIResponseError("AI-planen saknar blockinstruktion.")
    return WorkoutStepDraft(
        kind=kind,
        repetitions=repetitions,
        distance_meters=None if distance is None else float(distance),
        duration_seconds=duration,
        target=_parse_target(item["target"]),
        recovery_distance_meters=None if recovery_distance is None else float(recovery_distance),
        recovery_duration_seconds=recovery_duration,
        recovery_target=None if recovery_target is None else _parse_target(recovery_target),
        instruction=instruction.strip(),
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
