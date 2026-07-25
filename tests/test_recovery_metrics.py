from datetime import date

from pace.analysis.recovery_metrics import summarize_recovery
from pace.database.models import DailyMetric


def metric(metric_date: date, *, hrv: float, resting_hr: int, sleep_seconds: int):
    return DailyMetric(
        date=metric_date,
        hrv_value=hrv,
        resting_heart_rate=resting_hr,
        sleep_duration_seconds=sleep_seconds,
        raw_payload={},
    )


def test_recovery_summary_exposes_available_data_points_for_a_28_day_baseline():
    summary = summarize_recovery(
        [
            metric(date(2026, 6, 1), hrv=50, resting_hr=45, sleep_seconds=25200),
            metric(date(2026, 6, 14), hrv=60, resting_hr=50, sleep_seconds=28800),
        ],
        end_date=date(2026, 6, 14),
    )

    hrv = summary[0]
    sleep = summary[2]

    assert hrv.baseline_start_date == date(2026, 5, 18)
    assert hrv.baseline_data_points == 2
    assert hrv.expected_baseline_days == 28
    assert hrv.baseline_value == 55
    assert hrv.recent_data_points == 1
    assert hrv.latest_value == 60
    assert hrv.latest_date == date(2026, 6, 14)
    assert round(hrv.latest_deviation_percent or 0, 2) == 9.09
    assert sleep.unit == "hours"
    assert sleep.baseline_value == 7.5


def test_recovery_summary_keeps_missing_signals_explicit():
    summary = summarize_recovery([], end_date=date(2026, 6, 14))

    assert all(metric.baseline_value is None for metric in summary)
    assert all(metric.latest_value is None for metric in summary)
    assert all(metric.baseline_data_points == 0 for metric in summary)
