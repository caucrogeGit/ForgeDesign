"""Page de routes en lecture seule, utilisant le contexte existant."""

from dataclasses import replace
from pathlib import Path

from core.http.request import Request
from core.http.response import Response

from forge_design.contracts.linkage import (
    ViewContractLinksResult,
    analyze_view_contract_links,
)
from forge_design.contracts.reader import view_contract_source
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
from forge_design.forge.templates import TemplatesResult
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.real_preview.route_selection import (
    RealPreviewRouteSelection,
    route_preview_selection,
)
from forge_design.tools.route_diagnostics import build_route_diagnostics
from forge_design.tools.route_filters import RouteFilter, filter_route_explorer
from forge_design.tools.route_graph import build_route_graph
from forge_design.tools.route_linkage import (
    RouteLinkage,
    RouteLinkageReport,
    build_route_linkage,
)
from forge_design.web.graphics import scene_json_payload
from forge_design.web.real_preview import REAL_PREVIEW_WARNING
from forge_design.web.rendering import render_page
from forge_design.web.route_filters import parse_route_filter
from forge_design.web.route_graph_layout import layout_route_graph
from forge_design.web.route_graph_scene import build_route_graphic_scene
from forge_design.web.source import source_url
from forge_design.web.template_viewer import template_url

_PROJECT_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
)


def contract_url(path: str) -> str | None:
    """Vue source en lecture seule d'un contrat (chemin relatif à mvc/views)."""
    source = view_contract_source(path)
    return source_url(source) if source is not None else None


def _contract_links(
    registry: ToolRegistry, root: Path
) -> tuple[ViewContractLinksResult | None, str | None]:
    """Un inventaire des templates (Template Viewer) et une analyse des liens
    contrats ↔ templates par affichage, jamais par route."""
    try:
        templates = registry.get("template-viewer").run(root)
        if not isinstance(templates, TemplatesResult):
            raise TypeError("template-viewer doit retourner TemplatesResult.")
        return analyze_view_contract_links(root, templates), None
    except _PROJECT_ERRORS as exc:
        return None, f"Analyse des contrats de vue indisponible : {exc}"


def show_routes(
    request: Request,
    context: CurrentProjectContext,
    registry: ToolRegistry,
    *,
    real_preview_enabled: bool = False,
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
    linkage: RouteLinkageReport | None = None
    chains: tuple[RouteLinkage, ...] = ()
    previews: dict[int, RealPreviewRouteSelection] = {}
    if result is not None and context.root is not None:
        methods = tuple(dict.fromkeys(route.method for route in result.routes))
        total_routes = len(result.routes)
        diagnostics = build_route_diagnostics(result)
        try:
            view = filter_route_explorer(result, diagnostics, filters)
        except ValueError as exc:
            error, status, result = str(exc), 400, None
        else:
            # Chaînes construites sur le résultat complet (indices des
            # diagnostics), puis restreintes aux routes affichées.
            links, reason = _contract_links(registry, context.root)
            linkage = build_route_linkage(
                result, diagnostics, links, contracts_reason=reason
            )
            chains = linkage.select(view.routes)
            # Éligibilité sur l'inventaire complet : l'unicité de GET <chemin> ne
            # dépend pas des filtres affichés (FD-REALPREVIEW-008).
            full = result
            previews = {
                chain.index: route_preview_selection(chain.route, full)
                for chain in chains
            }
            diagnostics = view.diagnostics
            result = replace(result, routes=view.routes)
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
    layout = layout_route_graph(graph) if graph else None
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
            "graph_layout": layout,
            "graph_scene": (
                scene_json_payload(build_route_graphic_scene(layout))
                if layout
                else None
            ),
            "graph_nodes": {node.id: node for node in graph.nodes} if graph else {},
            "linkage": linkage,
            "chains": chains,
            "previews": previews,
            "real_preview_enabled": real_preview_enabled,
            "real_preview_warning": REAL_PREVIEW_WARNING,
            "template_url": template_url,
            "contract_url": contract_url,
        },
        status=status,
    )
