"""Application service for athlete-provided context memory."""

from dataclasses import dataclass
from datetime import date

from pace.database.models import ContextEvent
from pace.database.session import session_scope
from pace.repositories.context_event_repository import (
    create_context_event,
    get_all_context_events,
    get_context_events_in_date_range,
)


SUPPORTED_CONTEXT_EVENT_TYPES = frozenset(
    {
        "illness",
        "pain",
        "travel",
        "alcohol",
        "poor_sleep",
        "work_stress",
        "schedule_constraint",
    }
)


@dataclass(frozen=True, slots=True)
class ContextEventInput:
    """The explicit facts needed to create one athlete context event."""

    event_type: str
    start_date: date
    note: str
    end_date: date | None = None
    ongoing: bool = False


class ContextService:
    """Validate and persist context without interpreting its coaching meaning."""

    def add_event(self, event_input: ContextEventInput) -> ContextEvent:
        """Store a finite event or an explicitly ongoing event."""

        normalized_type = event_input.event_type.strip().lower()
        normalized_note = event_input.note.strip()

        if normalized_type not in SUPPORTED_CONTEXT_EVENT_TYPES:
            raise ValueError(f"Unsupported context event type: {normalized_type}.")
        if not normalized_note:
            raise ValueError("A context note cannot be empty.")
        if event_input.ongoing and event_input.end_date is not None:
            raise ValueError("An ongoing event cannot also have an end date.")
        if (
            event_input.end_date is not None
            and event_input.end_date < event_input.start_date
        ):
            raise ValueError("The end date cannot be earlier than the start date.")

        end_date = (
            None
            if event_input.ongoing
            else event_input.end_date or event_input.start_date
        )
        status = "active" if event_input.ongoing else "closed"

        context_event = ContextEvent(
            event_type=normalized_type,
            start_date=event_input.start_date,
            end_date=end_date,
            note=normalized_note,
            affected_metrics=[],
            status=status,
        )

        with session_scope() as session:
            saved_event = create_context_event(session, context_event)
            return saved_event

    def list_events(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ContextEvent]:
        """List all events or only events overlapping one explicit date range."""

        if (start_date is None) != (end_date is None):
            raise ValueError("Use both --from and --to when filtering context events.")

        with session_scope() as session:
            if start_date is None or end_date is None:
                return get_all_context_events(session)
            return get_context_events_in_date_range(
                session,
                start_date=start_date,
                end_date=end_date,
            )
