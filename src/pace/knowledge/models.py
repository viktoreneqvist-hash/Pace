"""Typed local contracts for curated Pace knowledge."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    """One external source described locally, never fetched at runtime."""

    id: str
    title: str
    authors: str
    publication_year: int
    evidence_type: str
    url: str


@dataclass(frozen=True, slots=True)
class KnowledgeBrief:
    """A reviewable Pace summary with source IDs and explicit limitations."""

    id: str
    title: str
    topic_tags: tuple[str, ...]
    source_ids: tuple[str, ...]
    supported_claims: tuple[str, ...]
    limitations: tuple[str, ...]
    applicability: str


@dataclass(frozen=True, slots=True)
class KnowledgeLibrary:
    """All reviewed source metadata and briefs available to the current build."""

    schema_version: int
    sources: tuple[KnowledgeSource, ...]
    briefs: tuple[KnowledgeBrief, ...]


@dataclass(frozen=True, slots=True)
class SelectedKnowledgeBrief:
    """A compact brief selected deterministically for one bounded AI call."""

    id: str
    title: str
    topic_tags: tuple[str, ...]
    source_ids: tuple[str, ...]
    supported_claims: tuple[str, ...]
    limitations: tuple[str, ...]
    applicability: str
