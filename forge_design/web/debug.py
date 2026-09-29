"""Page Debug Center, sans activation ni cache de projet."""

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.debug_errors import DebugErrorsResult
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.web.rendering import render_page


def show_debug(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    result = None
    error = None
    if context.root is not None:
        try:
            result = registry.get("debug-center").run(context.root)
        except (
            ProjectRootNotFoundError,
            ProjectRootNotDirectoryError,
            ProjectRootResolutionError,
            NotForgeProjectError,
        ) as exc:
            error = str(exc)
        if result is not None and not isinstance(result, DebugErrorsResult):
            raise TypeError("debug-center doit retourner DebugErrorsResult.")
    return render_page(
        "debug.html",
        {
            "active_page": "debug",
            "current_project": context.inspection,
            "result": result,
            "error": error,
        },
    )
