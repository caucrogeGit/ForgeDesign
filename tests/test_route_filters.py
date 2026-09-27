"""Sélection pure, associations exactes et cohérence du graphe filtré."""

import ast
import builtins
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import cast

import pytest
from jinja2 import Environment

from forge_design.forge import routes as bridge
from forge_design.forge.routes import (
    HandlerInfo,
    RouteInfo,
    RoutesResult,
    TemplateDependency,
    TemplateDependencyGraph,
    TemplateNodeInfo,
    TemplateResolution,
)
from forge_design.forge.source import SourceLocation
from forge_design.forge.template_cycles import TemplateCycle, TemplateCycleEdge
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools import route_diagnostics
from forge_design.tools.route_diagnostics import build_route_diagnostics
from forge_design.tools.route_filters import (
    RouteFilter,
    SeverityFilter,
    Visibility,
    filter_route_explorer,
)
from forge_design.tools.route_graph import build_route_graph
from forge_design.web.route_graph_layout import layout_route_graph


@pytest.fixture
def inventory() -> RoutesResult:
    missing = TemplateDependency(
        "include",
        "missing.html",
        False,
        2,
        "missing",
        source=SourceLocation("mvc/views/base.html", 2),
    )
    base = TemplateDependency("extends", "base.html", False, 1, "present", "valid")
    closure = TemplateDependencyGraph(
        "shared.html",
        (
            TemplateNodeInfo("shared.html", "present", "valid", (base,)),
            TemplateNodeInfo("base.html", "present", "valid", (missing,)),
            TemplateNodeInfo("missing.html", "missing", "not-applicable", ()),
        ),
    )
    shared = TemplateResolution(
        "found",
        "shared.html",
        "present",
        "valid",
        dependencies=(base,),
        dependency_graph=closure,
    )
    handler = HandlerInfo("Contact.list", "mvc/controllers/contact.py", "found", shared)
    cycle = TemplateCycle(
        (TemplateCycleEdge("health.html", "health.html", "include", 1),)
    )
    self_dependency = TemplateDependency(
        "include", "health.html", False, 1, "present", "valid"
    )
    health = TemplateResolution(
        "found",
        "health.html",
        "present",
        "valid",
        dependencies=(self_dependency,),
        dependency_graph=TemplateDependencyGraph(
            "health.html",
            (TemplateNodeInfo("health.html", "present", "valid", (self_dependency,)),),
            cycles=(cycle,),
        ),
    )
    return RoutesResult(
        (
            RouteInfo("GET", "/contact/list", "contact-index", True, handler),
            RouteInfo("POST", "/contact/create", None, False, handler),
            RouteInfo(
                "GET",
                "/users",
                None,
                True,
                HandlerInfo("Users.list", template=TemplateResolution("dynamic")),
            ),
            RouteInfo(
                "GET", "/health", None, True, HandlerInfo("health", template=health)
            ),
        ),
        ("inventaire partiel",),
    )


@pytest.mark.parametrize(
    "query,indices",
    [
        (None, (0, 1, 2, 3)),
        ("", (0, 1, 2, 3)),
        ("   ", (0, 1, 2, 3)),
        ("/contact/list", (0,)),
        ("Contact.list", (0, 1)),
        ("controllers/contact.py", (0, 1)),
        ("shared.html", (0, 1)),
        ("  CONTACT  ", (0, 1)),
        ("POST", (1,)),
        ("contact-index", (0,)),
        ("absent", ()),
        ("base.html", ()),
        (".*", ()),
    ],
)
def test_search(
    inventory: RoutesResult, query: str | None, indices: tuple[int, ...]
) -> None:
    diagnostics = build_route_diagnostics(inventory)
    view = filter_route_explorer(inventory, diagnostics, RouteFilter(query=query))
    assert view.routes == tuple(inventory.routes[i] for i in indices)
    assert view.total_routes == 4
    if query is None:
        assert view.diagnostics == diagnostics


@pytest.mark.parametrize(
    "criteria,indices",
    [
        (RouteFilter(method="get"), (0, 2, 3)),
        (RouteFilter(method="POST"), (1,)),
        (RouteFilter(visibility="public"), (0, 2, 3)),
        (RouteFilter(visibility="protected"), (1,)),
        (RouteFilter(diagnostics_only=True), (0, 1, 2)),
        (RouteFilter(severity="error"), (0, 1, 2, 3)),
        (RouteFilter(severity="warning"), (0, 1, 2, 3)),
        (RouteFilter(diagnostics_only=True, severity="error"), (0, 1)),
        (RouteFilter(diagnostics_only=True, severity="warning"), (2,)),
        (RouteFilter(diagnostics_only=True, severity="info"), ()),
        (
            RouteFilter(
                query="contact",
                method="POST",
                visibility="protected",
                severity="error",
                diagnostics_only=True,
            ),
            (1,),
        ),
    ],
)
def test_combinations(
    inventory: RoutesResult, criteria: RouteFilter, indices: tuple[int, ...]
) -> None:
    view = filter_route_explorer(
        inventory, build_route_diagnostics(inventory), criteria
    )
    assert view.routes == tuple(inventory.routes[i] for i in indices)
    if criteria.severity != "all":
        assert all(
            item.severity == criteria.severity for item in view.diagnostics.items
        )
    if criteria.diagnostics_only and criteria.severity == "error":
        assert view.diagnostics.error_count == 2  # erreur partagée et cycle global
        assert view.diagnostics.warning_count == 0


