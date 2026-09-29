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
from forge_design.limits import MAX_FILTER_QUERY_LENGTH
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_filters import (
    CATEGORIES,
    LEVELS,
    DebugFilter,
    filter_debug_events,
)
from forge_design.web.debug_filters import parse_debug_filters
from forge_design.web.rendering import render_page


def show_debug(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    result = None
    error = None
    status = 200
    filters = DebugFilter()
    try:
        filters = parse_debug_filters(request)
    except ValueError as exc:
        error, status = str(exc), 400
    if context.root is not None and error is None:
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
            "filters": filters,
            "levels": LEVELS,
            "categories": CATEGORIES,
            "query_limit": MAX_FILTER_QUERY_LENGTH,
            "view": filter_debug_events(result, filters)
            if result is not None
            else None,
        },
        status=status,
    )
