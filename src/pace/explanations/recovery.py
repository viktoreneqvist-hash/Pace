"""English deterministic templates for resting-heart-rate and sleep rules."""

from pace.explanations.models import ExplanationItem
from pace.rules.models import RuleEvaluationSummary
from pace.state.models import GarminCurrentFact


GARMIN_SIGNAL_LABELS = {
    "training_readiness": "Garmin training readiness",
    "body_battery_high": "Garmin Body Battery high",
    "body_battery_low": "Garmin Body Battery low",
    "average_stress": "Garmin average stress",
    "recovery_time_hours": "Garmin recovery time",
}


def explain_recovery_rules(rule_summary: RuleEvaluationSummary) -> tuple[ExplanationItem, ...]:
    """Explain the selected resting-heart-rate and sleep rule outcomes."""

    evaluations = {evaluation.rule_id: evaluation for evaluation in rule_summary.evaluations}
    return (
        _explain_resting_heart_rate(
            quality=evaluations["resting_heart_rate_baseline_data_quality"],
            pattern=evaluations["resting_heart_rate_elevation"],
        ),
        _explain_sleep_duration(
            quality=evaluations["sleep_duration_baseline_data_quality"],
            pattern=evaluations["sleep_duration_short_night"],
        ),
    )


def explain_garmin_current_facts(
    facts: tuple[GarminCurrentFact, ...],
) -> tuple[ExplanationItem, ...]:
    """Present Garmin-owned status values without making Pace rules from them."""

    current = [fact for fact in facts if fact.value is not None and fact.is_current]
    stale = [fact for fact in facts if fact.value is not None and not fact.is_current]
    items: list[ExplanationItem] = []

    if current:
        values = ", ".join(
            f"{GARMIN_SIGNAL_LABELS[fact.signal]}: {_format_value(fact)}"
            for fact in current
        )
        items.append(
            ExplanationItem(
                explanation_id="garmin_current_facts",
                text=(
                    f"Garmin status for today: {values}. "
                    "Pace does not use these Garmin values in its own rules."
                ),
            )
        )

    if stale:
        values = ", ".join(
            f"{GARMIN_SIGNAL_LABELS[fact.signal]} from {fact.source_date}"
            for fact in stale
        )
        items.append(
            ExplanationItem(
                explanation_id="garmin_stale_facts",
                text=(
                    f"The latest Garmin status is not current for this day: {values}. "
                    "These values are not used in Pace rules."
                ),
            )
        )

    return tuple(items)


def _explain_resting_heart_rate(*, quality, pattern) -> ExplanationItem:
    if quality.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="resting_heart_rate_baseline_insufficient",
            text=(
                "The resting-heart-rate baseline is still limited: "
                f"{quality.facts['observed_baseline_days']} of at least "
                f"{quality.facts['required_baseline_days']} observed days."
            ),
        )
    if pattern.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="resting_heart_rate_consecutive_days_missing",
            text=(
                "The resting-heart-rate baseline is sufficient, but Pace lacks two consecutive "
                "calendar days of resting-heart-rate data for evaluating the pattern."
            ),
        )
    if pattern.status == "triggered":
        return ExplanationItem(
            explanation_id="resting_heart_rate_elevated",
            text=(
                "Resting heart rate is at least "
                f"{pattern.facts['increase_percent_threshold']}% above the current "
                f"baseline on two consecutive days ({pattern.facts['signal_dates'][0]} and "
                f"{pattern.facts['signal_dates'][1]}). This is an observation, not "
                "an explanation or training recommendation."
            ),
        )
    return ExplanationItem(
        explanation_id="resting_heart_rate_pattern_not_present",
        text=(
            "Pace does not see two consecutive resting-heart-rate days at least 5% above the "
            "current baseline in this evaluation."
        ),
    )


def _explain_sleep_duration(*, quality, pattern) -> ExplanationItem:
    if quality.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="sleep_duration_baseline_insufficient",
            text=(
                "The sleep-duration baseline is still limited: "
                f"{quality.facts['observed_baseline_days']} of at least "
                f"{quality.facts['required_baseline_days']} observed days."
            ),
        )
    if pattern.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="sleep_duration_latest_value_missing",
            text=(
                "The sleep-duration baseline is sufficient, but Pace lacks the latest "
                "sleep duration for evaluating the night."
            ),
        )
    if pattern.status == "triggered":
        return ExplanationItem(
            explanation_id="sleep_duration_short_night",
            text=(
                "Sleep duration is at least "
                f"{pattern.facts['decrease_percent_threshold']}% below the current "
                f"baseline for {pattern.facts['signal_date']}. This is an "
                "observation, not an explanation or training recommendation."
            ),
        )
    return ExplanationItem(
        explanation_id="sleep_duration_pattern_not_present",
        text=(
            "Pace does not see sleep duration at least 10% below the current baseline "
            "in this evaluation."
        ),
    )


def _format_value(fact: GarminCurrentFact) -> str:
    if fact.signal == "recovery_time_hours":
        return f"{fact.value:.1f} hours"
    return f"{fact.value:g}"
