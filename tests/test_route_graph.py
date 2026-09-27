"""Le graphe représente les résultats sans consulter leur projet d'origine."""

import ast
import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from jinja2 import Environment

from forge_design.forge import routes as bridge
from forge_design.forge.routes import (
    HandlerInfo,
    RouteInfo,
    RoutesResult,
    TemplateDependency,
    TemplateResolution,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.route_graph import RouteGraph, build_route_graph


def test_empty_and_route_only() -> None:
    assert build_route_graph(RoutesResult((), ())) == RouteGraph((), ())
    graph = build_route_graph(RoutesResult((RouteInfo("GET", "/", None, True),), ()))
    assert [(n.kind, n.label) for n in graph.nodes] == [("route", "GET /")]
    assert graph.edges == ()
    with pytest.raises(FrozenInstanceError):
        setattr(graph.nodes[0], "label", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(graph, "nodes", ())


@pytest.mark.parametrize("controller", [None, "mvc/controllers/contact.py"])
@pytest.mark.parametrize(
    "template",
    [TemplateResolution(), TemplateResolution("found", "contact.html", "missing")],
)
def test_enrichment(controller: str | None, template: TemplateResolution) -> None:
    handler = HandlerInfo("Contact.list", controller, template=template)
    graph = build_route_graph(
        RoutesResult((RouteInfo("GET", "/", None, True, handler),), ())
    )
    expected = ["handles"]
    if controller:
        expected.append("defined-in")
    if template.status == "found":
        expected.append("renders")
        assert graph.nodes[-1].presence == "missing"
    assert [e.kind for e in graph.edges] == expected
    with pytest.raises(FrozenInstanceError):
        setattr(graph.edges[0], "kind", "renders")


def test_shared_nodes_edges_order_and_deterministic_ids() -> None:
    dependencies = (
        TemplateDependency("extends", "base.html", False, 1, "missing"),
        TemplateDependency("include", "base.html", False, 2),
        TemplateDependency("import", "macros.html", False, 3),
        TemplateDependency("from-import", "macros.html", False, 4),
        TemplateDependency("extends", "base.html", False, 5),
        TemplateDependency("include", None, True, 6),
    )
    template = TemplateResolution("found", "page.html", dependencies=dependencies)
    first = HandlerInfo("Contact.list", "mvc/controllers/contact.py", template=template)
    second = HandlerInfo("Contact.post", first.controller_file, template=template)
    route = RouteInfo("GET", "/contact", None, True, first)
    result = RoutesResult(
        (
            route,
            RouteInfo("POST", "/contact", None, True, first),
            RouteInfo("GET", "/second", None, True, second),
            route,
        ),
        (),
    )
    graph = build_route_graph(result)
    assert graph == build_route_graph(result)
    assert [(n.kind, n.label) for n in graph.nodes] == [
        ("route", "GET /contact"),
        ("handler", "Contact.list"),
        ("controller", "mvc/controllers/contact.py"),
        ("template", "page.html"),
        ("template", "base.html"),
        ("template", "macros.html"),
        ("route", "POST /contact"),
        ("route", "GET /second"),
        ("handler", "Contact.post"),
    ]
    assert [e.kind for e in graph.edges] == [
        "handles",
        "defined-in",
        "renders",
        "extends",
        "includes",
        "imports",
        "from-imports",
        "handles",
        "handles",
        "defined-in",
        "renders",
    ]
    assert len({n.id for n in graph.nodes}) == len(graph.nodes)
    assert len(set(graph.edges)) == len(graph.edges)
    assert graph.nodes[0].id == '["route","GET","/contact"]'
    assert all(
        e.source in {n.id for n in graph.nodes}
        and e.target in {n.id for n in graph.nodes}
        for e in graph.edges
    )
    assert result.routes == (route, result.routes[1], result.routes[2], route)


def test_builder_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    result = RoutesResult(
        (
            RouteInfo(
                "GET",
                "/",
                None,
                True,
                HandlerInfo(
                    "C.index",
                    "mvc/controllers/c.py",
                    template=TemplateResolution(
                        "found",
                        "a.html",
                        "present",
                        dependencies=(
                            TemplateDependency(
                                "include", "b.html", False, 1, "present"
                            ),
                        ),
                    ),
                ),
            ),
        ),
        (),
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Le builder ne doit pas consulter le projet.")

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "lstat")),
            (Path, ("open", "stat", "lstat", "iterdir")),
            (ast, ("parse",)),
            (Environment, ("parse",)),
            (ToolRegistry, ("get", "list")),
            (bridge, ("read_routes",)),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        graph = build_route_graph(result)
    assert len(graph.nodes) == 5
    assert len(graph.edges) == 4
