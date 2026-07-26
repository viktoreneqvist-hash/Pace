import pytest

from pace.ai.client import PaceAIResponseError
from pace.ai.plan_client import SYSTEM_INSTRUCTIONS, _parse_plan


def _payload() -> dict[str, object]:
    return {
        "coach_assessment": {
            "fact_references": ["planning_readiness"],
            "inferences": ["En coachslutsats."],
            "rationale": "Planen prioriterar kontinuitet.",
            "uncertainties": ["Underlaget är begränsat."],
            "coaching_principles": ["Gradvis progression."],
            "knowledge_references": ["progression_continuity"],
        },
        "block_outline": [
            {
                "week_start": "2026-07-26",
                "week_end": "2026-08-01",
                "focus": "Lugn kontinuitet.",
            }
        ],
        "sessions": [
            {
                "scheduled_date": "2026-07-27",
                "sport_type": "run",
                "purpose": "Lugn löpning.",
                "distance_meters": 5_000,
                "duration_seconds": None,
                "heart_rate_zone": None,
                "target": {
                    "kind": "rpe",
                    "rpe_min": 2,
                    "rpe_max": 3,
                    "pace_seconds_per_km": None,
                    "power_watts": None,
                    "evidence_reference_id": None,
                },
            }
        ],
    }


def test_plan_client_parses_a_structured_target_and_separate_coach_assessment():
    plan = _parse_plan(_payload())

    assert plan.coach_assessment.fact_references == ("planning_readiness",)
    assert plan.coach_assessment.inferences == ("En coachslutsats.",)
    assert plan.sessions[0].target.kind == "rpe"
    assert plan.sessions[0].target.rpe_max == 3


def test_plan_client_rejects_an_assessment_that_omits_uncertainties():
    payload = _payload()
    assessment = payload["coach_assessment"]
    assert isinstance(assessment, dict)
    del assessment["uncertainties"]

    with pytest.raises(PaceAIResponseError, match="coachbedömning"):
        _parse_plan(payload)


def test_plan_client_rejects_empty_required_assessment_sections():
    payload = _payload()
    assessment = payload["coach_assessment"]
    assert isinstance(assessment, dict)
    assessment["fact_references"] = []

    with pytest.raises(PaceAIResponseError, match="ogiltigt innehåll"):
        _parse_plan(payload)


def test_plan_client_rejects_legacy_free_text_intensity_fields():
    payload = _payload()
    session = payload["sessions"]
    assert isinstance(session, list)
    item = session[0]
    assert isinstance(item, dict)
    del item["target"]
    item["intensity_target"] = "Z2 eller ungefär 300 W"

    with pytest.raises(PaceAIResponseError, match="passfält"):
        _parse_plan(payload)


def test_plan_client_instructs_a_direct_coach_tone_without_routine_care_referrals():
    assert "direct, unsentimental Swedish endurance coach" in SYSTEM_INSTRUCTIONS
    assert "routine care-provider referrals" in SYSTEM_INSTRUCTIONS
    assert "toughness into recklessness" in SYSTEM_INSTRUCTIONS
