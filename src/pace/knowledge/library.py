"""Load and validate Pace's checked-in knowledge library."""

import json
from pathlib import Path

from pace.config.settings import PROJECT_ROOT
from pace.knowledge.models import KnowledgeBrief, KnowledgeLibrary, KnowledgeSource


KNOWLEDGE_DIRECTORY = PROJECT_ROOT / "knowledge"
SOURCES_FILE_NAME = "sources.json"
BRIEFS_DIRECTORY_NAME = "briefs"


class KnowledgeLibraryError(ValueError):
    """Raised when checked-in source or brief metadata is malformed."""


def load_knowledge_library(
    *,
    knowledge_directory: Path = KNOWLEDGE_DIRECTORY,
) -> KnowledgeLibrary:
    """Load local curated knowledge without network or database access."""

    source_payload = _load_json(knowledge_directory / SOURCES_FILE_NAME)
    schema_version = _required_int(source_payload, "schema_version")
    sources_raw = _required_list(source_payload, "sources")
    sources = tuple(_parse_source(item) for item in sources_raw)
    source_ids = {source.id for source in sources}
    if len(source_ids) != len(sources):
        raise KnowledgeLibraryError("Knowledge source IDs must be unique.")

    briefs_directory = knowledge_directory / BRIEFS_DIRECTORY_NAME
    brief_paths = sorted(briefs_directory.glob("*.md"))
    if not brief_paths:
        raise KnowledgeLibraryError("Knowledge library must contain at least one brief.")
    briefs = tuple(_parse_brief(path) for path in brief_paths)
    brief_ids = {brief.id for brief in briefs}
    if len(brief_ids) != len(briefs):
        raise KnowledgeLibraryError("Knowledge brief IDs must be unique.")
    unknown_source_ids = {
        source_id for brief in briefs for source_id in brief.source_ids if source_id not in source_ids
    }
    if unknown_source_ids:
        raise KnowledgeLibraryError("Knowledge brief references an unknown source ID.")
    return KnowledgeLibrary(
        schema_version=schema_version,
        sources=sources,
        briefs=briefs,
    )


def brief_by_id(library: KnowledgeLibrary, *, brief_id: str) -> KnowledgeBrief | None:
    """Find one locally reviewed brief without falling back to model knowledge."""

    return next((brief for brief in library.briefs if brief.id == brief_id), None)


def source_by_id(library: KnowledgeLibrary, *, source_id: str) -> KnowledgeSource | None:
    """Find one source record for a displayed brief citation."""

    return next((source for source in library.sources if source.id == source_id), None)


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise KnowledgeLibraryError(f"Could not read knowledge metadata: {path.name}.") from error
    if not isinstance(value, dict):
        raise KnowledgeLibraryError("Knowledge metadata must be a JSON object.")
    return value


def _parse_source(value: object) -> KnowledgeSource:
    if not isinstance(value, dict):
        raise KnowledgeLibraryError("Each knowledge source must be an object.")
    return KnowledgeSource(
        id=_required_text(value, "id"),
        title=_required_text(value, "title"),
        authors=_required_text(value, "authors"),
        publication_year=_required_int(value, "publication_year"),
        evidence_type=_required_text(value, "evidence_type"),
        url=_required_text(value, "url"),
    )


def _parse_brief(path: Path) -> KnowledgeBrief:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise KnowledgeLibraryError(f"Could not read knowledge brief: {path.name}.") from error
    prefix = "---json\n"
    separator = "\n---\n"
    if not content.startswith(prefix) or separator not in content:
        raise KnowledgeLibraryError(f"Knowledge brief has invalid metadata: {path.name}.")
    metadata_text, body = content[len(prefix) :].split(separator, maxsplit=1)
    if not body.strip():
        raise KnowledgeLibraryError(f"Knowledge brief has no human-readable body: {path.name}.")
    try:
        value = json.loads(metadata_text)
    except json.JSONDecodeError as error:
        raise KnowledgeLibraryError(f"Knowledge brief has invalid JSON: {path.name}.") from error
    if not isinstance(value, dict):
        raise KnowledgeLibraryError(f"Knowledge brief metadata must be an object: {path.name}.")
    return KnowledgeBrief(
        id=_required_text(value, "id"),
        title=_required_text(value, "title"),
        topic_tags=_required_text_tuple(value, "topic_tags"),
        source_ids=_required_text_tuple(value, "source_ids"),
        supported_claims=_required_text_tuple(value, "supported_claims"),
        limitations=_required_text_tuple(value, "limitations"),
        applicability=_required_text(value, "applicability"),
    )


def _required_text(value: dict[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise KnowledgeLibraryError(f"Knowledge metadata requires {key}.")
    return item.strip()


def _required_int(value: dict[str, object], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool):
        raise KnowledgeLibraryError(f"Knowledge metadata requires integer {key}.")
    return item


def _required_list(value: dict[str, object], key: str) -> list[object]:
    item = value.get(key)
    if not isinstance(item, list):
        raise KnowledgeLibraryError(f"Knowledge metadata requires list {key}.")
    return item


def _required_text_tuple(value: dict[str, object], key: str) -> tuple[str, ...]:
    item = _required_list(value, key)
    texts = tuple(element.strip() for element in item if isinstance(element, str) and element.strip())
    if not texts or len(texts) != len(item):
        raise KnowledgeLibraryError(f"Knowledge metadata requires non-empty text list {key}.")
    return texts
