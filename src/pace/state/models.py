"""Compact, deterministic representations of Pace's current athlete state."""

from dataclasses import dataclass
from datetime import date, datetime

from pace.analysis.models import PaceMetricSummary


@dataclass(frozen=True, slots=True)
class ContextEventState:
    """One explicitly selected local context event for an athlete snapshot."""

    id: int
    event_type: str
    start_date: date
    end_date: date | None
    note: str
    status: str


@dataclass(frozen=True, slots=True)
class HrvObservation:
    """One normalized HRV observation retained for deterministic rules."""

    date: date
    value: float


@dataclass(frozen=True, slots=True)
class AthleteContextWindow:
    """The current training window and its relevant athlete-provided context."""

    start_date: date
    end_date: date
    events: tuple[ContextEventState, ...]


@dataclass(frozen=True, slots=True)
class SyncDataQuality:
    """Audit facts about the latest completed Garmin synchronization."""

    provider: str
    completed_at: datetime
    status: str
    requested_start_date: date | None
    requested_end_date: date | None


@dataclass(frozen=True, slots=True)
class RecoveryDataQuality:
    """Completeness facts for one recovery metric, without an interpretation."""

    metric: str
    baseline_data_points: int
    expected_baseline_days: int
    recent_data_points: int
    latest_date: date | None


@dataclass(frozen=True, slots=True)
class AthleteStateDataQuality:
    """Source freshness and completeness facts for an athlete snapshot."""

    latest_completed_sync: SyncDataQuality | None
    recovery: tuple[RecoveryDataQuality, ...]


@dataclass(frozen=True, slots=True)
class AthleteState:
    """Current Pace facts, relevant context, and explicit source quality."""

    as_of_date: date
    metrics: PaceMetricSummary
    relevant_context: AthleteContextWindow
    data_quality: AthleteStateDataQuality
    recent_hrv_observations: tuple[HrvObservation, ...]
