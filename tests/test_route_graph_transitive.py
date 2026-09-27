"""Projection des fermetures existantes sans redécouverte ni diagnostic."""

import ast
import builtins
import os
from dataclasses import replace
from pathlib import Path

import pytest
from jinja2 import Environment

from forge_design.forge import routes as bridge
from forge_design.forge import template_cycles
from forge_design.forge.routes import (
    HandlerInfo,
    RouteInfo,
    RoutesResult,
    TemplateDependency,
    TemplateDependencyGraph,
    TemplateNodeInfo,
    TemplateResolution,
)
from forge_design.forge.template_cycles import TemplateCycle, TemplateCycleEdge
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.route_graph import build_route_graph
from forge_design.web.route_graph_layout import layout_route_graph


def route(root: str, closure: TemplateDependencyGraph) -> RouteInfo:
    dependencies = next(n.dependencies for n in closure.templates if n.path == root)
    return RouteInfo(
        "GET",
        "/" + root,
        None,
        True,
        HandlerInfo(
            "C." + root,
            "mvc/controllers/c.py",
            template=TemplateResolution(
                "found",
                root,
                "present",
                dependencies=dependencies,
                dependency_graph=closure,
            ),
        ),
    )


def node(path: str, *targets: str) -> TemplateNodeInfo:
    return TemplateNodeInfo(
        path,
        "present",
        "valid",
        tuple(
            TemplateDependency("include", target, False, i + 1, "present", "valid")
            for i, target in enumerate(targets)
        ),
    )


@pytest.mark.parametrize("depth", [1, 2, 3, 5])
def test_depth_and_compatibility(depth: int) -> None:
    templates = tuple(node(str(i), str(i + 1)) for i in range(depth)) + (
        node(str(depth)),
    )
    closure = TemplateDependencyGraph("0", templates)
    source = route("0", closure)
    graph = build_route_graph(RoutesResult((source,), ()))
    assert [n.label for n in graph.nodes if n.kind == "template"] == [
        str(i) for i in range(depth + 1)
    ]
    assert sum(e.kind == "includes" for e in graph.edges) == depth
    assert source.handler
    direct = replace(
        source,
        handler=replace(
            source.handler,
            template=replace(
                source.handler.template,
                dependency_graph=None,
            ),
        ),
    )
    old = build_route_graph(RoutesResult((direct,), ()))
    assert graph.nodes[: len(old.nodes)] == old.nodes
    assert graph.edges[: len(old.edges)] == old.edges
    layout = layout_route_graph(graph)
    assert [n.x for n in layout.nodes if n.node.kind == "template"] == [
        30 + 360 * (3 + i) for i in range(depth + 1)
    ]
    assert layout.width == 30 + 360 * (3 + depth) + 260 + 30
    assert layout == layout_route_graph(graph)


def test_shared_roots_cycles_and_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    templates = (node("a", "b", "c"), node("b", "c"), node("c", "a"))
    long_cycle = TemplateCycle(
        (
            TemplateCycleEdge("a", "b", "include", 1),
            TemplateCycleEdge("b", "c", "include", 1),
            TemplateCycleEdge("c", "a", "include", 1),
        )
    )
    short_cycle = TemplateCycle(
        (
            TemplateCycleEdge("a", "c", "include", 2),
            TemplateCycleEdge("c", "a", "include", 1),
        )
    )
    closure = TemplateDependencyGraph("a", templates, cycles=(long_cycle, short_cycle))
    result = RoutesResult(
        (route("a", closure), route("b", replace(closure, root="b"))), ()
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Aucune analyse supplémentaire")

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "lstat")),
            (Path, ("open", "stat", "lstat", "iterdir")),
            (ast, ("parse",)),
            (Environment, ("parse",)),
            (bridge, ("read_routes", "detect_template_cycles")),
            (template_cycles, ("detect_template_cycles",)),
            (ToolRegistry, ("get", "list")),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        graph = build_route_graph(result)
        assert graph == build_route_graph(result)
        layout = layout_route_graph(graph)
    assert len([n for n in graph.nodes if n.kind == "template"]) == 3
    assert sum(e.in_cycle for e in graph.edges) == 4
    assert all(not e.in_cycle for e in graph.edges if e.kind != "includes")
    assert len({(e.source, e.target, e.kind) for e in graph.edges}) == len(graph.edges)
    positioned = {n.node.label: n for n in layout.nodes if n.node.kind == "template"}
    assert positioned["a"].x == positioned["b"].x == 1110
    assert positioned["c"].x == 1470
    assert positioned["a"].y != positioned["b"].y
    assert any(e.edge.in_cycle and "H 1090" in e.path for e in layout.edges)
    for i, first in enumerate(layout.nodes):
        for second in layout.nodes[i + 1 :]:
            assert (
                first.x + first.width <= second.x
                or second.x + second.width <= first.x
                or first.y + first.height <= second.y
                or second.y + second.height <= first.y
            )


def test_terminal_and_unchecked_targets() -> None:
    dependencies = (
        TemplateDependency("extends", "missing", False, 1, "missing"),
        TemplateDependency("include", "../refused", False, 2, "invalid-path"),
        TemplateDependency("import", "unchecked", False, 3),
        TemplateDependency("from-import", None, True, 4),
    )
    closure = TemplateDependencyGraph(
        "a",
        (node("a", "b"), TemplateNodeInfo("b", "present", "valid", dependencies)),
        True,
    )
    graph = build_route_graph(RoutesResult((route("a", closure),), ()))
    assert graph.transitive_truncated
    assert [(n.label, n.presence) for n in graph.nodes if n.kind == "template"] == [
        ("a", "present"),
        ("b", "present"),
        ("missing", "missing"),
        ("../refused", "invalid-path"),
        ("unchecked", "not-applicable"),
    ]
    assert [e.kind for e in graph.edges][-3:] == ["extends", "includes", "imports"]


def test_auto_cycle_and_no_implicit_detection() -> None:
    closure = TemplateDependencyGraph("a", (node("a", "a"),))
    result = RoutesResult((route("a", closure),), ())
    assert not any(e.in_cycle for e in build_route_graph(result).edges)
    closure = replace(
        closure, cycles=(TemplateCycle((TemplateCycleEdge("a", "a", "include", 1),)),)
    )
    graph = build_route_graph(RoutesResult((route("a", closure),), ()))
    layout = layout_route_graph(graph)
    assert sum(e.in_cycle for e in graph.edges) == 1
    assert len([n for n in layout.nodes if n.node.kind == "template"]) == 1
    assert layout == layout_route_graph(graph)
