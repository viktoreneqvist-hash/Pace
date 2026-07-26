"""Transparent resting-heart-rate and sleep-duration rules for Pace v1."""

from datetime import timedelta

from pace.rules.models import RuleEvaluation
from pace.state.models import AthleteState, RecoveryDayObservation


MIN_RECOVERY_BASELINE_DAYS = 14
RESTING_HEART_RATE_INCREASE_PERCENT = 5
SLEEP_DURATION_DECREASE_PERCENT = 10


def evaluate_resting_heart_rate_baseline_data_quality(
    state: AthleteState,
) -> RuleEvaluation:
    """Expose whether resting heart rate has enough data for its rule."""

    return _baseline_quality_evaluation(
        state,
        metric="resting_heart_rate",
        rule_id="resting_heart_rate_baseline_data_quality",
    )


def evaluate_resting_heart_rate_elevation(state: AthleteState) -> RuleEvaluation:
    """Find two adjacent resting-heart-rate days at least 5 percent above baseline."""

    summary = _metric_summary(state, "resting_heart_rate")
    quality = _metric_quality(state, "resting_heart_rate")
    base_facts = _base_facts(summary, quality)
    if quality.baseline_data_points < MIN_RECOVERY_BASELINE_DAYS:
        return _insufficient_data("resting_heart_rate_elevation", base_facts)
    if summary.baseline_value in (None, 0) or summary.latest_date is None:
        return _missing_data("resting_heart_rate_elevation", base_facts)

    latest_observation = _observation_for_date(state, summary.latest_date)
    previous_date = summary.latest_date - timedelta(days=1)
    previous_observation = _observation_for_date(state, previous_date)
    if latest_observation is None or previous_observation is None:
        return RuleEvaluation(
            rule_id="resting_heart_rate_elevation",
            status="insufficient_data",
            facts=base_facts,
            limitations=("requires_two_consecutive_resting_heart_rate_days",),
        )

    threshold_value = summary.baseline_value * (
        1 + RESTING_HEART_RATE_INCREASE_PERCENT / 100
    )
    both_days_elevated = (
        latest_observation.resting_heart_rate is not None
        and previous_observation.resting_heart_rate is not None
        and latest_observation.resting_heart_rate >= threshold_value
        and previous_observation.resting_heart_rate >= threshold_value
    )
    return RuleEvaluation(
        rule_id="resting_heart_rate_elevation",
        status="triggered" if both_days_elevated else "not_triggered",
        facts={
            **base_facts,
            "signal_dates": (previous_observation.date, latest_observation.date),
            "signal_values": (
                previous_observation.resting_heart_rate,
                latest_observation.resting_heart_rate,
            ),
            "increase_percent_threshold": RESTING_HEART_RATE_INCREASE_PERCENT,
            "threshold_value": threshold_value,
            "two_consecutive_days_elevated": both_days_elevated,
        },
        limitations=(),
    )


def evaluate_sleep_duration_baseline_data_quality(state: AthleteState) -> RuleEvaluation:
    """Expose whether sleep duration has enough data for its rule."""

    return _baseline_quality_evaluation(
        state,
        metric="sleep_duration",
        rule_id="sleep_duration_baseline_data_quality",
    )


def evaluate_sleep_duration_short_night(state: AthleteState) -> RuleEvaluation:
    """Find one sleep duration at least 10 percent below its current baseline."""

    summary = _metric_summary(state, "sleep_duration")
    quality = _metric_quality(state, "sleep_duration")
    base_facts = _base_facts(summary, quality)
    if quality.baseline_data_points < MIN_RECOVERY_BASELINE_DAYS:
        return _insufficient_data("sleep_duration_short_night", base_facts)
    if summary.baseline_value in (None, 0) or summary.latest_date is None:
        return _missing_data("sleep_duration_short_night", base_facts)

    latest_observation = _observation_for_date(state, summary.latest_date)
    if latest_observation is None or latest_observation.sleep_duration_hours is None:
        return RuleEvaluation(
            rule_id="sleep_duration_short_night",
            status="insufficient_data",
            facts=base_facts,
            limitations=("missing_latest_sleep_duration",),
        )

    threshold_value = summary.baseline_value * (
        1 - SLEEP_DURATION_DECREASE_PERCENT / 100
    )
    short_night = latest_observation.sleep_duration_hours <= threshold_value
    return RuleEvaluation(
        rule_id="sleep_duration_short_night",
        status="triggered" if short_night else "not_triggered",
        facts={
            **base_facts,
            "signal_date": latest_observation.date,
            "signal_value": latest_observation.sleep_duration_hours,
            "decrease_percent_threshold": SLEEP_DURATION_DECREASE_PERCENT,
            "threshold_value": threshold_value,
            "night_is_short": short_night,
        },
        limitations=(),
    )


def _baseline_quality_evaluation(
    state: AthleteState,
    *,
    metric: str,
    rule_id: str,
) -> RuleEvaluation:
    quality = _metric_quality(state, metric)
    is_sufficient = quality.baseline_data_points >= MIN_RECOVERY_BASELINE_DAYS
    return RuleEvaluation(
        rule_id=rule_id,
        status="sufficient_data" if is_sufficient else "insufficient_data",
        facts={
            "observed_baseline_days": quality.baseline_data_points,
            "required_baseline_days": MIN_RECOVERY_BASELINE_DAYS,
            "expected_baseline_days": quality.expected_baseline_days,
        },
        limitations=(
            ()
            if is_sufficient
            else (f"insufficient_{metric}_baseline_data",)
        ),
    )


def _base_facts(summary, quality) -> dict[str, object]:
    return {
        "observed_baseline_days": quality.baseline_data_points,
        "required_baseline_days": MIN_RECOVERY_BASELINE_DAYS,
        "baseline_value": summary.baseline_value,
        "latest_date": summary.latest_date,
    }


def _insufficient_data(rule_id: str, facts: dict[str, object]) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule_id,
        status="insufficient_data",
        facts=facts,
        limitations=("insufficient_recovery_baseline_data",),
    )


def _missing_data(rule_id: str, facts: dict[str, object]) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule_id,
        status="insufficient_data",
        facts=facts,
        limitations=("missing_recovery_baseline_or_latest_value",),
    )


def _metric_summary(state: AthleteState, metric: str):
    return next(summary for summary in state.metrics.recovery if summary.metric == metric)


def _metric_quality(state: AthleteState, metric: str):
    return next(quality for quality in state.data_quality.recovery if quality.metric == metric)


def _observation_for_date(
    state: AthleteState,
    target_date,
) -> RecoveryDayObservation | None:
    return next(
        (
            observation
            for observation in state.recent_recovery_observations
            if observation.date == target_date
        ),
        None,
    )
