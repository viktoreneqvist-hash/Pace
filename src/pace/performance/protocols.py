"""Owner-approved, deterministic benchmark eligibility rules."""

from dataclasses import dataclass

from pace.database.models import ActivityPerformanceDetail


@dataclass(frozen=True, slots=True)
class BenchmarkProtocol:
    """The minimum observable facts required for one explicitly marked test."""

    key: str
    sport_type: str
    label: str
    minimum_distance_meters: float | None = None
    maximum_distance_meters: float | None = None
    minimum_power_split_seconds: int | None = None
    maximum_power_split_seconds: int | None = None


BENCHMARK_PROTOCOLS = {
    "run_5k_time_trial": BenchmarkProtocol(
        key="run_5k_time_trial",
        sport_type="run",
        label="5 km time trial",
        minimum_distance_meters=4_750,
        maximum_distance_meters=5_250,
    ),
    "run_10k_time_trial": BenchmarkProtocol(
        key="run_10k_time_trial",
        sport_type="run",
        label="10 km time trial",
        minimum_distance_meters=9_500,
        maximum_distance_meters=10_500,
    ),
    "ride_20min_power_test": BenchmarkProtocol(
        key="ride_20min_power_test",
        sport_type="ride",
        label="20-minute power test",
        minimum_power_split_seconds=1_140,
        maximum_power_split_seconds=1_260,
    ),
}
SUPPORTED_BENCHMARK_PROTOCOLS = frozenset(BENCHMARK_PROTOCOLS)


def validate_benchmark_activity(
    *,
    protocol: BenchmarkProtocol,
    sport_type: str,
    distance_meters: float | None,
    detail: ActivityPerformanceDetail,
) -> None:
    """Reject a marked activity that does not meet the approved test contract."""

    if sport_type != protocol.sport_type:
        raise ValueError(
            f"{protocol.label} requires a normalized {protocol.sport_type} activity."
        )
    if protocol.minimum_distance_meters is not None:
        if distance_meters is None:
            raise ValueError(f"{protocol.label} requires a known activity distance.")
        if not protocol.minimum_distance_meters <= distance_meters <= protocol.maximum_distance_meters:
            raise ValueError(
                f"{protocol.label} requires {protocol.minimum_distance_meters / 1000:g}–"
                f"{protocol.maximum_distance_meters / 1000:g} km according to Garmin."
            )
    if protocol.minimum_power_split_seconds is not None:
        has_power_segment = any(
            split.get("duration_seconds") is not None
            and protocol.minimum_power_split_seconds
            <= split["duration_seconds"]
            <= protocol.maximum_power_split_seconds
            and split.get("average_power") is not None
            for split in detail.splits
        )
        if not has_power_segment:
            raise ValueError(
                f"{protocol.label} requires one 19–21 minute Garmin split with power."
            )
