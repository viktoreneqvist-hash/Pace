from datetime import date

from pace.explanations.hrv import explain_hrv_rules, render_explanation_summary
from pace.explanations.recovery import explain_garmin_current_facts, explain_recovery_rules
from pace.rules.models import RuleEvaluation, RuleEvaluationSummary
from pace.state.models import GarminCurrentFact


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
    assert "7 of at least 14" in summary.items[0].text


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
    assert "may be relevant" in summary.context_check_in.question
    rendered = render_explanation_summary(summary)
    assert "Nothing is saved automatically" in rendered


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
    assert "poor sleep, alcohol" in summary.items[0].text
    assert "not cause" in summary.items[0].text


def test_recovery_explanations_keep_resting_heart_rate_and_sleep_separate():
    summary = _rule_summary(
        _quality_evaluation(status="sufficient_data", observed_days=14),
        _hrv_context_evaluation(status="not_triggered", facts={}),
        RuleEvaluation(
            rule_id="resting_heart_rate_baseline_data_quality",
            status="sufficient_data",
            facts={},
            limitations=(),
        ),
        RuleEvaluation(
            rule_id="resting_heart_rate_elevation",
            status="triggered",
            facts={
                "increase_percent_threshold": 5,
                "signal_dates": (date(2026, 7, 24), date(2026, 7, 25)),
            },
            limitations=(),
        ),
        RuleEvaluation(
            rule_id="sleep_duration_baseline_data_quality",
            status="sufficient_data",
            facts={},
            limitations=(),
        ),
        RuleEvaluation(
            rule_id="sleep_duration_short_night",
            status="triggered",
            facts={
                "decrease_percent_threshold": 10,
                "signal_date": date(2026, 7, 25),
            },
            limitations=(),
        ),
    )

    items = explain_recovery_rules(summary)

    assert items[0].explanation_id == "resting_heart_rate_elevated"
    assert "5%" in items[0].text
    assert items[1].explanation_id == "sleep_duration_short_night"
    assert "10%" in items[1].text


def test_garmin_current_facts_are_presented_without_creating_rules():
    items = explain_garmin_current_facts(
        (
            GarminCurrentFact(
                signal="training_readiness",
                value=71,
                source_date=date(2026, 7, 25),
                is_current=True,
            ),
            GarminCurrentFact(
                signal="recovery_time_hours",
                value=18,
                source_date=date(2026, 7, 24),
                is_current=False,
            ),
        )
    )

    assert items[0].explanation_id == "garmin_current_facts"
    assert "does not use these Garmin values in its own rules" in items[0].text
    assert items[1].explanation_id == "garmin_stale_facts"
    assert "2026-07-24" in items[1].text
