"""Sélection exacte, immuable et sans I/O."""

import builtins
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from test_debug_filters import sample

from forge_design.forge import debug_errors
from forge_design.forge.debug_errors import DebugErrorsResult
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_detail import find_debug_event


@pytest.mark.parametrize(
    "line,event_id,index",
    [
        (1, "same", 0),
        (2, "same", 1),
        (3, "last", 2),
        (1, "last", None),
        (3, "same", None),
        (4, "same", None),
        (1, "wrong", None),
    ],
)
def test_selection(
    line: int, event_id: str, index: int | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = tuple(
        replace(sample(), line_number=i, id=event_id)
        for i, event_id in enumerate(("same", "same", "last"), 1)
    )
    result = DebugErrorsResult(events)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Selection must be pure")

    with monkeypatch.context() as patch:
        for owner, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "listdir", "scandir")),
            (Path, ("open", "read_text", "read_bytes", "stat", "iterdir")),
            (json, ("loads", "load")),
            (ToolRegistry, ("get",)),
            (debug_errors, ("read_debug_errors",)),
        ):
            for name in names:
                patch.setattr(owner, name, forbidden)
        selected = find_debug_event(result, line_number=line, event_id=event_id)
        assert selected is (None if index is None else events[index])
        assert selected is find_debug_event(result, line_number=line, event_id=event_id)
        assert (
            find_debug_event(DebugErrorsResult(), line_number=line, event_id=event_id)
            is None
        )
    assert result.events is events
    assert [e.line_number for e in events] == [1, 2, 3]
