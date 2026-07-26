"""Persistence queries for athlete-confirmed performance evidence links."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pace.database.models import PerformanceEvidence


def get_evidence_for_activity(
    session: Session, *, activity_id: int
) -> PerformanceEvidence | None:
    statement = select(PerformanceEvidence).where(
        PerformanceEvidence.activity_id == activity_id
    )
    return session.scalar(statement)


def get_evidence_for_race(
    session: Session, *, race_id: int
) -> PerformanceEvidence | None:
    statement = select(PerformanceEvidence).where(PerformanceEvidence.race_id == race_id)
    return session.scalar(statement)


def get_evidence_for_activities(
    session: Session, *, activity_ids: list[int]
) -> dict[int, PerformanceEvidence]:
    if not activity_ids:
        return {}
    statement = select(PerformanceEvidence).where(
        PerformanceEvidence.activity_id.in_(activity_ids)
    )
    return {evidence.activity_id: evidence for evidence in session.scalars(statement)}


def create_performance_evidence(
    session: Session, evidence: PerformanceEvidence
) -> PerformanceEvidence:
    session.add(evidence)
    session.flush()
    return evidence
