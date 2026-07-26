"""Swedish deterministic templates for the reviewed HRV rules."""

from pace.explanations.models import ContextCheckIn, ExplanationItem, ExplanationSummary
from pace.rules.models import RuleEvaluationSummary


EVENT_TYPE_LABELS = {
    "poor_sleep": "dålig sömn",
    "alcohol": "alkohol",
    "travel": "resa",
    "work_stress": "arbetsstress",
    "illness": "sjukdom",
}


def explain_hrv_rules(rule_summary: RuleEvaluationSummary) -> ExplanationSummary:
    """Turn approved HRV rule outcomes into concise non-diagnostic Swedish."""

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
                        "HRV-underlaget är ännu begränsat: "
                        f"{observed_days} av minst {required_days} observerade dagar. "
                        "Därför gör Pace ingen HRV-tolkning ännu."
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
                        "HRV-underlaget räcker, men Pace saknar två sammanhängande "
                        "kalenderdagar med HRV-data för att utvärdera HRV-regeln."
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
                        "Pace ser inte två sammanhängande HRV-dagar under den "
                        "aktuella baslinjen i den här utvärderingen."
                    ),
                ),
            ),
            context_check_in=None,
        )

    signal_dates = hrv_context.facts["signal_dates"]
    signal_values = hrv_context.facts["signal_values"]
    baseline_value = hrv_context.facts["baseline_value"]
    observation_text = (
        "Två HRV-dagar i följd ligger under den aktuella baslinjen: "
        f"{signal_dates[0]} ({signal_values[0]:.1f} ms) och "
        f"{signal_dates[1]} ({signal_values[1]:.1f} ms), jämfört med "
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
                        f"{observation_text} Registrerad relevant kontext nära i tid: "
                        f"{event_labels}. Detta visar ett sammanfall, inte en orsak."
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
                    f"{observation_text} Pace hittar ingen registrerad relevant "
                    "kontext nära i tid."
                ),
            ),
        ),
        context_check_in=ContextCheckIn(
            question=(
                "Fanns det något mellan "
                f"{hrv_context.facts['context_start_date']} och "
                f"{hrv_context.facts['context_end_date']} som kan vara relevant, "
                "till exempel dålig sömn, alkohol, resa, arbetsstress eller sjukdom?"
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

    lines = [f"Pace-förklaring ({summary.as_of_date})"]
    lines.extend(f"- {item.text}" for item in summary.items)

    if summary.context_check_in is not None:
        lines.extend(
            [
                "",
                f"Fråga: {summary.context_check_in.question}",
                "Inget sparas automatiskt. Använd 'pace note add' om du vill lägga till kontext.",
            ]
        )

    return "\n".join(lines)
