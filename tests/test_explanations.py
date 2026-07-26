from datetime import date

from pace.explanations.hrv import explain_hrv_rules, render_explanation_summary
from pace.rules.models import RuleEvaluation, RuleEvaluationSummary


def _rule_summary(*evaluations: RuleEvaluation) -> RuleEvaluationSummary:
    return RuleEvaluationSummary(
        as_of_date=date(2026, 7, 25),
        evaluations=evaluations,
    )


def _quality_evaluation(*, status: str, observed_days: int) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id="hrv_baseline_data_quality",
        status=status,
        facts={
            "observed_baseline_days": observed_days,
            "required_baseline_days": 14,
            "expected_baseline_days": 28,
        },
        limitations=(),
    )


def _hrv_context_evaluation(*, status: str, facts: dict[str, object]) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id="hrv_context_present",
        status=status,
        facts=facts,
        limitations=(),
    )


def test_explanation_reports_insufficient_hrv_data_without_a_check_in():
    summary = explain_hrv_rules(
        _rule_summary(
            _quality_evaluation(status="insufficient_data", observed_days=7),
            _hrv_context_evaluation(status="insufficient_data", facts={}),
        )
    )

    assert summary.context_check_in is None
    assert summary.items[0].explanation_id == "hrv_baseline_insufficient"
    assert "7 av minst 14" in summary.items[0].text


def test_explanation_asks_a_neutral_check_in_only_for_signal_without_context():
    summary = explain_hrv_rules(
        _rule_summary(
            _quality_evaluation(status="sufficient_data", observed_days=14),
            _hrv_context_evaluation(
                status="not_triggered",
                facts={
                    "two_consecutive_days_below_baseline": True,
                    "signal_dates": (date(2026, 7, 24), date(2026, 7, 25)),
                    "signal_values": (80.0, 79.0),
                    "baseline_value": 96.0,
                    "relevant_context_event_types": (),
                    "context_start_date": date(2026, 7, 23),
                    "context_end_date": date(2026, 7, 25),
                },
            ),
        )
    )

    assert summary.items[0].explanation_id == "hrv_pattern_without_context"
    assert summary.context_check_in is not None
    assert "kan vara relevant" in summary.context_check_in.question
    rendered = render_explanation_summary(summary)
    assert "Inget sparas automatiskt" in rendered


def test_explanation_describes_selected_context_without_claiming_causality():
    summary = explain_hrv_rules(
        _rule_summary(
            _quality_evaluation(status="sufficient_data", observed_days=14),
            _hrv_context_evaluation(
                status="triggered",
                facts={
                    "two_consecutive_days_below_baseline": True,
                    "signal_dates": (date(2026, 7, 24), date(2026, 7, 25)),
                    "signal_values": (80.0, 79.0),
                    "baseline_value": 96.0,
                    "relevant_context_event_types": ("poor_sleep", "alcohol"),
                },
            ),
        )
    )

    assert summary.context_check_in is None
    assert summary.items[0].explanation_id == "hrv_pattern_with_context"
    assert "dålig sömn, alkohol" in summary.items[0].text
    assert "inte en orsak" in summary.items[0].text
