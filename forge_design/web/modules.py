"""Pages de l'hôte des modules spécialisés (FD-MODULES-002, FD-EDIT-001).

Le cœur possède le HTML, la navigation, la CSP et l'accessibilité : un module
ne fournit ni template ni handler. Les routes sont exactes et enregistrées par
l'application pour chaque module exposé muni d'une UiEntry, sous /modules/<id>/.

Actions (FD-EDIT-001) : un POST exact par action exposée,
/modules/<id>/actions/<action>. Le cœur contrôle l'origine, le format, la
taille, l'enveloppe (type, path, revision) et les champs, puis délègue le cycle
lecture → handler → écriture à ModuleHost ; il choisit seul le statut HTTP et
redirige (303) vers la page ressource après succès ou absence de changement.

Édition (FD-GRAPHICS-EDIT-001) : la page ressource transporte, en JSON inerte, le
contexte calculé par l'hôte pour le script d'édition déclaré par le module ; le
client générique /module-resource.js l'importe. Aucun script de module n'est
chargé ailleurs.
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
from forge_design.modules.actions import (
    MAX_MODULE_ACTION_BYTES,
    MAX_MODULE_ACTION_FIELDS,
    is_revision_token,
)
from forge_design.modules.host import ActionOutcomeCode, ModuleHost
from forge_design.web.graphics import scene_json_payload
from forge_design.web.rendering import render_page
from forge_design.web.security import is_local_action

Handler = Callable[[Request], Response]
_PROJECT_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
)
_STATUS = {"resource-not-found": 404, "resource-refused": 400}
_FORM = "application/x-www-form-urlencoded"
# Retour POST/Redirect/GET : seule information transportée, liste fermée.
NOTICES = {"saved": "Modification enregistrée.", "unchanged": "Aucune modification."}
# Matrice normative des issues d'action (docs/modules/module-actions.md).
ACTION_STATUS: dict[ActionOutcomeCode, int] = {
    "saved": 303,
    "unchanged": 303,
    "payload-invalid": 400,
    "type-mismatch": 400,
    "resource-refused": 400,
    "resource-not-found": 404,
    "resource-unusable": 409,
    "conflict": 409,
    "refused": 422,
    "invalid-resource": 422,
    "module-error": 500,
    "write-failed": 500,
}


def resource_url(
    base_url: str, type_id: str, path: str, notice: str | None = None
) -> str:
    query = {"type": type_id, "path": path}
    if notice is not None:
        query["notice"] = notice
    return f"{base_url}resource?" + urlencode(query)


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


def parse_resource_query(request: Request) -> tuple[str, str, str | None]:
    for key, values in request.params.items():
        if key not in {"type", "path", "notice"}:
            raise ValueError("Paramètre inconnu.")
        if len(values) != 1:
            raise ValueError("Une seule valeur est autorisée par paramètre.")
    type_id = request.query("type", "")
    path = request.query("path", "")
    notice = request.query("notice")
    if not type_id:
        raise ValueError("Type de ressource absent.")
    if not path or len(path) > MAX_SOURCE_PATH_LENGTH:
        raise ValueError("Chemin absent ou trop long.")
    if notice is not None and notice not in NOTICES:
        raise ValueError("Notice inconnue.")
    return type_id, path, notice


def show_module_resource(
    request: Request, host: ModuleHost, module_id: str, context: CurrentProjectContext
) -> Response:
    page = _base(host, module_id, context)
    view, error, status, notice = None, None, 200, None
    try:
        type_id, path, notice = parse_resource_query(request)
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
    editor = (
        scene_json_payload(dict(view.editor))
        if view is not None and view.editor is not None
        else None
    )
    return render_page(
        "module_resource.html",
        {
            **page,
            "view": view,
            "error": error,
            "scene": scene,
            "editor": editor,
            "notice": NOTICES.get(notice or "") if error is None else None,
        },
        status=status,
    )


class ActionRequestError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


def parse_action_request(request: Request) -> tuple[str, str, str, dict[str, str]]:
    """Enveloppe et champs d'une action, bornés avant tout accès au projet.

    Le corps est celui déjà analysé par Forge (parse_qs) : aucun parseur HTTP
    parallèle. Chaque champ est fourni une seule fois ; les champs réservés
    (type, path, revision) forment l'enveloppe, les autres le payload.
    """
    if request.header("Content-Type", "").split(";", 1)[0].strip() != _FORM:
        raise ActionRequestError(415, "Formulaire encodé attendu.")
    try:
        length = int(request.header("Content-Length", "0"))
    except ValueError:
        raise ActionRequestError(400, "Longueur de corps invalide.") from None
    if length > MAX_MODULE_ACTION_BYTES:
        raise ActionRequestError(413, "Corps d'action trop volumineux.")
    if request.params:
        raise ActionRequestError(400, "Paramètres d'URL refusés pour une action.")
    body = request.body
    if len(body) > MAX_MODULE_ACTION_FIELDS + 3:
        raise ActionRequestError(400, "Trop de champs.")
    if any(len(values) != 1 for values in body.values()):
        raise ActionRequestError(400, "Chaque champ doit être fourni une seule fois.")
    fields = {key: values[0] for key, values in body.items()}
    if "_method" in fields:
        raise ActionRequestError(400, "Champ réservé refusé : _method.")
    type_id = fields.pop("type", "")
    path = fields.pop("path", "")
    token = fields.pop("revision", "")
    if not type_id or not path or len(path) > MAX_SOURCE_PATH_LENGTH:
        raise ActionRequestError(400, "Type et chemin de ressource requis.")
    if not is_revision_token(token):
        raise ActionRequestError(400, "Jeton de révision absent ou invalide.")
    return type_id, path, token, fields


def module_action(
    request: Request,
    host: ModuleHost,
    module_id: str,
    action_id: str,
    context: CurrentProjectContext,
) -> Response:
    """POST d'une action exposée : statut et redirection décidés par le cœur."""
    page = _base(host, module_id, context)
    target: str | None = None
    issues: tuple[object, ...] = ()
    try:
        if not is_local_action(request):
            raise ActionRequestError(403, "Origine de la requête non autorisée.")
        type_id, path, token, fields = parse_action_request(request)
        root = context.root
        if root is None:
            raise ActionRequestError(409, "Aucun projet ouvert.")
        try:
            outcome = host.execute_action(
                module_id, action_id, root, type_id, path, token, fields
            )
        except _PROJECT_ERRORS as exc:
            raise ActionRequestError(409, str(exc)) from None
    except ActionRequestError as exc:
        status, message = exc.status, str(exc)
    else:
        status, message = ACTION_STATUS[outcome.code], outcome.message
        if status == 303:
            base_url = host.module(module_id).descriptor.base_url
            notice = "saved" if outcome.code == "saved" else "unchanged"
            location = resource_url(base_url, type_id, path, notice)
            return Response(303, b"", headers={"Location": location})
        issues = outcome.issues
        if outcome.code not in {"type-mismatch", "resource-refused"}:
            target = resource_url(
                host.module(module_id).descriptor.base_url, type_id, path
            )
    return render_page(
        "module_action.html",
        {**page, "error": message, "issues": issues, "resource_link": target},
        status=status,
    )


def module_asset(host: ModuleHost, module_id: str, name: str) -> Handler:
    data, media_type = host.asset(module_id, name)

    def serve(request: Request) -> Response:
        return Response(body=data, content_type=media_type)

    return serve
