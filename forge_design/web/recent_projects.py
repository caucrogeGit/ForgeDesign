"""Accueil et actions explicites sur l'historique local."""

from pathlib import Path

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.project_selector import ProjectSelector
from forge_design.recent_project_states import inspect_recent_projects
from forge_design.recent_projects import RecentProjects, RecentProjectsError
from forge_design.web.rendering import render_page
from forge_design.web.security import is_local_action


def show_home(
    request: Request,
    context: CurrentProjectContext,
    store: RecentProjects,
    registry: ToolRegistry,
    *,
    error: str | None = None,
    message: str | None = None,
    selection_warning: str | None = None,
    status: int = 200,
) -> Response:
    recent = store.list()
    return render_page(
        "index.html",
        {
            "active_page": "home",
            "current_project": context.inspection,
            "recent_projects": inspect_recent_projects(recent, registry, context.root),
            "recent_warning": store.warning,
            "error": error,
            "message": message,
            "selection_warning": selection_warning,
        },
        status=status,
    )


def recent_action(
    request: Request,
    context: CurrentProjectContext,
    registry: ToolRegistry,
    store: RecentProjects,
    *,
    selector: ProjectSelector,
    remove: bool = False,
) -> Response:
    if not is_local_action(request):
        return show_home(
            request,
            context,
            store,
            registry,
            error="Origine de la requête non autorisée.",
            status=403,
        )
    if request.header("Content-Type", "").split(";", 1)[0] != (
        "application/x-www-form-urlencoded"
    ):
        return show_home(
            request,
            context,
            store,
            registry,
            error="Format de formulaire non pris en charge.",
            status=415,
        )
    value = request.form("recent")
    if value is None or value not in {item.path for item in store.list()}:
        return show_home(
            request,
            context,
            store,
            registry,
            error="Ce projet n’appartient pas aux projets récents.",
            status=400,
        )
    if not remove:
        selection = selector.open(Path(value))
        if selection.status != "selected":
            return show_home(
                request,
                context,
                store,
                registry,
                error="Le projet récent n’est plus disponible.",
                status=200 if selection.status == "invalid" else 400,
            )
        return show_home(
            request,
            context,
            store,
            registry,
            message="Projet ouvert.",
            selection_warning=selection.recent_warning,
        )
    try:
        store.remove(Path(value))
    except RecentProjectsError as error:
        return show_home(request, context, store, registry, error=str(error))
    return show_home(request, context, store, registry)
