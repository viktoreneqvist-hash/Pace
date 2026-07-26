"""Read-only composition of metrics, context, and source-quality facts."""

from datetime import date

from pace.database.session import session_scope
from pace.repositories.context_event_repository import get_context_events_in_date_range
from pace.repositories.daily_metric_repository import (
    get_daily_metrics_in_date_range,
    get_latest_daily_metric_with_value,
)
from pace.repositories.sync_run_repository import get_latest_completed_sync_run
from pace.state.models import (
    AthleteContextWindow,
    AthleteState,
    AthleteStateDataQuality,
    ContextEventState,
    GarminCurrentFact,
    RecoveryDayObservation,
    RecoveryDataQuality,
    SyncDataQuality,
)
from pace.timezones import as_utc
from pace.services.metric_service import MetricService


class AthleteStateService:
    """Build a dynamic athlete snapshot without coaching interpretation."""

    def get_state(self, *, end_date: date) -> AthleteState:
        """Return facts and context relevant to the current seven-day window."""

        metrics = MetricService().get_summary(end_date=end_date)
        current_window = metrics.training.current

        with session_scope() as session:
            context_events = get_context_events_in_date_range(
                session,
                start_date=current_window.start_date,
                end_date=current_window.end_date,
            )
            latest_sync = get_latest_completed_sync_run(session)
            daily_metrics = get_daily_metrics_in_date_range(
                session,
                start_date=current_window.start_date,
                end_date=current_window.end_date,
            )
            latest_garmin_metrics = {
                field_name: get_latest_daily_metric_with_value(
                    session,
                    field_name=field_name,
                    end_date=end_date,
                )
                for field_name in _GARMIN_STATUS_FIELDS
            }

        context = AthleteContextWindow(
            start_date=current_window.start_date,
            end_date=current_window.end_date,
            events=tuple(
                ContextEventState(
                    id=event.id,
                    event_type=event.event_type,
                    start_date=event.start_date,
                    end_date=event.end_date,
                    note=event.note,
                    status=event.status,
                )
                for event in context_events
            ),
        )
        data_quality = AthleteStateDataQuality(
            latest_completed_sync=(
                None
                if latest_sync is None or latest_sync.completed_at is None
                else SyncDataQuality(
                    provider=latest_sync.provider,
                    completed_at=as_utc(latest_sync.completed_at),
                    status=latest_sync.status,
                    requested_start_date=latest_sync.requested_start_date,
                    requested_end_date=latest_sync.requested_end_date,
                )
            ),
            recovery=tuple(
                RecoveryDataQuality(
                    metric=metric.metric,
                    baseline_data_points=metric.baseline_data_points,
                    expected_baseline_days=metric.expected_baseline_days,
                    recent_data_points=metric.recent_data_points,
                    latest_date=metric.latest_date,
                )
                for metric in metrics.recovery
            ),
        )

        return AthleteState(
            as_of_date=end_date,
            metrics=metrics,
            relevant_context=context,
            data_quality=data_quality,
            recent_recovery_observations=tuple(
                RecoveryDayObservation(
                    date=metric.date,
                    hrv_value=metric.hrv_value,
                    resting_heart_rate=(
                        None
                        if metric.resting_heart_rate is None
                        else float(metric.resting_heart_rate)
                    ),
                    sleep_duration_hours=(
                        None
                        if metric.sleep_duration_seconds is None
                        else metric.sleep_duration_seconds / 3600
                    ),
                )
                for metric in daily_metrics
            ),
            garmin_current_facts=_garmin_current_facts(
                latest_garmin_metrics=latest_garmin_metrics,
                end_date=end_date,
            ),
        )


_GARMIN_STATUS_FIELDS = (
    "training_readiness",
    "body_battery_high",
    "body_battery_low",
    "average_stress",
    "recovery_time_hours",
)


def _garmin_current_facts(
    *,
    latest_garmin_metrics,
    end_date: date,
) -> tuple[GarminCurrentFact, ...]:
    """Return the latest local Garmin-owned values without interpreting them."""

    facts: list[GarminCurrentFact] = []
    for field_name in _GARMIN_STATUS_FIELDS:
        latest_metric = latest_garmin_metrics[field_name]
        facts.append(
            GarminCurrentFact(
                signal=field_name,
                value=(
                    None
                    if latest_metric is None
                    else float(getattr(latest_metric, field_name))
                ),
                source_date=None if latest_metric is None else latest_metric.date,
                is_current=(
                    latest_metric is not None and latest_metric.date == end_date
                ),
            )
        )
    return tuple(facts)
