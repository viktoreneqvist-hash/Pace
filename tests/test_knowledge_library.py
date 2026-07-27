from datetime import date

from pace.knowledge.library import load_knowledge_library
from pace.knowledge.selection import (
    MAX_SELECTED_BRIEFS,
    select_for_plan_context,
    select_for_question,
    serialize_selected_briefs,
)


def test_checked_in_library_has_resolvable_sources_for_every_brief():
    library = load_knowledge_library()

    assert library.schema_version == 1
    assert len(library.sources) >= 15
    assert len(library.briefs) >= 50
    source_ids = {source.id for source in library.sources}
    assert all(set(brief.source_ids).issubset(source_ids) for brief in library.briefs)


def test_question_selection_is_local_bounded_and_recovery_relevant():
    library = load_knowledge_library()

    selected = select_for_question(library, question="Vad betyder lägre HRV för återhämtning?")

    assert 1 <= len(selected) <= MAX_SELECTED_BRIEFS
    assert any("hrv" in brief.id for brief in selected)
    serialized = serialize_selected_briefs(library, briefs=selected)
    assert serialized["library_schema_version"] == 1
    assert all("supported_claims" in item for item in serialized["briefs"])
    assert all("body" not in item for item in serialized["briefs"])


def test_plan_selection_includes_taper_and_run_ride_for_relevant_local_facts():
    library = load_knowledge_library()
    context = {
        "fact_catalog": {
            "goal": {"value": {"race": {"race_date": date(2026, 9, 1)}}},
            "capacity_profile": {
                "value": {"sports": [{"sport_type": "run"}, {"sport_type": "ride"}]}
            },
        }
    }

    selected = select_for_plan_context(library, context=context)

    selected_tags = {
        tag
        for brief in selected
        for tag in brief.topic_tags
    }
    assert "taper" in selected_tags
    assert "run_ride" in selected_tags
