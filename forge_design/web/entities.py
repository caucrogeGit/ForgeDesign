"""Page Entity Explorer, sans activation ni cache de projet."""

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.entities import EntitiesResult
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.entity_diagnostics import build_entity_diagnostics
from forge_design.tools.entity_filters import EntityFilter, filter_entities
from forge_design.tools.entity_graph import build_entity_graph_from_items
from forge_design.web.entity_filters import parse_entity_filter
from forge_design.web.entity_graph_layout import layout_entity_graph
from forge_design.web.rendering import render_page
from forge_design.web.source import source_available, source_url


def show_entities(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    result = None
    error = None
    status = 200
    filters = EntityFilter()
    view = None
    try:
        filters = parse_entity_filter(request)
    except ValueError as exc:
        error, status = str(exc), 400
    if context.root is not None and error is None:
        try:
            result = registry.get("entity-explorer").run(context.root)
        except (
            ProjectRootNotFoundError,
            ProjectRootNotDirectoryError,
            ProjectRootResolutionError,
            NotForgeProjectError,
        ) as exc:
            error = str(exc)
        if result is not None and not isinstance(result, EntitiesResult):
            raise TypeError("entity-explorer doit retourner EntitiesResult.")
    if result is not None:
        view = filter_entities(result, build_entity_diagnostics(result), filters)
    return render_page(
        "entities.html",
        {
            "active_page": "entities",
            "current_project": context.inspection,
            "result": result,
            "view": view,
            "filters": filters,
            "source_available": source_available,
            "source_url": source_url,
            "error": error,
            "diagnostics": (view.diagnostics if view is not None else None),
            "entity_layout": (
                layout_entity_graph(
                    build_entity_graph_from_items(view.graph_entities, view.relations)
                )
                if view is not None
                else None
            ),
        },
        status=status,
    )
