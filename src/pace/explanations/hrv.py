"""English deterministic templates for the reviewed HRV rules."""

from pace.explanations.models import ContextCheckIn, ExplanationItem, ExplanationSummary
from pace.rules.models import RuleEvaluationSummary


EVENT_TYPE_LABELS = {
    "poor_sleep": "poor sleep",
    "alcohol": "alcohol",
    "travel": "travel",
    "work_stress": "work stress",
    "illness": "illness",
}


def explain_hrv_rules(rule_summary: RuleEvaluationSummary) -> ExplanationSummary:
    """Turn approved HRV rule outcomes into concise non-diagnostic English."""

    evaluations = {evaluation.rule_id: evaluation for evaluation in rule_summary.evaluations}
    quality = evaluations["hrv_baseline_data_quality"]
    hrv_context = evaluations["hrv_context_present"]

    if quality.status == "insufficient_data":
        observed_days = quality.facts["observed_baseline_days"]
        required_days = quality.facts["required_baseline_days"]
        return ExplanationSummary(
            as_of_date=rule_summary.as_of_date,
            items=(
                ExplanationItem(
                    explanation_id="hrv_baseline_insufficient",
                    text=(
                        "The HRV baseline is still limited: "
                        f"{observed_days} of at least {required_days} observed days. "
                        "Pace therefore does not interpret HRV yet."
                    ),
                ),
            ),
            context_check_in=None,
        )

    if hrv_context.status == "insufficient_data":
        return ExplanationSummary(
            as_of_date=rule_summary.as_of_date,
            items=(
                ExplanationItem(
                    explanation_id="hrv_consecutive_days_missing",
                    text=(
                        "The HRV baseline is sufficient, but Pace lacks two consecutive "
                        "calendar days of HRV data for evaluating the HRV rule."
                    ),
                ),
            ),
            context_check_in=None,
        )

    if not hrv_context.facts["two_consecutive_days_below_baseline"]:
        return ExplanationSummary(
            as_of_date=rule_summary.as_of_date,
            items=(
                ExplanationItem(
                    explanation_id="hrv_pattern_not_present",
                    text=(
                        "Pace does not see two consecutive HRV days below the "
                        "current baseline in this evaluation."
                    ),
                ),
            ),
            context_check_in=None,
        )

    signal_dates = hrv_context.facts["signal_dates"]
    signal_values = hrv_context.facts["signal_values"]
    baseline_value = hrv_context.facts["baseline_value"]
    observation_text = (
        "Two consecutive HRV days are below the current baseline: "
        f"{signal_dates[0]} ({signal_values[0]:.1f} ms) and "
        f"{signal_dates[1]} ({signal_values[1]:.1f} ms), compared with "
        f"{baseline_value:.1f} ms."
    )
    context_event_types = hrv_context.facts["relevant_context_event_types"]
    if context_event_types:
        event_labels = ", ".join(
            EVENT_TYPE_LABELS[event_type] for event_type in context_event_types
        )
        return ExplanationSummary(
            as_of_date=rule_summary.as_of_date,
            items=(
                ExplanationItem(
                    explanation_id="hrv_pattern_with_context",
                    text=(
                        f"{observation_text} Relevant context recorded nearby in time: "
                        f"{event_labels}. This shows coincidence, not cause."
                    ),
                ),
            ),
            context_check_in=None,
        )

    return ExplanationSummary(
        as_of_date=rule_summary.as_of_date,
        items=(
            ExplanationItem(
                explanation_id="hrv_pattern_without_context",
                text=(
                    f"{observation_text} Pace finds no relevant recorded "
                    "context nearby in time."
                ),
            ),
        ),
        context_check_in=ContextCheckIn(
            question=(
                "Was there anything between "
                f"{hrv_context.facts['context_start_date']} and "
                f"{hrv_context.facts['context_end_date']} that may be relevant, "
                "such as poor sleep, alcohol, travel, work stress, or illness?"
            ),
            suggested_event_types=(
                "poor_sleep",
                "alcohol",
                "travel",
                "work_stress",
                "illness",
            ),
        ),
    )


def render_explanation_summary(summary: ExplanationSummary) -> str:
    """Render concise local CLI text without changing the structured result."""

    lines = [f"Pace explanation ({summary.as_of_date})"]
    lines.extend(f"- {item.text}" for item in summary.items)

    if summary.context_check_in is not None:
        lines.extend(
            [
                "",
                f"Question: {summary.context_check_in.question}",
                "Nothing is saved automatically. Use 'pace note add' if you want to add context.",
            ]
        )

    return "\n".join(lines)