def test_validation(inventory: RoutesResult) -> None:
    with pytest.raises(ValueError, match="256"):
        RouteFilter(query=" " * 257)
    assert RouteFilter(query="x" * 256).query == "x" * 256
    for value in ("GTE", "DELETE", " GET "):
        with pytest.raises(ValueError, match="Méthode"):
            filter_route_explorer(
                inventory, build_route_diagnostics(inventory), RouteFilter(method=value)
            )
    with pytest.raises(ValueError, match="Visibilité"):
        RouteFilter(visibility=cast(Visibility, "private"))
    with pytest.raises(ValueError, match="Sévérité"):
        RouteFilter(severity=cast(SeverityFilter, "fatal"))


def test_graph_shared_templates_transitive_and_excluded_routes(
    inventory: RoutesResult,
) -> None:
    diagnostics = build_route_diagnostics(inventory)
    shared = next(
        item for item in diagnostics.items if item.code == "template.dependency_missing"
    )
    assert shared.route_indices == (0, 1)
    view = filter_route_explorer(inventory, diagnostics, RouteFilter(method="POST"))
    graph = build_route_graph(replace(inventory, routes=view.routes))
    assert [n.label for n in graph.nodes if n.kind == "route"] == [
        "POST /contact/create"
    ]
    assert [n.label for n in graph.nodes if n.kind == "handler"] == ["Contact.list"]
    assert [n.label for n in graph.nodes if n.kind == "template"] == [
        "shared.html",
        "base.html",
        "missing.html",
    ]
    assert not any(edge.in_cycle for edge in graph.edges)
    assert any(item.code == "template.cycle" for item in view.diagnostics.items)
    health = filter_route_explorer(inventory, diagnostics, RouteFilter(query="/health"))
    assert any(
        e.in_cycle
        for e in build_route_graph(replace(inventory, routes=health.routes)).edges
    )
    empty = filter_route_explorer(inventory, diagnostics, RouteFilter(query="zzzz"))
    assert build_route_graph(replace(inventory, routes=empty.routes)).nodes == ()
    assert {d.code for d in empty.diagnostics.items} == {
        "template.cycle",
        "route.partial",
    }


def test_filters_are_pure_and_immutable(
    inventory: RoutesResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    diagnostics = build_route_diagnostics(inventory)
    before = repr(inventory), repr(diagnostics)
    criteria = RouteFilter(query="contact", diagnostics_only=True)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Pas d'analyse pendant le filtre")

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "lstat")),
            (Path, ("open", "stat", "lstat", "iterdir", "glob", "rglob")),
            (ast, ("parse",)),
            (Environment, ("parse",)),
            (ToolRegistry, ("get", "list")),
            (bridge, ("read_routes", "detect_template_cycles")),
            (route_diagnostics, ("build_route_diagnostics",)),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        view = filter_route_explorer(inventory, diagnostics, criteria)
        assert view == filter_route_explorer(inventory, diagnostics, criteria)
        graph = build_route_graph(replace(inventory, routes=view.routes))
        assert layout_route_graph(graph).nodes
    assert before == (repr(inventory), repr(diagnostics))
    assert view.routes[0] is inventory.routes[0]
    for obj, field in ((view, "routes"), (criteria, "query")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, field, None)


def test_same_handler_reference_does_not_associate_unrelated_routes() -> None:
    broken = HandlerInfo("Alias.list", "mvc/controllers/a.py", "method-missing")
    healthy = HandlerInfo("Alias.list", "mvc/controllers/b.py", "found")
    result = RoutesResult(
        (
            RouteInfo("GET", "/a", None, True, broken),
            RouteInfo("GET", "/b", None, True, healthy),
        ),
        (),
    )
    diagnostics = build_route_diagnostics(result)
    assert diagnostics.items[0].route_indices == (0,)
    assert filter_route_explorer(
        result, diagnostics, RouteFilter(diagnostics_only=True)
    ).routes == (result.routes[0],)


def test_truncation_is_global_and_does_not_select_a_route() -> None:
    template = TemplateResolution(
        "found",
        "a.html",
        "present",
        "valid",
        dependency_graph=TemplateDependencyGraph("a.html", (), truncated=True),
    )
    result = RoutesResult(
        (
            RouteInfo(
                "GET", "/a", None, True, HandlerInfo("C.index", template=template)
            ),
        ),
        (),
    )
    diagnostics = build_route_diagnostics(result)
    assert diagnostics.items[0].route_indices == ()
    view = filter_route_explorer(
        result, diagnostics, RouteFilter(diagnostics_only=True)
    )
    assert view.routes == () and view.diagnostics == diagnostics
    errors = filter_route_explorer(result, diagnostics, RouteFilter(severity="error"))
    assert errors.routes == result.routes and errors.diagnostics.items == ()
