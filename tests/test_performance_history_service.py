from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from pace.database.models import (
    Activity,
    ActivityPerformanceDetail,
    PerformanceEvidence,
    PerformanceSyncRun,
    Race,
    SyncRun,
)
from pace.database.session import SessionFactory, session_scope
from pace.integrations.garmin.client import GarminIntegrationError, GarminRateLimitError
from pace.services.performance_history_service import PerformanceHistoryService


def _activity(identifier: str, activity_date: date, sport_type: str = "run") -> Activity:
    return Activity(
        provider="garmin",
        provider_activity_id=identifier,
        sport_type=sport_type,
        start_time=datetime.combine(activity_date, datetime.min.time(), tzinfo=UTC),
        duration_seconds=1_800,
        distance_meters=5_000,
        raw_payload={"synthetic_only": True},
    )


class StubPerformanceSource:
    def __init__(self, *, split_error: Exception | None = None) -> None:
        self.split_error = split_error
        self.detail_requests: list[str] = []
        self.split_requests: list[str] = []

    def get_activity_performance_detail(self, activity_id: str):
        self.detail_requests.append(activity_id)
        return {
            "activityDetailDTO": {
                "duration": 1_805,
                "distance": 5_010,
                "averageHR": 151,
                "maxHR": 170,
                "averageSpeed": 2.77,
                "averagePower": 250,
            },
            "geoPolylineDTO": {"polyline": "must-not-be-stored"},
            "chartData": [{"latitude": 59.3, "longitude": 18.0}],
        }

    def get_activity_splits(self, activity_id: str):
        self.split_requests.append(activity_id)
        if self.split_error is not None:
            raise self.split_error
        return {
            "lapDTOs": [
                {
                    "duration": 900,
                    "distance": 2_500,
                    "averageHR": 150,
                    "averageSpeed": 2.78,
                    "averagePower": 245,
                    "startLatitude": 59.3,
                    "startLongitude": 18.0,
                },
                {
                    "duration": 905,
                    "distance": 2_510,
                    "averageHR": 152,
                    "averageSpeed": 2.76,
                    "averagePower": 255,
                    "startLatitude": 59.4,
                    "startLongitude": 18.1,
                },
            ]
        }


def test_detail_sync_stores_only_normalized_run_ride_detail_and_splits():
    with session_scope() as session:
        session.add_all(
            [
                _activity("run-1", date(2026, 7, 20), "run"),
                _activity("ride-1", date(2026, 7, 21), "ride"),
                _activity("other-1", date(2026, 7, 22), "other"),
            ]
        )

    source = StubPerformanceSource()
    result = PerformanceHistoryService(source).sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 26)
    )

    assert result.status == "success"
    assert result.candidate_activities == 2
    assert result.details_fetched == 2
    assert result.details_inserted == 2
    assert source.detail_requests == ["run-1", "ride-1"]
    with SessionFactory() as session:
        details = session.scalars(select(ActivityPerformanceDetail)).all()
        audit = session.scalar(select(PerformanceSyncRun))

    assert len(details) == 2
    assert details[0].splits[0] == {
        "split_number": 1,
        "duration_seconds": 900,
        "distance_meters": 2_500.0,
        "average_heart_rate": 150,
        "average_speed_mps": 2.78,
        "average_cadence": None,
        "average_power": 245.0,
    }
    assert "latitude" not in str(details[0].splits)
    assert audit is not None
    assert audit.status == "success"
    assert audit.candidate_activities == 2


def test_identical_detail_resync_reports_no_updates():
    with session_scope() as session:
        session.add(_activity("run-1", date(2026, 7, 20)))
    service = PerformanceHistoryService(StubPerformanceSource())

    service.sync_details(start_date=date(2026, 7, 20), end_date=date(2026, 7, 20))
    result = service.sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 20)
    )

    assert result.details_inserted == 0
    assert result.details_updated == 0


