"""Deterministically select a small relevant subset of local knowledge."""

from pace.knowledge.models import KnowledgeBrief, KnowledgeLibrary, SelectedKnowledgeBrief


MAX_SELECTED_BRIEFS = 5
_TAG_WEIGHTS = {
    # Topic-specific evidence should not be crowded out by the two general
    # planning tags when the local facts clearly indicate a narrower topic.
    "recovery": 20,
    "run_ride": 20,
    "taper": 20,
    # A named race distance is a much more precise planning signal than the
    # generic planning tags. It must therefore win a slot when the local goal
    # unambiguously identifies it, without becoming a fixed workout template.
    "run_10k": 25,
    "workout_structure": 3,
    "race_pacing": 3,
    "strength": 2,
    "cycling": 2,
    "sleep": 2,
    "progression": 1,
    "intensity": 1,
}


def select_for_question(
    library: KnowledgeLibrary,
    *,
    question: str,
) -> tuple[SelectedKnowledgeBrief, ...]:
    """Select topic-tagged briefs without an LLM, embedding, or web lookup."""

    normalized = question.casefold()
    tags = {"progression", "intensity"}
    if any(term in normalized for term in ("taper", "lopp", "race", "maraton")):
        tags.add("taper")
    if any(term in normalized for term in ("hrv", "återhämt", "sömn")):
        tags.add("recovery")
    if any(term in normalized for term in ("intervall", "400", "1 km", "passupplägg")):
        tags.add("workout_structure")
    if any(term in normalized for term in ("styrk", "gym", "plyometr")):
        tags.add("strength")
    if any(term in normalized for term in ("fart", "pacing", "öppna", "disponera")):
        tags.add("race_pacing")
    if any(term in normalized for term in ("cykel", "cycling", "ride")):
        tags.add("cycling")
    if any(term in normalized for term in ("cykel", "cycling", "ride")) and any(
        term in normalized for term in ("löp", "running", "run")
    ):
        tags.add("run_ride")
    return select_for_tags(library, tags=tags)


def select_for_plan_context(
    library: KnowledgeLibrary,
    *,
    context: dict[str, object],
) -> tuple[SelectedKnowledgeBrief, ...]:
    """Select plan knowledge from bounded Pace context, not model judgment."""

    tags = {"progression", "intensity", "workout_structure"}
    fact_catalog = context.get("fact_catalog")
    if isinstance(fact_catalog, dict):
        goal = _catalog_value(fact_catalog, "goal")
        if isinstance(goal, dict) and goal.get("race") is not None:
            tags.add("taper")
            race = goal.get("race")
            if isinstance(race, dict) and race.get("sport_type") == "run":
                tags.add("race_pacing")
                distance_meters = race.get("distance_meters")
                if isinstance(distance_meters, (int, float)) and 8_000 <= distance_meters <= 12_000:
                    tags.add("run_10k")
        capacity = _catalog_value(fact_catalog, "capacity_profile")
        if isinstance(capacity, dict):
            sports = capacity.get("sports")
            if isinstance(sports, list) and {item.get("sport_type") for item in sports if isinstance(item, dict)} >= {"run", "ride"}:
                tags.add("run_ride")
            if isinstance(sports, list) and any(
                item.get("sport_type") == "ride" for item in sports if isinstance(item, dict)
            ):
                tags.add("cycling")
    return select_for_tags(library, tags=tags)


def select_for_tags(
    library: KnowledgeLibrary,
    *,
    tags: set[str],
) -> tuple[SelectedKnowledgeBrief, ...]:
    """Rank overlap deterministically and send only a bounded compact contract."""

    ranked = sorted(
        library.briefs,
        key=lambda brief: (-_tag_score(brief, tags=tags), brief.id),
    )
    selected = [brief for brief in ranked if set(brief.topic_tags).intersection(tags)]
    return tuple(_selected(brief) for brief in selected[:MAX_SELECTED_BRIEFS])


def serialize_selected_briefs(
    library: KnowledgeLibrary,
    *,
    briefs: tuple[SelectedKnowledgeBrief, ...],
) -> dict[str, object]:
    """Build the only research-shaped contract permitted to cross the AI boundary."""

    return {
        "library_schema_version": library.schema_version,
        "briefs": [
            {
                "id": brief.id,
                "title": brief.title,
                "topic_tags": list(brief.topic_tags),
                "source_ids": list(brief.source_ids),
                "supported_claims": list(brief.supported_claims),
                "limitations": list(brief.limitations),
                "applicability": brief.applicability,
            }
            for brief in briefs
        ],
    }


def _catalog_value(catalog: dict[str, object], key: str) -> object:
    entry = catalog.get(key)
    return entry.get("value") if isinstance(entry, dict) else None


def _selected(brief: KnowledgeBrief) -> SelectedKnowledgeBrief:
    return SelectedKnowledgeBrief(
        id=brief.id,
        title=brief.title,
        topic_tags=brief.topic_tags,
        source_ids=brief.source_ids,
        supported_claims=brief.supported_claims,
        limitations=brief.limitations,
        applicability=brief.applicability,
    )


def _tag_score(brief: KnowledgeBrief, *, tags: set[str]) -> int:
    return sum(_TAG_WEIGHTS.get(tag, 1) for tag in set(brief.topic_tags).intersection(tags))
