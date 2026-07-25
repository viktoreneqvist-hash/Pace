import json
from datetime import date
from pathlib import Path

from pace.integrations.garmin.daily_metrics import normalize_garmin_daily_metric


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "garmin"


def load_fixture(name: str):
    return json.loads((FIXTURES_PATH / name).read_text())


def test_normalize_garmin_daily_recovery_signals():
    metric = normalize_garmin_daily_metric(
        metric_date=date(2026, 6, 14),
        summary=load_fixture("daily_summary.json"),
        sleep=load_fixture("sleep_day.json"),
        hrv=load_fixture("hrv_day.json"),
        readiness=load_fixture("training_readiness_day.json"),
    )

    assert metric.date == date(2026, 6, 14)
    assert metric.hrv_value == 62.5
    assert metric.hrv_status == "BALANCED"
    assert metric.resting_heart_rate == 46
    assert metric.sleep_duration_seconds == 28_800
    assert metric.sleep_score == 84
    assert metric.average_stress == 24
    assert metric.body_battery_high == 82
    assert metric.body_battery_low == 19
    assert metric.training_readiness == 71
    assert metric.recovery_time_hours == 6.0
    assert set(metric.raw_payload) == {"summary", "sleep", "hrv", "training_readiness"}


def test_recovery_time_is_zero_when_garmin_marks_it_complete():
    readiness = load_fixture("training_readiness_day.json")
    readiness[0]["recoveryTime"] = 360
    readiness[0]["recoveryTimeChangePhrase"] = "REACHED_ZERO"

    metric = normalize_garmin_daily_metric(
        metric_date=date(2026, 6, 14),
        summary={},
        sleep={},
        hrv={},
        readiness=readiness,
    )

    assert metric.recovery_time_hours == 0.0
