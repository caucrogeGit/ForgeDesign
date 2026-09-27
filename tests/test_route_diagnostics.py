"""Diagnostics issus exclusivement de faits déjà disponibles."""

import ast
import builtins
import os
from dataclasses import FrozenInstanceError, replace
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
from forge_design.forge.source import SourceLocation
from forge_design.forge.template_cycles import TemplateCycle, TemplateCycleEdge
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.route_diagnostics import (
    RouteDiagnostics,
    build_route_diagnostics,
)

ROUTE = SourceLocation("mvc/routes/contact.py", 4)
METHOD = SourceLocation("mvc/controllers/contact.py", 8)
VIEW = SourceLocation("mvc/views/a.html")


def result_for(handler: HandlerInfo) -> RoutesResult:
    return RoutesResult((RouteInfo("GET", "/", None, True, handler, ROUTE),), ())


def test_empty_and_unknown_handler_are_not_anomalies() -> None:
    assert build_route_diagnostics(RoutesResult((), ())) == RouteDiagnostics()
    assert (
        build_route_diagnostics(RoutesResult((RouteInfo("GET", "/", None, True),), ()))
        == RouteDiagnostics()
    )
    assert (
        build_route_diagnostics(result_for(HandlerInfo("health"))) == RouteDiagnostics()
    )


def test_known_dynamic_handler_and_opaque_warnings() -> None:
    result = RoutesResult(
        (RouteInfo("GET", "/", None, True, source=ROUTE, handler_dynamic=True),),
        ("Texte opaque controller.missing <script>", "autre texte"),
    )
    diagnostics = build_route_diagnostics(result)
    assert [d.code for d in diagnostics.items] == ["handler.dynamic", "route.partial"]
    assert diagnostics.warning_count == 2 and diagnostics.error_count == 0
    assert diagnostics.items[0].source == ROUTE
    assert diagnostics.items[0].source_available
    assert result.warnings[0].endswith("<script>")


@pytest.mark.parametrize(
    "handler,code,severity",
    [
        (
            HandlerInfo(
                "C.list",
                verification="unreadable",
                missing_controller="mvc/controllers/c.py",
            ),
            "missing",
            "error",
        ),
        (
            HandlerInfo("C.list", "mvc/controllers/c.py", "class-missing"),
            "class_missing",
            "error",
        ),
        (
            HandlerInfo("C.list", "mvc/controllers/c.py", "method-missing"),
            "method_missing",
            "error",
        ),
        (
            HandlerInfo("C.list", "mvc/controllers/c.py", "ambiguous"),
            "ambiguous",
            "warning",
        ),
        (
            HandlerInfo("C.list", "mvc/controllers/c.py", "unreadable"),
            "unreadable",
            "warning",
        ),
    ],
)
def test_controller(handler: HandlerInfo, code: str, severity: str) -> None:
    (diagnostic,) = build_route_diagnostics(result_for(handler)).items
    assert diagnostic.code == "controller." + code
    assert diagnostic.severity == severity
    assert diagnostic.source == (
        ROUTE if code == "missing" else SourceLocation("mvc/controllers/c.py")
    )


@pytest.mark.parametrize(
    "template,code,severity",
    [
        (TemplateResolution("dynamic"), "dynamic", "warning"),
        (TemplateResolution("ambiguous"), "ambiguous", "warning"),
        (TemplateResolution("found", "a.html", "missing"), "missing", "error"),
        (
            TemplateResolution("found", "../a.html", "invalid-path"),
            "invalid_path",
            "error",
        ),
        (TemplateResolution("found", "a.html", "unreadable"), "unreadable", "warning"),
        (
            TemplateResolution("found", "a.html", "present", "unreadable"),
            "unreadable",
            "warning",
        ),
        (
            TemplateResolution(
                "found", "a.html", "present", "invalid", 12, "bad syntax", source=VIEW
            ),
            "syntax_invalid",
            "error",
        ),
    ],
)
def test_template(template: TemplateResolution, code: str, severity: str) -> None:
    handler = HandlerInfo("C.list", template=template, method_source=METHOD)
    (diagnostic,) = build_route_diagnostics(result_for(handler)).items
    assert diagnostic.code == "template." + code
    assert diagnostic.severity == severity
    if code == "syntax_invalid":
        assert diagnostic.source == SourceLocation(VIEW.path, 12)
        assert "12" in diagnostic.message and "bad syntax" in diagnostic.message
    elif template.presence != "present":
        assert diagnostic.source == METHOD


@pytest.mark.parametrize(
    "dependency,code,severity",
    [
        (
            TemplateDependency("include", "b.html", False, 2, "missing"),
            "missing",
            "error",
        ),
        (
            TemplateDependency("extends", "../b.html", False, 2, "invalid-path"),
            "invalid_path",
            "error",
        ),
        (
            TemplateDependency("import", "b.html", False, 2, "unreadable"),
            "unreadable",
            "warning",
        ),
        (
            TemplateDependency("include", "b.html", False, 2, "present", "unreadable"),
            "unreadable",
            "warning",
        ),
        (
            TemplateDependency(
                "from-import", "b.html", False, 2, "present", "invalid", 9, "bad"
            ),
            "syntax_invalid",
            "error",
        ),
    ],
)
def test_dependency(dependency: TemplateDependency, code: str, severity: str) -> None:
    declaration = SourceLocation(VIEW.path, 2)
    dependency = replace(dependency, source=declaration)
    template = TemplateResolution("found", "a.html", dependencies=(dependency,))
    (diagnostic,) = build_route_diagnostics(
        result_for(HandlerInfo("C.list", template=template))
    ).items
    assert diagnostic.code == "template.dependency_" + code
    assert diagnostic.source == declaration and diagnostic.source_available
    assert diagnostic.severity == severity
    if code == "syntax_invalid":
        assert "9" in diagnostic.message and "bad" in diagnostic.message


