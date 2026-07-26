"""Swedish deterministic templates for resting-heart-rate and sleep rules."""

from pace.explanations.models import ExplanationItem
from pace.rules.models import RuleEvaluationSummary
from pace.state.models import GarminCurrentFact


GARMIN_SIGNAL_LABELS = {
    "training_readiness": "Garmin training readiness",
    "body_battery_high": "Garmin Body Battery högsta värde",
    "body_battery_low": "Garmin Body Battery lägsta värde",
    "average_stress": "Garmin genomsnittlig stress",
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
                    f"Garmin-status för idag: {values}. "
                    "Pace använder inte dessa Garmin-värden i egna regler."
                ),
            )
        )

    if stale:
        values = ", ".join(
            f"{GARMIN_SIGNAL_LABELS[fact.signal]} från {fact.source_date}"
            for fact in stale
        )
        items.append(
            ExplanationItem(
                explanation_id="garmin_stale_facts",
                text=(
                    f"Senaste Garmin-status är inte aktuell för denna dag: {values}. "
                    "Dessa värden används inte i Pace-regler."
                ),
            )
        )

    return tuple(items)


def _explain_resting_heart_rate(*, quality, pattern) -> ExplanationItem:
    if quality.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="resting_heart_rate_baseline_insufficient",
            text=(
                "Vilopulsunderlaget är ännu begränsat: "
                f"{quality.facts['observed_baseline_days']} av minst "
                f"{quality.facts['required_baseline_days']} observerade dagar."
            ),
        )
    if pattern.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="resting_heart_rate_consecutive_days_missing",
            text=(
                "Vilopulsunderlaget räcker, men Pace saknar två sammanhängande "
                "kalenderdagar med vilopulsdata för att utvärdera mönstret."
            ),
        )
    if pattern.status == "triggered":
        return ExplanationItem(
            explanation_id="resting_heart_rate_elevated",
            text=(
                "Vilopulsen ligger minst "
                f"{pattern.facts['increase_percent_threshold']} % över den aktuella "
                f"baslinjen två dagar i följd ({pattern.facts['signal_dates'][0]} och "
                f"{pattern.facts['signal_dates'][1]}). Detta är en observation, inte "
                "en förklaring eller ett träningsråd."
            ),
        )
    return ExplanationItem(
        explanation_id="resting_heart_rate_pattern_not_present",
        text=(
            "Pace ser inte två sammanhängande vilopulsdagar minst 5 % över den "
            "aktuella baslinjen i den här utvärderingen."
        ),
    )


def _explain_sleep_duration(*, quality, pattern) -> ExplanationItem:
    if quality.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="sleep_duration_baseline_insufficient",
            text=(
                "Sömnlängdsunderlaget är ännu begränsat: "
                f"{quality.facts['observed_baseline_days']} av minst "
                f"{quality.facts['required_baseline_days']} observerade dagar."
            ),
        )
    if pattern.status == "insufficient_data":
        return ExplanationItem(
            explanation_id="sleep_duration_latest_value_missing",
            text=(
                "Sömnlängdsunderlaget räcker, men Pace saknar den senaste "
                "sömnlängden för att utvärdera natten."
            ),
        )
    if pattern.status == "triggered":
        return ExplanationItem(
            explanation_id="sleep_duration_short_night",
            text=(
                "Sömnlängden ligger minst "
                f"{pattern.facts['decrease_percent_threshold']} % under den aktuella "
                f"baslinjen för {pattern.facts['signal_date']}. Detta är en "
                "observation, inte en förklaring eller ett träningsråd."
            ),
        )
    return ExplanationItem(
        explanation_id="sleep_duration_pattern_not_present",
        text=(
            "Pace ser inte en sömnlängd minst 10 % under den aktuella baslinjen "
            "i den här utvärderingen."
        ),
    )


def _format_value(fact: GarminCurrentFact) -> str:
    if fact.signal == "recovery_time_hours":
        return f"{fact.value:.1f} timmar"
    return f"{fact.value:g}"
