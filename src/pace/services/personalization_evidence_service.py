"""Derive current, non-persistent feedback evidence for L3."""

from collections import Counter
from datetime import date, timedelta

from pace.database.session import session_scope
from pace.personalization.models import PersonalizationEvidence
from pace.repositories.training_plan_repository import list_feedback_trend_records


class PersonalizationEvidenceService:
    def get_evidence(self, *, end_date: date) -> PersonalizationEvidence:
        start_date = end_date - timedelta(days=55)
        with session_scope() as session:
            records = list_feedback_trend_records(session, start_date=start_date, end_date=end_date)
        sports = tuple(sorted(Counter(item.sport_type for item in records).items()))
        ready = len(records) >= 12
        limitations = ["explicit_feedback_only"]
        if not ready:
            limitations.append("insufficient_56_day_feedback")
        if not any(count >= 4 for _, count in sports):
            limitations.append("insufficient_same_sport_feedback")
        return PersonalizationEvidence(end_date, start_date, len(records), 12, sports, 4, "ready" if ready else "insufficient_data", tuple(limitations))
