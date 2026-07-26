from datetime import date, timedelta

from pace.database.models import ContextEvent, DailyMetric
from pace.database.session import session_scope
from pace.services.rule_service import RuleService


def _store_hrv_history(
    *,
    end_date: date,
    values_by_date: dict[date, float],
) -> None:
    with session_scope() as session:
        session.add_all(
            [
                DailyMetric(
                    date=metric_date,
                    hrv_value=value,
                    raw_payload={},
                )
                for metric_date, value in values_by_date.items()
            ]
        )


def _evaluations_by_rule_id(*, end_date: date):
    summary = RuleService().evaluate(end_date=end_date)
    return {evaluation.rule_id: evaluation for evaluation in summary.evaluations}


def test_hrv_rules_report_insufficient_data_before_fourteen_baseline_days():
    end_date = date(2026, 7, 25)
    _store_hrv_history(
        end_date=end_date,
        values_by_date={
            end_date - timedelta(days=offset): 90.0 for offset in range(13)
        },
    )

    evaluations = _evaluations_by_rule_id(end_date=end_date)

    assert evaluations["hrv_baseline_data_quality"].status == "insufficient_data"
    assert evaluations["hrv_baseline_data_quality"].facts == {
        "observed_baseline_days": 13,
        "required_baseline_days": 14,
        "expected_baseline_days": 28,
    }
    assert evaluations["hrv_context_present"].status == "insufficient_data"
    assert evaluations["hrv_context_present"].limitations == (
        "insufficient_hrv_baseline_data",
    )


def test_hrv_context_rule_triggers_for_two_consecutive_days_and_selected_context():
    end_date = date(2026, 7, 25)
    values_by_date = {
        end_date - timedelta(days=offset): 100.0 for offset in range(14)
    }
    values_by_date[end_date - timedelta(days=1)] = 80.0
    values_by_date[end_date] = 79.0
    _store_hrv_history(end_date=end_date, values_by_date=values_by_date)
    with session_scope() as session:
        session.add_all(
            [
                ContextEvent(
                    event_type="poor_sleep",
                    start_date=end_date - timedelta(days=1),
                    end_date=end_date - timedelta(days=1),
                    note="Private note is deliberately not part of rule output.",
                    affected_metrics=[],
                    status="closed",
                ),
                ContextEvent(
                    event_type="pain",
                    start_date=end_date,
                    end_date=end_date,
                    note="Not selected as HRV context.",
                    affected_metrics=[],
                    status="closed",
                ),
            ]
        )

    evaluations = _evaluations_by_rule_id(end_date=end_date)
    context_evaluation = evaluations["hrv_context_present"]

    assert evaluations["hrv_baseline_data_quality"].status == "sufficient_data"
    assert context_evaluation.status == "triggered"
    assert context_evaluation.facts["signal_dates"] == (
        end_date - timedelta(days=1),
        end_date,
    )
    assert context_evaluation.facts["two_consecutive_days_below_baseline"] is True
    assert context_evaluation.facts["relevant_context_event_types"] == ("poor_sleep",)


def test_hrv_context_rule_requires_two_adjacent_calendar_days():
    end_date = date(2026, 7, 25)
    values_by_date = {
        end_date - timedelta(days=offset): 100.0 for offset in range(15)
    }
    values_by_date.pop(end_date - timedelta(days=1))
    values_by_date[end_date] = 80.0
    _store_hrv_history(end_date=end_date, values_by_date=values_by_date)

    evaluations = _evaluations_by_rule_id(end_date=end_date)

    assert evaluations["hrv_baseline_data_quality"].status == "sufficient_data"
    assert evaluations["hrv_context_present"].status == "insufficient_data"
    assert evaluations["hrv_context_present"].limitations == (
        "requires_two_consecutive_hrv_days",
    )


def test_hrv_context_rule_does_not_trigger_without_selected_context():
    end_date = date(2026, 7, 25)
    values_by_date = {
        end_date - timedelta(days=offset): 100.0 for offset in range(14)
    }
    values_by_date[end_date - timedelta(days=1)] = 80.0
    values_by_date[end_date] = 79.0
    _store_hrv_history(end_date=end_date, values_by_date=values_by_date)

    evaluations = _evaluations_by_rule_id(end_date=end_date)
    context_evaluation = evaluations["hrv_context_present"]

    assert context_evaluation.status == "not_triggered"
    assert context_evaluation.facts["two_consecutive_days_below_baseline"] is True
    assert context_evaluation.facts["relevant_context_event_types"] == ()


def test_resting_heart_rate_rule_requires_two_days_at_least_five_percent_elevated():
    end_date = date(2026, 7, 25)
    with session_scope() as session:
        session.add_all(
            [
                DailyMetric(
                    date=end_date - timedelta(days=offset),
                    resting_heart_rate=54 if offset in (0, 1) else 50,
                    raw_payload={},
                )
                for offset in range(14)
            ]
        )

    evaluations = _evaluations_by_rule_id(end_date=end_date)

    assert (
        evaluations["resting_heart_rate_baseline_data_quality"].status
        == "sufficient_data"
    )
    assert evaluations["resting_heart_rate_elevation"].status == "triggered"
    assert evaluations["resting_heart_rate_elevation"].facts[
        "increase_percent_threshold"
    ] == 5


def test_sleep_duration_rule_triggers_for_one_night_ten_percent_below_baseline():
    end_date = date(2026, 7, 25)
    with session_scope() as session:
        session.add_all(
            [
                DailyMetric(
                    date=end_date - timedelta(days=offset),
                    sleep_duration_seconds=23_400 if offset == 0 else 28_800,
                    raw_payload={},
                )
                for offset in range(14)
            ]
        )

    evaluations = _evaluations_by_rule_id(end_date=end_date)

    assert evaluations["sleep_duration_baseline_data_quality"].status == "sufficient_data"
    assert evaluations["sleep_duration_short_night"].status == "triggered"
    assert evaluations["sleep_duration_short_night"].facts[
        "decrease_percent_threshold"
    ] == 10


def test_sleep_duration_rule_uses_seven_day_data_gate():
    end_date = date(2026, 7, 25)
    with session_scope() as session:
        session.add_all(
            [
                DailyMetric(
                    date=end_date - timedelta(days=offset),
                    sleep_duration_seconds=28_800,
                    raw_payload={},
                )
                for offset in range(7)
            ]
        )

    evaluations = _evaluations_by_rule_id(end_date=end_date)

    assert evaluations["sleep_duration_baseline_data_quality"].status == "sufficient_data"
    assert evaluations["sleep_duration_baseline_data_quality"].facts[
        "required_baseline_days"
    ] == 7
    assert evaluations["sleep_duration_short_night"].status == "not_triggered"
