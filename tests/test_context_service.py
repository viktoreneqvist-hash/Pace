from datetime import date

import pytest

from pace.services.context_service import ContextEventInput, ContextService


def test_regular_context_note_is_closed_on_its_start_date():
    event = ContextService().add_event(
        ContextEventInput(
            event_type="poor_sleep",
            start_date=date(2026, 7, 25),
            note="Somnade sent.",
        )
    )

    assert event.event_type == "poor_sleep"
    assert event.start_date == date(2026, 7, 25)
    assert event.end_date == date(2026, 7, 25)
    assert event.status == "closed"
    assert event.affected_metrics == []


def test_ongoing_context_note_has_no_end_date_and_remains_active():
    event = ContextService().add_event(
        ContextEventInput(
            event_type="pain",
            start_date=date(2026, 7, 25),
            note="Känning i vänster vad.",
            ongoing=True,
        )
    )

    assert event.end_date is None
    assert event.status == "active"


def test_context_note_rejects_unsupported_type_and_invalid_date_combinations():
    service = ContextService()

    with pytest.raises(ValueError, match="Unsupported"):
        service.add_event(
            ContextEventInput(
                event_type="race",
                start_date=date(2026, 7, 25),
                note="Not in this first slice.",
            )
        )

    with pytest.raises(ValueError, match="ongoing"):
        service.add_event(
            ContextEventInput(
                event_type="illness",
                start_date=date(2026, 7, 25),
                end_date=date(2026, 7, 26),
                ongoing=True,
                note="Should be rejected.",
            )
        )

    with pytest.raises(ValueError, match="earlier"):
        service.add_event(
            ContextEventInput(
                event_type="travel",
                start_date=date(2026, 7, 25),
                end_date=date(2026, 7, 24),
                note="Invalid range.",
            )
        )


def test_context_list_returns_only_events_overlapping_the_requested_range():
    service = ContextService()
    service.add_event(
        ContextEventInput(
            event_type="travel",
            start_date=date(2026, 7, 20),
            end_date=date(2026, 7, 22),
            note="Trip.",
        )
    )
    service.add_event(
        ContextEventInput(
            event_type="work_stress",
            start_date=date(2026, 7, 25),
            note="Deadline.",
        )
    )
    service.add_event(
        ContextEventInput(
            event_type="pain",
            start_date=date(2026, 7, 26),
            note="Ongoing symptom.",
            ongoing=True,
        )
    )

    events = service.list_events(
        start_date=date(2026, 7, 22),
        end_date=date(2026, 7, 26),
    )

    assert [event.event_type for event in events] == [
        "travel",
        "work_stress",
        "pain",
    ]


def test_context_list_requires_a_complete_date_range_filter():
    with pytest.raises(ValueError, match="both --from and --to"):
        ContextService().list_events(start_date=date(2026, 7, 25))
