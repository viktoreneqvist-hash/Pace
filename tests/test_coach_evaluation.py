from datetime import date

from pace.coach_evaluation.scenarios import load_scenarios
from pace.planning.draft_models import (
    BlockOutlineItem,
    GeneratedPlanDraft,
    PlannedSessionDraft,
    SessionTargetDraft,
)
from pace.services.coach_evaluation_service import CoachEvaluationService


class SyntheticGenerator:
    def generate(self, request):
        allowed_sports = request.context["fact_catalog"]["evaluation_boundary"]["value"][
            "allowed_sports"
        ]
        return GeneratedPlanDraft(
            block_outline=(
                BlockOutlineItem(date(2026, 7, 27), date(2026, 8, 2), "Syntetiskt."),
            ),
            sessions=(
                PlannedSessionDraft(
                    scheduled_date=date(2026, 7, 28),
                    sport_type=allowed_sports[0],
                    purpose="Syntetiskt kontraktspass.",
                    distance_meters=5_000,
                    duration_seconds=1_800,
                    heart_rate_zone=None,
                    target=SessionTargetDraft("rpe", 2, 3, None, None, None),
                ),
            ),
        )


def test_synthetic_coach_catalog_is_bounded_and_passes_contract_evaluation():
    assert len(load_scenarios()) == 6

    report = CoachEvaluationService().evaluate(generator=SyntheticGenerator())

    assert report.scenario_count == 6
    assert report.passed == 6
    assert report.failed == 0