def test_valid_and_dynamic_dependencies_do_not_add_noise() -> None:
    template = TemplateResolution(
        "found",
        "a.html",
        "present",
        "valid",
        dependencies=(TemplateDependency("include", None, True, 1),),
    )
    assert (
        build_route_diagnostics(result_for(HandlerInfo("C.list", template=template)))
        == RouteDiagnostics()
    )


def test_sharing_cycles_transitive_order_counts_and_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = TemplateDependency(
        "include",
        "missing.html",
        False,
        2,
        "missing",
        source=SourceLocation("mvc/views/base.html", 2),
    )
    cycle = TemplateCycle((TemplateCycleEdge("base.html", "base.html", "include", 1),))
    closure = TemplateDependencyGraph(
        "a.html",
        (TemplateNodeInfo("base.html", "present", "valid", (dependency,), VIEW),),
        True,
        (cycle,),
    )
    template = TemplateResolution(
        "found",
        "a.html",
        "present",
        "invalid",
        7,
        "bad",
        dependencies=(dependency,),
        dependency_graph=closure,
        source=VIEW,
    )
    first = result_for(HandlerInfo("C.list", template=template)).routes[0]
    second = replace(first, path="/second")
    result = RoutesResult((first, second), ("opaque",))
    before = repr(result)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Aucune analyse dans le consolidateur")

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "lstat")),
            (Path, ("open", "stat", "lstat", "iterdir", "glob", "rglob")),
            (ast, ("parse",)),
            (Environment, ("parse",)),
            (ToolRegistry, ("get", "list")),
            (bridge, ("read_routes", "detect_template_cycles")),
            (template_cycles, ("detect_template_cycles",)),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        diagnostics = build_route_diagnostics(result)
        assert diagnostics == build_route_diagnostics(result)
    assert [d.code for d in diagnostics.items] == [
        "template.syntax_invalid",
        "template.dependency_missing",
        "template.cycle",
        "template.analysis_truncated",
        "route.partial",
    ]
    assert (
        diagnostics.error_count,
        diagnostics.warning_count,
        diagnostics.info_count,
    ) == (3, 2, 0)
    assert repr(result) == before
    for value, field in ((diagnostics, "items"), (diagnostics.items[0], "code")):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, ())


def test_dependency_syntax_shared_across_parents() -> None:
    dependency = TemplateDependency(
        "include", "b.html", False, 1, "present", "invalid", 3, "bad"
    )
    routes: list[RouteInfo] = []
    for name in ("a.html", "c.html"):
        template = TemplateResolution(
            "found",
            name,
            dependencies=(
                replace(dependency, source=SourceLocation("mvc/views/" + name, 1)),
            ),
        )
        routes.append(result_for(HandlerInfo("C.list", template=template)).routes[0])
    diagnostics = build_route_diagnostics(RoutesResult(tuple(routes), ()))
    assert len(diagnostics.items) == 1


def test_non_navigable_source_is_text_only() -> None:
    handler = HandlerInfo(
        "C.list",
        template=TemplateResolution("dynamic"),
        method_source=SourceLocation("../secret"),
    )
    (diagnostic,) = build_route_diagnostics(result_for(handler)).items
    assert diagnostic.source == handler.method_source
    assert not diagnostic.source_available


def test_missing_fact_retained_by_bridge(tmp_path: Path) -> None:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).write_text("raise AssertionError")
    directory = tmp_path / "mvc/routes"
    directory.mkdir(parents=True)
    (directory / "__init__.py").write_text(
        "from mvc.controllers.missing import Missing\nrouter = Router()\n"
        'router.add("GET", "/", Missing.index)\n'
    )
    result = bridge.read_routes(tmp_path)
    assert result.routes[0].handler is not None
    assert result.routes[0].handler.missing_controller == "mvc/controllers/missing.py"
    assert build_route_diagnostics(result).items[0].code == "controller.missing"


def test_cycle_and_dependency_shared_between_distinct_roots() -> None:
    cycle = TemplateCycle((TemplateCycleEdge("base.html", "base.html", "include", 3),))
    source = SourceLocation("mvc/views/base.html", 3)
    dependency = TemplateDependency(
        "include", "missing.html", False, 3, "missing", source=source
    )
    node = TemplateNodeInfo("base.html", "present", "valid", (dependency,), source)
    routes: list[RouteInfo] = []
    for name in ("a.html", "b.html"):
        closure = TemplateDependencyGraph(name, (node,), True, (cycle,))
        template = TemplateResolution("found", name, dependency_graph=closure)
        routes.append(result_for(HandlerInfo("C.list", template=template)).routes[0])
    diagnostics = build_route_diagnostics(RoutesResult(tuple(routes), ()))
    assert [d.code for d in diagnostics.items] == [
        "template.dependency_missing",
        "template.cycle",
        "template.analysis_truncated",
        "template.analysis_truncated",
    ]
    assert diagnostics.items[1].source == source
    assert diagnostics.error_count == 2 and diagnostics.warning_count == 2
