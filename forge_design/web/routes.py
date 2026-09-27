"""Page de routes en lecture seule, utilisant le contexte existant."""

from dataclasses import replace

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.routes import (
    RoutesResult,
    RoutesSourceMissingError,
    RoutesSourceUnreadableError,
)
from forge_design.forge.template_cycles import TemplateCycle
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.route_diagnostics import build_route_diagnostics
from forge_design.tools.route_filters import RouteFilter, filter_route_explorer
from forge_design.tools.route_graph import build_route_graph
from forge_design.web.rendering import render_page
from forge_design.web.route_filters import parse_route_filter
from forge_design.web.route_graph_layout import layout_route_graph
from forge_design.web.source import source_url


def show_routes(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    result = None
    error = None
    status = 200
    filters = RouteFilter()
    diagnostics = None
    methods: tuple[str, ...] = ()
    total_routes = 0
    try:
        filters = parse_route_filter(request)
    except ValueError as exc:
        error, status = str(exc), 400
    if context.root is not None and error is None:
        try:
            result = registry.get("route-explorer").run(context.root)
        except (
            ProjectRootNotFoundError,
            ProjectRootNotDirectoryError,
            ProjectRootResolutionError,
            NotForgeProjectError,
            RoutesSourceMissingError,
            RoutesSourceUnreadableError,
        ) as exc:
            error = str(exc)
        if result is not None and not isinstance(result, RoutesResult):
            raise TypeError("route-explorer doit retourner RoutesResult.")
    if result is not None:
        methods = tuple(dict.fromkeys(route.method for route in result.routes))
        total_routes = len(result.routes)
        diagnostics = build_route_diagnostics(result)
        try:
            view = filter_route_explorer(result, diagnostics, filters)
            diagnostics = view.diagnostics
            result = replace(result, routes=view.routes)
        except ValueError as exc:
            error, status, result = str(exc), 400, None
    elif error is None and filters.method is not None:
        error, status = "Méthode absente de l’inventaire des routes.", 400
    cycles: dict[tuple[tuple[str, str, str], ...], TemplateCycle] = {}
    partial = False
    if result is not None:
        for route in result.routes:
            closure = route.handler.template.dependency_graph if route.handler else None
            if closure is not None:
                partial = partial or closure.truncated
                for cycle in closure.cycles:
                    cycles.setdefault(cycle.key, cycle)
    graph = build_route_graph(result) if result is not None and result.routes else None
    return render_page(
        "routes.html",
        {
            "active_page": "routes",
            "current_project": context.inspection,
            "result": result,
            "diagnostics": diagnostics,
            "filters": filters,
            "methods": methods,
            "total_routes": total_routes,
            "error": error,
            "source_url": source_url,
            "template_cycles": tuple(cycles.values()),
            "cycles_partial": partial,
            "graph": graph,
            "graph_layout": layout_route_graph(graph) if graph else None,
            "graph_nodes": {node.id: node for node in graph.nodes} if graph else {},
        },
        status=status,
    )
