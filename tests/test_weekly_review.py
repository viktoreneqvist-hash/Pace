from datetime import date

from pace.presentation.weekly_review import render_weekly_review_html
from pace.weekly_review.models import WeeklyReviewAnswer


def test_weekly_review_html_is_self_contained_and_read_only():
    html = render_weekly_review_html(
        end_date=date(2026, 7, 26),
        answer=WeeklyReviewAnswer(
            summary="Veckan var jämn.",
            observations=("Tre cykelpass.",),
            recommendations=("Följ nästa planerade pass.",),
            uncertainties=("Feedback saknas.",),
            knowledge_references=("progression_continuity",),
        ),
    )

    assert "VECKOREVIEW" in html
    assert "Veckan var jämn." in html
    assert "ändrar inte planen" in html
    assert "https://" not in html
