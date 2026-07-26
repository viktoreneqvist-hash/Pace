"""Pace database models.

Importing models here ensures Alembic sees every table in the shared metadata.
"""

from pace.database.models.activity import Activity
from pace.database.models.activity_performance_detail import ActivityPerformanceDetail
from pace.database.models.base import Base, TimestampMixin
from pace.database.models.context_event import ContextEvent
from pace.database.models.daily_metric import DailyMetric
from pace.database.models.heart_rate_zone_profile import HeartRateZoneProfile
from pace.database.models.race import Race
from pace.database.models.performance_evidence import PerformanceEvidence
from pace.database.models.performance_sync_run import PerformanceSyncRun
from pace.database.models.sync_run import SyncRun
from pace.database.models.training_plan import PlannedSession, SessionFeedback, TrainingPlan
from pace.database.models.training_preference import TrainingPreference

__all__ = [
    "Activity",
    "ActivityPerformanceDetail",
    "Base",
    "ContextEvent",
    "DailyMetric",
    "HeartRateZoneProfile",
    "PerformanceEvidence",
    "PerformanceSyncRun",
    "Race",
    "SyncRun",
    "PlannedSession",
    "SessionFeedback",
    "TimestampMixin",
    "TrainingPlan",
    "TrainingPreference",
]
