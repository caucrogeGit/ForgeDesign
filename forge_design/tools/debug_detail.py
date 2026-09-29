"""Sélection pure d’une occurrence dans la lecture courante du journal."""

from forge_design.forge.debug_errors import DebugError, DebugErrorsResult


def find_debug_event(
    result: DebugErrorsResult, *, line_number: int, event_id: str
) -> DebugError | None:
    return next(
        (
            event
            for event in result.events
            if event.line_number == line_number and event.id == event_id
        ),
        None,
    )
