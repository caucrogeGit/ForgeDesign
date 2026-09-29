"""Projection des seules étapes explicitement renseignées."""

import builtins
import json
import os
from dataclasses import FrozenInstanceError, replace
from itertools import combinations
from pathlib import Path

import pytest
from test_debug_filters import sample

from forge_design.forge import debug_errors
from forge_design.forge.debug_errors import DebugFrame, DebugRequest
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_flow import build_debug_flow

FIELDS = ("request", "route", "controller", "sql", "template")
CASES = [parts for count in range(6) for parts in combinations(FIELDS, count)]


@pytest.mark.parametrize("fields", CASES)
def test_subsets(fields: tuple[str, ...]) -> None:
    values: dict[str, object] = {field: field + "-value" for field in fields}
    if "request" in fields:
        values["request"] = DebugRequest(
            method="POST", path="/users", query="not-in-flow"
        )
    event = replace(sample(), **values)
    flow = build_debug_flow(event)
    expected = ["router" if f == "route" else f for f in fields]
    assert [n.kind for n in flow.nodes] == expected
    assert [n.id for n in flow.nodes] == ["debug-node-" + kind for kind in expected]
    assert [(e.source, e.target) for e in flow.edges] == [
        (a.id, b.id) for a, b in zip(flow.nodes, flow.nodes[1:])
    ]
    assert "model" not in expected and "response" not in expected
    assert "not-in-flow" not in repr(flow) and "sql-value" not in repr(flow)
    assert build_debug_flow(event) == flow
    if "request" in fields:
        assert flow.nodes[0].detail == "POST /users"
    for item in (flow, *flow.nodes, *flow.edges):
        with pytest.raises(FrozenInstanceError):
            setattr(item, next(iter(item.__dataclass_fields__)), None)


@pytest.mark.parametrize(
    "req,detail",
    [
        (DebugRequest(), None),
        (DebugRequest(method="POST"), "POST"),
        (DebugRequest(path="/users"), "/users"),
    ],
)
def test_partial_request(req: DebugRequest, detail: str | None) -> None:
    flow = build_debug_flow(replace(sample(), request=req))
    assert len(flow.nodes) == 1 and flow.nodes[0].detail == detail


@pytest.mark.parametrize("category", ["database", "template"])
def test_no_inference(category: str) -> None:
    event = replace(
        sample(),
        category=category,
        exception_type="TemplateNotFound",
        message="Model SQL response",
        hint="template hint",
        traceback=(DebugFrame("mvc/models/user.py", 2, "save"),),
    )
    assert not build_debug_flow(event).nodes
    assert not build_debug_flow(
        replace(event, route="", controller="", sql="", template="")
    ).nodes


def test_purity_and_full_details(monkeypatch: pytest.MonkeyPatch) -> None:
    event = replace(sample(), controller="long-controller" * 100)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No I/O in projection")

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
        flow = build_debug_flow(event)
    assert flow.nodes[0].detail == event.controller
