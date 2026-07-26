"""Pure recovery summaries with explicit rolling windows and missing-data facts."""

from collections.abc import Callable
from datetime import date, timedelta
from statistics import fmean

from pace.analysis.models import RecoveryMetricSummary
from pace.database.models import DailyMetric


BASELINE_DAYS = 28
RECENT_DAYS = 7


def _metric_values(
    daily_metrics: list[DailyMetric],
    *,
    start_date: date,
    end_date: date,
    value_getter: Callable[[DailyMetric], float | int | None],
    scale: float,
) -> list[tuple[date, float]]:
    values = [
        (daily_metric.date, float(value) / scale)
        for daily_metric in daily_metrics
        if start_date <= daily_metric.date <= end_date
        and (value := value_getter(daily_metric)) is not None
    ]
    return sorted(values, key=lambda item: item[0])


def summarize_recovery_metric(
    daily_metrics: list[DailyMetric],
    *,
    metric: str,
    unit: str,
    end_date: date,
    value_getter: Callable[[DailyMetric], float | int | None],
    scale: float = 1,
) -> RecoveryMetricSummary:
    """Calculate a 28-day baseline and a seven-day recent average.

    The baseline includes every available daily value in the trailing 28
    calendar days. Its data-point count makes incomplete history explicit;
    this function does not invent a missing baseline or interpret its meaning.
    """

    baseline_start_date = end_date - timedelta(days=BASELINE_DAYS - 1)
    recent_start_date = end_date - timedelta(days=RECENT_DAYS - 1)
    baseline_values = _metric_values(
        daily_metrics,
        start_date=baseline_start_date,
        end_date=end_date,
        value_getter=value_getter,
        scale=scale,
    )
    recent_values = _metric_values(
        daily_metrics,
        start_date=recent_start_date,
        end_date=end_date,
        value_getter=value_getter,
        scale=scale,
    )

    baseline_value = (
        fmean(value for _, value in baseline_values) if baseline_values else None
    )
    recent_value = fmean(value for _, value in recent_values) if recent_values else None
    latest_date, latest_value = baseline_values[-1] if baseline_values else (None, None)
    latest_deviation_percent = (
        (latest_value - baseline_value) / baseline_value * 100
        if latest_value is not None and baseline_value not in (None, 0)
        else None
    )

    return RecoveryMetricSummary(
        metric=metric,
        unit=unit,
        baseline_start_date=baseline_start_date,
        baseline_end_date=end_date,
        baseline_value=baseline_value,
        baseline_data_points=len(baseline_values),
        expected_baseline_days=BASELINE_DAYS,
        recent_start_date=recent_start_date,
        recent_end_date=end_date,
        recent_value=recent_value,
        recent_data_points=len(recent_values),
        latest_value=latest_value,
        latest_date=latest_date,
        latest_deviation_percent=latest_deviation_percent,
    )


def summarize_recovery(
    daily_metrics: list[DailyMetric],
    *,
    end_date: date,
) -> tuple[RecoveryMetricSummary, ...]:
    """Return the initial, coaching-relevant recovery summaries."""

    return (
        summarize_recovery_metric(
            daily_metrics,
            metric="hrv",
            unit="ms",
            end_date=end_date,
            value_getter=lambda metric: metric.hrv_value,
        ),
        summarize_recovery_metric(
            daily_metrics,
            metric="resting_heart_rate",
            unit="bpm",
            end_date=end_date,
            value_getter=lambda metric: metric.resting_heart_rate,
        ),
        summarize_recovery_metric(
            daily_metrics,
            metric="sleep_duration",
            unit="hours",
            end_date=end_date,
            value_getter=lambda metric: metric.sleep_duration_seconds,
            scale=3600,
        ),
    )
