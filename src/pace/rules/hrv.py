"""Explicit, non-diagnostic HRV context rules selected for Pace v1."""

from datetime import timedelta

from pace.rules.models import RuleEvaluation
from pace.state.models import AthleteState, HrvObservation


MIN_HRV_BASELINE_DAYS = 14
HRV_CONTEXT_LOOKBACK_DAYS = 2
HRV_RELEVANT_CONTEXT_TYPES = frozenset(
    {"poor_sleep", "alcohol", "travel", "work_stress", "illness"}
)


def evaluate_hrv_baseline_data_quality(state: AthleteState) -> RuleEvaluation:
    """Expose whether HRV has enough observations for the selected rule."""

    hrv_quality = _hrv_quality(state)
    is_sufficient = hrv_quality.baseline_data_points >= MIN_HRV_BASELINE_DAYS

    return RuleEvaluation(
        rule_id="hrv_baseline_data_quality",
        status="sufficient_data" if is_sufficient else "insufficient_data",
        facts={
            "observed_baseline_days": hrv_quality.baseline_data_points,
            "required_baseline_days": MIN_HRV_BASELINE_DAYS,
            "expected_baseline_days": hrv_quality.expected_baseline_days,
        },
        limitations=() if is_sufficient else ("insufficient_hrv_baseline_data",),
    )


def evaluate_hrv_context_present(state: AthleteState) -> RuleEvaluation:
    """Find selected context around two consecutive below-baseline HRV days."""

    hrv_summary = _hrv_summary(state)
    hrv_quality = _hrv_quality(state)
    base_facts: dict[str, object] = {
        "observed_baseline_days": hrv_quality.baseline_data_points,
        "required_baseline_days": MIN_HRV_BASELINE_DAYS,
        "baseline_value": hrv_summary.baseline_value,
        "latest_hrv_date": hrv_summary.latest_date,
    }

    if hrv_quality.baseline_data_points < MIN_HRV_BASELINE_DAYS:
        return RuleEvaluation(
            rule_id="hrv_context_present",
            status="insufficient_data",
            facts=base_facts,
            limitations=("insufficient_hrv_baseline_data",),
        )
    if hrv_summary.baseline_value is None or hrv_summary.latest_date is None:
        return RuleEvaluation(
            rule_id="hrv_context_present",
            status="insufficient_data",
            facts=base_facts,
            limitations=("missing_hrv_baseline_or_latest_value",),
        )

    latest_observation = _observation_for_date(
        state.recent_hrv_observations,
        hrv_summary.latest_date,
    )
    previous_date = hrv_summary.latest_date - timedelta(days=1)
    previous_observation = _observation_for_date(
        state.recent_hrv_observations,
        previous_date,
    )
    if latest_observation is None or previous_observation is None:
        return RuleEvaluation(
            rule_id="hrv_context_present",
            status="insufficient_data",
            facts=base_facts,
            limitations=("requires_two_consecutive_hrv_days",),
        )

    if previous_date < state.relevant_context.start_date:
        return RuleEvaluation(
            rule_id="hrv_context_present",
            status="insufficient_data",
            facts=base_facts,
            limitations=("context_window_does_not_cover_signal_lookback",),
        )

    both_days_below_baseline = (
        latest_observation.value < hrv_summary.baseline_value
        and previous_observation.value < hrv_summary.baseline_value
    )
    signal_facts = {
        **base_facts,
        "signal_dates": (previous_observation.date, latest_observation.date),
        "signal_values": (previous_observation.value, latest_observation.value),
        "two_consecutive_days_below_baseline": both_days_below_baseline,
    }
    if not both_days_below_baseline:
        return RuleEvaluation(
            rule_id="hrv_context_present",
            status="not_triggered",
            facts=signal_facts,
            limitations=(),
        )

    context_start_date = hrv_summary.latest_date - timedelta(
        days=HRV_CONTEXT_LOOKBACK_DAYS
    )
    context_event_types = tuple(
        event.event_type
        for event in state.relevant_context.events
        if event.event_type in HRV_RELEVANT_CONTEXT_TYPES
        and event.start_date <= hrv_summary.latest_date
        and (event.end_date is None or event.end_date >= context_start_date)
    )
    context_facts = {
        **signal_facts,
        "context_start_date": context_start_date,
        "context_end_date": hrv_summary.latest_date,
        "relevant_context_event_types": context_event_types,
    }
    return RuleEvaluation(
        rule_id="hrv_context_present",
        status="triggered" if context_event_types else "not_triggered",
        facts=context_facts,
        limitations=(),
    )


def _hrv_quality(state: AthleteState):
    """Return the already-computed HRV completeness facts from athlete state."""

    return next(quality for quality in state.data_quality.recovery if quality.metric == "hrv")


def _hrv_summary(state: AthleteState):
    """Return the already-computed HRV summary from athlete state metrics."""

    return next(metric for metric in state.metrics.recovery if metric.metric == "hrv")


def _observation_for_date(
    observations: tuple[HrvObservation, ...],
    target_date,
) -> HrvObservation | None:
    """Find the exact calendar-day HRV fact required by the selected rule."""

    return next(
        (observation for observation in observations if observation.date == target_date),
        None,
    )
