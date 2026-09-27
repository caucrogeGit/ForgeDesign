"""Page de routes en lecture seule, utilisant le contexte existant."""

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
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.route_graph import build_route_graph
from forge_design.web.rendering import render_page
from forge_design.web.route_graph_layout import layout_route_graph


def show_routes(context: CurrentProjectContext, registry: ToolRegistry) -> Response:
    result = None
    error = None
    if context.root is not None:
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
    graph = build_route_graph(result) if result is not None else None
    return render_page(
        "routes.html",
        {
            "active_page": "routes",
            "current_project": context.inspection,
            "result": result,
            "error": error,
            "graph": graph,
            "graph_layout": layout_route_graph(graph) if graph else None,
            "graph_nodes": {node.id: node for node in graph.nodes} if graph else {},
        },
    )
