"""Cycles témoins déterministes sur données exclusivement en mémoire."""

import ast
import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from jinja2 import Environment

from forge_design.forge import routes as bridge
from forge_design.forge.routes import (
    TemplateDependency,
    TemplateDependencyGraph,
    TemplateNodeInfo,
)
from forge_design.forge.template_cycles import detect_template_cycles
from forge_design.platform.tool_registry import ToolRegistry


def graph_of(links: dict[str, tuple[str, ...]], truncated: bool = False):
    return TemplateDependencyGraph(
        next(iter(links), ""),
        tuple(
            TemplateNodeInfo(
                path,
                "present",
                "valid",
                tuple(
                    TemplateDependency("include", target, False, i + 1)
                    for i, target in enumerate(targets)
                ),
            )
            for path, targets in links.items()
        ),
        truncated,
    )


@pytest.mark.parametrize(
    "links,expected",
    [
        ({}, ()),
        ({"a": ("b",), "b": ()}, ()),
        ({"a": ("a",)}, (("a", "a"),)),
        ({"a": ("b",), "b": ("a",)}, (("a", "b", "a"),)),
        ({"a": ("b",), "b": ("c",), "c": ("a",)}, (("a", "b", "c", "a"),)),
        (
            {"a": ("b",), "b": ("a",), "c": ("d",), "d": ("e",), "e": ("c",)},
            (("a", "b", "a"), ("c", "d", "e", "c")),
        ),
        (
            {"a": ("b", "c"), "b": ("a",), "c": ("a",)},
            (("a", "b", "a"), ("a", "c", "a")),
        ),
        ({"c": ("a",), "a": ("b",), "b": ("c",)}, (("a", "b", "c", "a"),)),
        ({"a": ("c",), "c": ("b",), "b": ("a",)}, (("a", "c", "b", "a"),)),
        ({"a": ("b", "b"), "b": ("a", "a")}, (("a", "b", "a"),)),
    ],
)
def test_cycles(
    links: dict[str, tuple[str, ...]], expected: tuple[tuple[str, ...], ...]
):
    graph = graph_of(links)
    result = detect_template_cycles(graph)
    assert tuple(c.paths for c in result) == expected
    assert detect_template_cycles(graph) == result
    assert graph.cycles == ()
    if result:
        with pytest.raises(FrozenInstanceError):
            setattr(result[0], "edges", ())


@pytest.mark.parametrize("truncated", [False, True])
def test_types_lines_dynamic_and_terminals(truncated: bool) -> None:
    graph = TemplateDependencyGraph(
        "a",
        (
            TemplateNodeInfo(
                "a",
                "present",
                "valid",
                (
                    TemplateDependency("extends", "b", False, 12),
                    TemplateDependency("include", "a", True, 2),
                    TemplateDependency("include", None, True, 3),
                    TemplateDependency("include", "missing", False, 4),
                    TemplateDependency("include", "outside", False, 5),
                ),
            ),
            TemplateNodeInfo(
                "b", "present", "valid", (TemplateDependency("import", "c", False, 7),)
            ),
            TemplateNodeInfo(
                "c",
                "present",
                "valid",
                (TemplateDependency("from-import", "a", False, 9),),
            ),
            TemplateNodeInfo("missing", "missing", "not-applicable", ()),
        ),
        truncated,
    )
    (cycle,) = detect_template_cycles(graph)
    assert cycle.paths == ("a", "b", "c", "a")
    assert [e.kind for e in cycle.edges] == ["extends", "import", "from-import"]
    assert [e.line for e in cycle.edges] == [12, 7, 9]
    assert not detect_template_cycles(graph_of({"a": ("outside",)}, truncated))


def test_isolation_and_iterative_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = graph_of({str(i): (str(i + 1),) for i in range(1500)})

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("I/O, parser ou appel métier interdit")

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "lstat")),
            (Path, ("open", "stat", "lstat", "iterdir")),
            (ast, ("parse",)),
            (Environment, ("parse",)),
            (bridge, ("read_routes",)),
            (ToolRegistry, ("get", "list")),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        assert detect_template_cycles(graph) == ()
        assert detect_template_cycles(graph_of({"a": ("a",)}))[0].paths == ("a", "a")