def test_failed_split_preserves_an_existing_detail_and_marks_partial():
    with session_scope() as session:
        session.add(_activity("run-1", date(2026, 7, 20)))
    PerformanceHistoryService(StubPerformanceSource()).sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 20)
    )

    result = PerformanceHistoryService(
        StubPerformanceSource(split_error=GarminIntegrationError("split unavailable"))
    ).sync_details(start_date=date(2026, 7, 20), end_date=date(2026, 7, 20))

    with SessionFactory() as session:
        detail = session.scalar(select(ActivityPerformanceDetail))
    assert result.status == "partial"
    assert result.details_fetched == 0
    assert detail is not None
    assert len(detail.splits) == 2


def test_rate_limit_stops_remaining_candidates_after_preserving_prior_success():
    class RateLimitedAfterFirst(StubPerformanceSource):
        def get_activity_performance_detail(self, activity_id: str):
            if activity_id == "run-2":
                raise GarminRateLimitError("wait")
            return super().get_activity_performance_detail(activity_id)

    with session_scope() as session:
        session.add_all(
            [
                _activity("run-1", date(2026, 7, 20)),
                _activity("run-2", date(2026, 7, 21)),
            ]
        )

    result = PerformanceHistoryService(RateLimitedAfterFirst()).sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 21)
    )
    with SessionFactory() as session:
        details = session.scalars(select(ActivityPerformanceDetail)).all()

    assert result.status == "partial"
    assert result.stop_reason == "rate_limit"
    assert result.details_fetched == 1
    assert len(details) == 1


def test_detail_sync_rejects_more_than_seven_days_before_calling_source():
    source = StubPerformanceSource()

    with pytest.raises(ValueError, match="at most 7 days"):
        PerformanceHistoryService(source).sync_details(
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 8)
        )

    assert source.detail_requests == []


def test_race_evidence_requires_detail_and_an_explicit_same_day_same_sport_link():
    with session_scope() as session:
        session.add(_activity("race-run", date(2026, 7, 20)))
        race = Race(
            name="Synthetic 5k",
            sport_type="run",
            race_date=date(2026, 7, 20),
            distance_meters=5_000,
            priority="B",
        )
        session.add(race)
        session.flush()
        race_id = race.id
    PerformanceHistoryService(StubPerformanceSource()).sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 20)
    )

    evidence = PerformanceHistoryService().link_race_evidence(
        garmin_activity_id="race-run", race_id=race_id
    )
    history = PerformanceHistoryService().get_history(end_date=date(2026, 7, 26))

    assert evidence.evidence_type == "race"
    assert len(history.race_evidence) == 1
    assert history.race_evidence[0].race_name == "Synthetic 5k"
    assert history.race_evidence[0].distance_meters == 5_010
    assert history.race_evidence[0].scalar_source == "activity_detail"
    assert "performance_target_proposals_belong_to_j3" in history.limitations
    with SessionFactory() as session:
        assert session.scalar(select(PerformanceEvidence)) is not None


def test_race_link_rejects_a_different_activity_day():
    with session_scope() as session:
        session.add(_activity("run-1", date(2026, 7, 20)))
        race = Race(
            name="Wrong day",
            sport_type="run",
            race_date=date(2026, 7, 21),
            distance_meters=5_000,
            priority="B",
        )
        session.add(race)
        session.flush()
        race_id = race.id
    PerformanceHistoryService(StubPerformanceSource()).sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 20)
    )

    with pytest.raises(ValueError, match="date must match"):
        PerformanceHistoryService().link_race_evidence(
            garmin_activity_id="run-1", race_id=race_id
        )


