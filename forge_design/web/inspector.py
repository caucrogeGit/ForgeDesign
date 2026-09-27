"""Frontière Web de Project Inspector : formulaire, délégation et rendu Forge."""

from pathlib import Path

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.project_selector import ProjectSelector
from forge_design.tools.project_inspector import ProjectInspection
from forge_design.web.rendering import render_page
from forge_design.web.security import is_local_action

MAX_PATH_LENGTH = 4096


def _render(
    context: CurrentProjectContext,
    path: str = "",
    *,
    result: ProjectInspection | None = None,
    error: str | None = None,
    message: str | None = None,
    status: int = 200,
) -> Response:
    return render_page(
        "inspector.html",
        {
            "path": path,
            "result": result,
            "error": error,
            "message": message,
            "max_path_length": MAX_PATH_LENGTH,
            "active_page": "inspector",
            "current_project": context.inspection,
        },
        status=status,
    )


def show_inspector(request: Request, context: CurrentProjectContext) -> Response:
    """Afficher un formulaire vierge, sans nouvelle inspection."""
    return _render(context)


def inspect_submission(
    request: Request,
    selector: ProjectSelector,
    context: CurrentProjectContext,
) -> Response:
    """Valider les données HTTP puis déléguer au service de sélection.

    Route POST activant le projet en mémoire, sans session : l'origine HTTP locale
    exacte est obligatoire à la place du CSRF Forge fondé sur une session.
    Aucun chemin n'est résolu ou lu ici ; Path adapte uniquement le type d'entrée.
    """
    if not is_local_action(request):
        return _render(
            context, error="Origine de la requête non autorisée.", status=403
        )
    if request.header("Content-Type", "").split(";", 1)[0] != (
        "application/x-www-form-urlencoded"
    ):
        return _render(
            context, error="Format de formulaire non pris en charge.", status=415
        )
    path = request.form("path")
    if path is None or not path or path.isspace():
        return _render(context, error="Saisissez le chemin du projet.", status=400)
    if len(path) > MAX_PATH_LENGTH:
        return _render(
            context, error="Le chemin dépasse la limite de 4096 caractères.", status=400
        )
    selection = selector.open(Path(path))
    message = (
        f"Projet ouvert ; avertissement : {selection.recent_warning}"
        if selection.recent_warning
        else None
    )
    return _render(
        context,
        path,
        result=selection.inspection,
        error=selection.error,
        message=message,
        status=200 if selection.status in {"selected", "invalid"} else 400,
    )


def refresh_project(
    request: Request, registry: ToolRegistry, context: CurrentProjectContext
) -> Response:
    """Réinspecter uniquement la racine courante, sans utiliser de chemin HTTP."""
    if not is_local_action(request):
        return _render(
            context, error="Origine de la requête non autorisée.", status=403
        )
    root = context.root
    if root is None:
        return _render(context, error="Aucun projet à actualiser.", status=409)
    try:
        result = registry.get("project-inspector").run(root)
    except (
        ProjectRootNotFoundError,
        ProjectRootNotDirectoryError,
        ProjectRootResolutionError,
    ) as error:
        context.clear()
        return _render(context, error=f"Projet fermé : {error}", status=400)
    if not isinstance(result, ProjectInspection):
        raise TypeError("project-inspector doit retourner ProjectInspection.")
    if not result.valid:
        context.clear()
        return _render(
            context,
            result=result,
            error="Le projet n’est plus reconnu ; il a été fermé.",
        )
    context.set_project(result)
    return _render(context, result=result, message="Projet actualisé.")
