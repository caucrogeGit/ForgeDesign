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
from forge_design.web.rendering import render_page


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
    return render_page(
        "routes.html",
        {
            "active_page": "routes",
            "current_project": context.inspection,
            "result": result,
            "error": error,
        },
    )
