from datetime import date
from types import SimpleNamespace

import pytest

from pace.ai.client import PaceAIUnavailableError
from pace.presentation.weekly_review import (
    load_weekly_review_snapshot,
    render_weekly_review_html,
    write_weekly_review_html,
)
from pace.weekly_review.client import WeeklyReviewClient
from pace.weekly_review.models import WeeklyReviewAnswer
from pace.weekly_review.models import WeeklyReviewRequest


def test_weekly_review_html_is_self_contained_and_read_only():
    html = render_weekly_review_html(
        end_date=date(2026, 7, 26),
        answer=WeeklyReviewAnswer(
            summary="Veckan var jämn.",
            observations=("Tre cykelpass.",),
            coach_assessment=("Kontinuiteten är viktigare än mer intensitet nu.",),
            recommendations=("Följ nästa planerade pass.",),
            uncertainties=("Feedback saknas.",),
            knowledge_references=("progression_continuity",),
        ),
    )

    assert "WEEKLY REVIEW" in html
    assert "Veckan var jämn." in html
    assert "Coach assessment" in html
    assert "does not change the plan" in html
    assert "https://" not in html


def test_weekly_review_persists_a_snapshot_for_the_loopback_app(tmp_path):
    answer = WeeklyReviewAnswer(
        summary="Veckan var jämn.",
        observations=("Tre cykelpass.",),
        coach_assessment=("Kontinuitet först.",),
        recommendations=("Följ planen.",),
        uncertainties=("Feedback saknas.",),
        knowledge_references=(),
    )

    write_weekly_review_html(
        end_date=date(2026, 7, 26), answer=answer, reports_directory=tmp_path
    )
    snapshot = load_weekly_review_snapshot(reports_directory=tmp_path)

    assert snapshot is not None
    assert snapshot.end_date == date(2026, 7, 26)
    assert snapshot.summary == "Veckan var jämn."


class FailingResponses:
    def create(self, **_kwargs):
        raise RateLimitFailure()


class RateLimitFailure(Exception):
    status_code = 429


def test_weekly_review_explains_rate_limit_without_provider_detail():
    client = WeeklyReviewClient(
        api_key="test-key",
        model="test-model",
        client=type("Client", (), {"responses": FailingResponses()})(),
    )

    with pytest.raises(PaceAIUnavailableError, match="HTTP 429"):
        client.review(WeeklyReviewRequest(context={}))


def test_weekly_review_discards_unselected_knowledge_references():
    response = SimpleNamespace(
        output_text=(
            '{"summary":"Veckan var jämn.","observations":["Tre cykelpass."],'
            '"coach_assessment":["Kontinuitet före mer intensitet."],'
            '"recommendations":["Följ planen."],"uncertainties":[], '
            '"knowledge_references":["general_endurance_knowledge"]}'
        )
    )
    client = WeeklyReviewClient(
        api_key="test-key",
        model="test-model",
        client=SimpleNamespace(responses=type("Responses", (), {"create": lambda *_args, **_kwargs: response})()),
    )

    answer = client.review(
        WeeklyReviewRequest(context={"knowledge_briefs": {"briefs": [{"id": "known"}]}})
    )

    assert answer.coach_assessment == ("Kontinuitet före mer intensitet.",)
    assert answer.knowledge_references == ()
