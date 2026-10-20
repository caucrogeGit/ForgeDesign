"""Frontière Web de Project Inspector : formulaire, délégation et rendu Forge."""

from collections.abc import Callable
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
from forge_design.tools.project_health import (
    ProjectHealthSummary,
    summarize_project_health,
)
from forge_design.tools.project_inspector import ProjectInspection
from forge_design.web.rendering import render_page
from forge_design.web.security import is_local_action

MAX_PATH_LENGTH = 4096
PREVIEW_STILL_RUNNING = (
    "La preview réelle n'a pas pu être arrêtée : le projet courant est conservé."
)


def _render(
    context: CurrentProjectContext,
    path: str = "",
    *,
    registry: ToolRegistry | None = None,
    result: ProjectInspection | None = None,
    error: str | None = None,
    message: str | None = None,
    status: int = 200,
) -> Response:
    # Synthèse du projet courant, recalculée à chaque affichage (jamais mise en
    # cache) ; la racine vient du contexte, jamais d'un paramètre HTTP.
    health: ProjectHealthSummary | None = None
    if registry is not None and context.root is not None:
        health = summarize_project_health(
            context.root,
            registry,
            # Inspection que l'action vient de faire pour le projet courant :
            # réutilisée, jamais relancée (une seule inspection par action).
            inspection=result
            if result is not None and result.root == context.root
            else None,
        )
    return render_page(
        "inspector.html",
        {
            "path": path,
            "result": result,
            "details": result
            if result is not None
            else health.inspection
            if health is not None
            else None,
            "health": health,
            "error": error,
            "message": message,
            "max_path_length": MAX_PATH_LENGTH,
            "active_page": "inspector",
            "current_project": context.inspection,
        },
        status=status,
    )


def show_opened_project(
    context: CurrentProjectContext,
    registry: ToolRegistry,
    result: ProjectInspection | None,
    *,
    warning: str | None = None,
) -> Response:
    """Vue d'ensemble du projet que l'on vient d'ouvrir depuis l'accueil (FD-UX-011).

    L'inspection de l'ouverture est réutilisée, jamais relancée.
    """
    message = (
        f"Projet ouvert. Avertissement : {warning}" if warning else "Projet ouvert."
    )
    return _render(context, registry=registry, result=result, message=message)


def show_inspector(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    """Formulaire et, si un projet est sélectionné, sa synthèse de santé.

    Lecture seule : le contexte n'est jamais modifié ici, même si le projet est
    devenu inaccessible (seul « Actualiser » ferme un projet).
    """
    return _render(context, registry=registry)


OpenFailure = Callable[[str, str, int], Response]


def inspect_submission(
    request: Request,
    selector: ProjectSelector,
    context: CurrentProjectContext,
    *,
    failure: OpenFailure | None = None,
) -> Response:
    """Valider les données HTTP puis déléguer au service de sélection.

    Route POST activant le projet en mémoire, sans session : l'origine HTTP locale
    exacte est obligatoire à la place du CSRF Forge fondé sur une session.
    Aucun chemin n'est résolu ou lu ici ; Path adapte uniquement le type d'entrée.

    L'accueil est le seul formulaire d'ouverture (FD-UX-010) : un échec
    d'ouverture lui est rendu par ``failure``, avec le chemin saisi. Un projet
    inspecté mais non reconnu reste affiché ici, avec ses constats.
    """

    def fail(error: str, path: str, status: int) -> Response:
        if failure is not None:
            return failure(error, path, status)
        return _render(context, path, error=error, status=status)

    if not is_local_action(request):
        return fail("Origine de la requête non autorisée.", "", 403)
    if request.header("Content-Type", "").split(";", 1)[0] != (
        "application/x-www-form-urlencoded"
    ):
        return fail("Format de formulaire non pris en charge.", "", 415)
    path = request.form("path")
    if path is None or not path or path.isspace():
        return fail("Saisissez le chemin du projet.", "", 400)
    if len(path) > MAX_PATH_LENGTH:
        return fail("Le chemin dépasse la limite de 4096 caractères.", "", 400)
    selection = selector.open(Path(path))
    if selection.status not in {"selected", "invalid"}:
        return fail(
            selection.error or "Ouverture impossible.",
            path,
            409 if selection.status == "busy" else 400,
        )
    registry = selector.registry
    message = (
        f"Projet ouvert. Avertissement : {selection.recent_warning}"
        if selection.recent_warning
        else None
    )
    return _render(
        context,
        path,
        registry=registry,
        result=selection.inspection,
        error=selection.error,
        message=message,
    )


def refresh_project(
    request: Request,
    registry: ToolRegistry,
    context: CurrentProjectContext,
    *,
    release: Callable[[], bool] | None = None,
) -> Response:
    """Réinspecter uniquement la racine courante, sans utiliser de chemin HTTP.

    release (arrêt de la preview réelle) précède toute fermeture ou tout
    changement de racine ; s'il échoue, le projet courant est conservé.
    """
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
        if release is not None and not release():
            return _render(context, error=PREVIEW_STILL_RUNNING, status=409)
        context.clear()
        return _render(context, error=f"Projet fermé : {error}", status=400)
    if not isinstance(result, ProjectInspection):
        raise TypeError("project-inspector doit retourner ProjectInspection.")
    if (not result.valid or result.root != root) and (
        release is not None and not release()
    ):
        return _render(context, error=PREVIEW_STILL_RUNNING, status=409)
    if not result.valid:
        context.clear()
        return _render(
            context,
            result=result,
            error="Le projet n’est plus reconnu. Il a été fermé.",
        )
    context.set_project(result)
    return _render(
        context, registry=registry, result=result, message="Projet actualisé."
    )
