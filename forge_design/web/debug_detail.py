"""Détail runtime via le Tool uniquement, sans lecture JSONL indépendante."""

from urllib.parse import urlencode

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.debug_errors import DebugError, DebugErrorsResult
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import MAX_DEBUG_EVENT_ID_LENGTH
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_detail import find_debug_event
from forge_design.tools.debug_flow import build_debug_flow
from forge_design.web.debug_flow_layout import layout_debug_flow
from forge_design.web.debug_flow_scene import build_debug_graphic_scene
from forge_design.web.graphics import scene_json_payload
from forge_design.web.rendering import render_page


def debug_event_url(event: DebugError) -> str | None:
    if not event.id or len(event.id) > MAX_DEBUG_EVENT_ID_LENGTH:
        return None
    return "/debug/event?" + urlencode({"line": event.line_number, "id": event.id})


def parse_debug_detail(request: Request) -> tuple[int, str]:
    for key, values in request.params.items():
        if key not in {"line", "id"}:
            raise ValueError("Paramètre de détail inconnu.")
        if len(values) != 1:
            raise ValueError("Une seule valeur est autorisée par paramètre.")
    line = request.query("line", "")
    event_id = request.query("id", "")
    # Même politique numérique que /source ; Request élimine les valeurs vides.
    if not line.isascii() or not line.isdigit() or len(line) > 9 or int(line) < 1:
        raise ValueError("Numéro de ligne invalide.")
    # Borne Web en caractères, sans regex ni normalisation de l’id.
    if not event_id or len(event_id) > MAX_DEBUG_EVENT_ID_LENGTH:
        raise ValueError("Identifiant absent ou trop long.")
    return int(line), event_id


def show_debug_detail(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    result = None
    event = None
    error = None
    status = 200
    try:
        line, event_id = parse_debug_detail(request)
    except ValueError as exc:
        error, status = str(exc), 400
    else:
        if context.root is None:
            error, status = "Aucun projet ouvert.", 409
        else:
            try:
                result = registry.get("debug-center").run(context.root)
            except (
                ProjectRootNotFoundError,
                ProjectRootNotDirectoryError,
                ProjectRootResolutionError,
                NotForgeProjectError,
            ) as exc:
                # Contexte projet devenu inutilisable, comme pour la liste.
                error, status = str(exc), 409
            else:
                if not isinstance(result, DebugErrorsResult):
                    raise TypeError("debug-center doit retourner DebugErrorsResult.")
                event = find_debug_event(result, line_number=line, event_id=event_id)
                if event is None:
                    error, status = (
                        "Cet événement n’est plus disponible "
                        "dans la lecture actuelle du journal.",
                        404,
                    )
    # Flux, layout et scène calculés une seule fois ; aucun moteur sans étape.
    flow_layout = (
        layout_debug_flow(build_debug_flow(event)) if event is not None else None
    )
    return render_page(
        "debug_detail.html",
        {
            "active_page": "debug",
            "current_project": context.inspection,
            "event": event,
            "flow_layout": flow_layout,
            "flow_scene": scene_json_payload(build_debug_graphic_scene(flow_layout))
            if flow_layout is not None and flow_layout.nodes
            else None,
            "error": error,
            "truncated": result.truncated
            if isinstance(result, DebugErrorsResult)
            else False,
        },
        status=status,
    )
