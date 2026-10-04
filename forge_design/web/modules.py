"""Pages GET de l'hôte des modules spécialisés (FD-MODULES-002).

Le cœur possède le HTML, la navigation, la CSP et l'accessibilité : un module
ne fournit ni template ni handler. Les routes sont exactes et enregistrées par
l'application pour chaque module exposé muni d'une UiEntry, sous /modules/<id>/.
"""

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import MAX_SOURCE_PATH_LENGTH
from forge_design.modules.host import ModuleHost
from forge_design.web.graphics import scene_json_payload
from forge_design.web.rendering import render_page

Handler = Callable[[Request], Response]
_PROJECT_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
)
_STATUS = {"resource-not-found": 404, "resource-refused": 400}


def resource_url(base_url: str, type_id: str, path: str) -> str:
    return f"{base_url}resource?" + urlencode({"type": type_id, "path": path})


def _base(
    host: ModuleHost, module_id: str, context: CurrentProjectContext
) -> dict[str, object]:
    module = host.module(module_id)
    descriptor = module.descriptor
    definition = descriptor.definition
    return {
        "active_page": f"module:{module_id}",
        "current_project": context.inspection,
        "module": module,
        "module_label": definition.ui_entry.label
        if definition.ui_entry
        else definition.name,
        "capabilities": sorted(module.available_capabilities),
        "unavailable": sorted(module.unavailable_dependencies.items()),
        "styles": [
            descriptor.asset_url(asset.name)
            for asset in descriptor.assets
            if asset.name.endswith(".css")
        ],
    }


def show_module(
    request: Request, host: ModuleHost, module_id: str, context: CurrentProjectContext
) -> Response:
    page = _base(host, module_id, context)
    root = context.root
    listings: list[object] = []
    error, status = None, 200
    if root is None:
        error = "Aucun projet ouvert."
    else:
        try:
            for resource_type, listing in host.list_resources(module_id, root):
                listings.append(
                    {
                        "type": resource_type,
                        "listing": listing,
                        "links": [
                            (
                                path,
                                resource_url(
                                    host.module(module_id).descriptor.base_url,
                                    resource_type.id,
                                    path,
                                ),
                            )
                            for path in listing.paths
                        ],
                    }
                )
        except _PROJECT_ERRORS as exc:
            error, status = str(exc), 409
    return render_page(
        "module.html", {**page, "listings": listings, "error": error}, status=status
    )


def parse_resource_query(request: Request) -> tuple[str, str]:
    for key, values in request.params.items():
        if key not in {"type", "path"}:
            raise ValueError("Paramètre inconnu.")
        if len(values) != 1:
            raise ValueError("Une seule valeur est autorisée par paramètre.")
    type_id = request.query("type", "")
    path = request.query("path", "")
    if not type_id:
        raise ValueError("Type de ressource absent.")
    if not path or len(path) > MAX_SOURCE_PATH_LENGTH:
        raise ValueError("Chemin absent ou trop long.")
    return type_id, path


def show_module_resource(
    request: Request, host: ModuleHost, module_id: str, context: CurrentProjectContext
) -> Response:
    page = _base(host, module_id, context)
    view, error, status = None, None, 200
    try:
        type_id, path = parse_resource_query(request)
        host.resource_type(module_id, type_id)
    except (ValueError, KeyError) as exc:
        error, status = (
            (str(exc) if isinstance(exc, ValueError) else "Type de ressource inconnu."),
            400,
        )
    else:
        root: Path | None = context.root
        if root is None:
            error, status = "Aucun projet ouvert.", 409
        else:
            try:
                view = host.read_resource(module_id, type_id, root, path)
            except _PROJECT_ERRORS as exc:
                error, status = str(exc), 409
            else:
                if view.read is not None and view.read.error in _STATUS:
                    status = _STATUS[view.read.error]
    scene = (
        scene_json_payload(dict(view.scene))
        if view is not None and view.scene is not None
        else None
    )
    return render_page(
        "module_resource.html",
        {**page, "view": view, "error": error, "scene": scene},
        status=status,
    )


def module_asset(host: ModuleHost, module_id: str, name: str) -> Handler:
    data, media_type = host.asset(module_id, name)

    def serve(request: Request) -> Response:
        return Response(body=data, content_type=media_type)

    return serve