def test_performance_history_falls_back_to_normalized_activity_scalars():
    with session_scope() as session:
        activity = _activity("run-summary-fallback", date(2026, 7, 20))
        activity.average_heart_rate = 145
        session.add(activity)
        session.flush()
        session.add(
            ActivityPerformanceDetail(
                activity_id=activity.id,
                splits=[{"split_number": 1, "duration_seconds": 1_800}],
            )
        )

    history = PerformanceHistoryService().get_history(end_date=date(2026, 7, 26))

    fact = history.detailed_activities[0]
    assert fact.duration_seconds == 1_800
    assert fact.distance_meters == 5_000
    assert fact.scalar_source == "activity_summary"


def test_approved_run_benchmark_requires_matching_garmin_distance_and_is_visible():
    with session_scope() as session:
        session.add(_activity("benchmark-run", date(2026, 7, 20)))
    PerformanceHistoryService(StubPerformanceSource()).sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 20)
    )

    evidence = PerformanceHistoryService().mark_benchmark_evidence(
        garmin_activity_id="benchmark-run",
        protocol_key="run_5k_time_trial",
    )
    history = PerformanceHistoryService().get_history(end_date=date(2026, 7, 26))

    assert evidence.evidence_type == "benchmark"
    assert len(history.benchmark_evidence) == 1
    assert history.benchmark_evidence[0].protocol == "run_5k_time_trial"


def test_benchmark_rejects_an_activity_that_does_not_match_its_protocol():
    with session_scope() as session:
        session.add(_activity("wrong-distance", date(2026, 7, 20)))
    PerformanceHistoryService(StubPerformanceSource()).sync_details(
        start_date=date(2026, 7, 20), end_date=date(2026, 7, 20)
    )

    with pytest.raises(ValueError, match="10 km"):
        PerformanceHistoryService().mark_benchmark_evidence(
            garmin_activity_id="wrong-distance",
            protocol_key="run_10k_time_trial",
        )


def test_readiness_requires_evidence_and_two_recent_same_sport_activities():
    with session_scope() as session:
        session.add_all(
            [
                SyncRun(
                    provider="garmin",
                    completed_at=datetime(2026, 7, 26, tzinfo=UTC),
                    status="success",
                    requested_start_date=date(2026, 6, 28),
                    requested_end_date=date(2026, 7, 4),
                ),
                SyncRun(
                    provider="garmin",
                    completed_at=datetime(2026, 7, 26, tzinfo=UTC),
                    status="success",
                    requested_start_date=date(2026, 7, 5),
                    requested_end_date=date(2026, 7, 11),
                ),
                SyncRun(
                    provider="garmin",
                    completed_at=datetime(2026, 7, 26, tzinfo=UTC),
                    status="success",
                    requested_start_date=date(2026, 7, 12),
                    requested_end_date=date(2026, 7, 18),
                ),
                SyncRun(
                    provider="garmin",
                    completed_at=datetime(2026, 7, 26, tzinfo=UTC),
                    status="success",
                    requested_start_date=date(2026, 7, 19),
                    requested_end_date=date(2026, 7, 25),
                ),
            ]
        )
        evidence_activity = _activity("run-evidence", date(2026, 7, 12))
        first_recent = _activity("run-recent-one", date(2026, 7, 20))
        second_recent = _activity("run-recent-two", date(2026, 7, 25))
        session.add_all((evidence_activity, first_recent, second_recent))
        session.flush()
        session.add_all(
            [
                ActivityPerformanceDetail(
                    activity_id=evidence_activity.id,
                    splits=[],
                ),
                PerformanceEvidence(
                    activity_id=evidence_activity.id,
                    evidence_type="benchmark",
                    benchmark_protocol="run_5k_time_trial",
                ),
            ]
        )

    readiness = PerformanceHistoryService().get_readiness(end_date=date(2026, 7, 26))
    run, ride = readiness.sports

    assert run.status == "ready_for_intensity_target"
    assert run.can_propose_intensity_target is True
    assert run.recent_activity_count == 2
    assert ride.status == "general_plan_only"
    assert "no_verified_evidence_in_last_12_weeks" in ride.limitations
