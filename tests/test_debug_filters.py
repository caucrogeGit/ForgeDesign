"""Filtrage pur et tri stable des événements déjà masqués."""

import builtins
import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from forge_design.forge import debug_errors
from forge_design.forge.debug_errors import (
    DebugError,
    DebugErrorsResult,
    DebugFrame,
    DebugIssue,
    DebugRequest,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_filters import (
    CATEGORIES,
    LEVELS,
    DebugFilter,
    filter_debug_events,
)


def sample() -> DebugError:
    return DebugError(
        "1.0",
        "id",
        "2026-09-29T10:00:00+00:00",
        "dev",
        "ERROR",
        "runtime",
        "RuntimeError",
        "message",
        False,
        1,
    )


@pytest.mark.parametrize(
    "query,expected",
    [(None, None), ("", None), ("  ", None), (" AbC ", "abc"), (" STRAßE ", "strasse")],
)
def test_normalization(query: str | None, expected: str | None) -> None:
    filters = DebugFilter(query=query)
    assert filters.query == expected
    assert (filters.level, filters.category, filters.order) == ("all", "all", "newest")


@pytest.mark.parametrize("query", ["x" * 257, "ß" * 129])
def test_query_limits(query: str) -> None:
    with pytest.raises(ValueError):
        DebugFilter(query=query)
    assert len(DebugFilter(query="ß" * 128).query or "") == 256


@pytest.mark.parametrize(
    "field,value",
    [
        ("level", "error"),
        ("level", "FATAL"),
        ("category", "security"),
        ("order", "random"),
    ],
)
def test_invalid(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        DebugFilter(**{field: value})


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize("category", CATEGORIES)
def test_exact_filters(level: str, category: str) -> None:
    events = tuple(
        replace(sample(), level=level_value, category=category_value)
        for level_value in LEVELS[1:]
        for category_value in CATEGORIES[1:]
    )
    result = DebugErrorsResult(events)
    view = filter_debug_events(result, DebugFilter(level=level, category=category))
    expected = tuple(
        e
        for e in events
        if (level == "all" or e.level == level)
        and (category == "all" or e.category == category)
    )
    assert view.events == expected and view.total_events == 32


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "exception_type",
        "message",
        "route",
        "controller",
        "template",
        "hint",
        "correlation_id",
        "request.method",
        "request.path",
    ],
)
def test_search_fields(field: str) -> None:
    if field.startswith("request."):
        event = replace(
            sample(),
            request=(
                DebugRequest(method="Straße")
                if field == "request.method"
                else DebugRequest(path="Straße")
            ),
        )
    else:
        event = replace(sample(), **{field: "Straße"})
    result = DebugErrorsResult((event,))
    assert filter_debug_events(result, DebugFilter(query=" STRASSE ")).events == (
        event,
    )
    assert not filter_debug_events(
        result, DebugFilter(query="strasse", level="INFO")
    ).events


def test_excluded_fields() -> None:
    event = replace(
        sample(),
        sql="sql-only",
        request=DebugRequest(query="query-only"),
        traceback=(DebugFrame("frame-only", 1, "function-only"),),
    )
    for term in (
        "sql-only",
        "query-only",
        "frame-only",
        "function-only",
        "ERROR",
        "runtime",
    ):
        # exception_type is deliberately independent of the level/category.
        result = DebugErrorsResult((replace(event, exception_type="Exception"),))
        assert not filter_debug_events(result, DebugFilter(query=term)).events


@pytest.mark.parametrize(
    "order,expected",
    [("newest", [5, 1, 3, 7, 2, 4, 6]), ("oldest", [7, 1, 3, 5, 2, 4, 6])],
)
def test_temporal_sort(order: str, expected: list[int]) -> None:
    timestamps = [
        "2026-09-29T10:00:00+00:00",
        "not-a-date",
        "2026-09-29T12:00:00+02:00",
        "2026-09-29T10:00:00",
        "2026-09-30T10:00:00Z",
        "",
        "2026-09-28T10:00:00-02:00",
    ]
    events = tuple(
        replace(sample(), timestamp=t, line_number=i)
        for i, t in enumerate(timestamps, 1)
    )
    result = DebugErrorsResult(events)
    view = filter_debug_events(result, DebugFilter(order=order))
    assert [e.line_number for e in view.events] == expected
    assert result.events is events
    assert filter_debug_events(result, DebugFilter(order=order)) == view
    # Sorting an already sorted result keeps the same stable order.
    assert (
        filter_debug_events(
            replace(result, events=view.events), DebugFilter(order=order)
        ).events
        == view.events
    )


def test_purity_immutability_and_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    result = DebugErrorsResult((sample(),), (DebugIssue("debug.json_invalid", "JSON"),))
    filters = DebugFilter(query="missing")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("I/O forbidden during projection")

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
        view = filter_debug_events(result, filters)
        assert view == filter_debug_events(result, filters)
    assert not view.events and view.total_events == 1 and view.issues is result.issues
    with pytest.raises(FrozenInstanceError):
        setattr(filters, "query", "x")
    with pytest.raises(FrozenInstanceError):
        setattr(view, "events", ())
    assert result.events == (sample(),)
    assert not filter_debug_events(DebugErrorsResult(), DebugFilter()).events
