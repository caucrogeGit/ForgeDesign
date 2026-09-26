"""Frontière Web de Project Inspector : formulaire, délégation et rendu Forge."""

import re
from importlib.resources import as_file, files
from pathlib import Path

from core.http.request import Request
from core.http.response import Response

# Forge rc9 ne fournit pas de marqueur py.typed pour ce paquet public.
from integrations.jinja2.renderer import (  # pyright: ignore[reportMissingTypeStubs]
    Jinja2Renderer,
)

from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.project_inspector import ProjectInspection

MAX_PATH_LENGTH = 4096


def _render(
    path: str = "",
    *,
    result: ProjectInspection | None = None,
    error: str | None = None,
    status: int = 200,
) -> Response:
    # Seules les ressources du paquet sont ouvertes par cette couche.
    with as_file(files("forge_design.web").joinpath("templates")) as templates:
        renderer = Jinja2Renderer(str(templates))
        html = renderer.render(
            "inspector.html",
            {
                "path": path,
                "result": result,
                "error": error,
                "max_path_length": MAX_PATH_LENGTH,
            },
        )
    return Response.html(html, status=status)


def show_inspector(request: Request) -> Response:
    """Afficher un formulaire vierge, sans inspection ni état mémorisé."""
    return _render()


def inspect_submission(request: Request, registry: ToolRegistry) -> Response:
    """Valider les données HTTP puis déléguer intégralement au Tool enregistré.

    Route POST publique en lecture seule, sans session : l'origine HTTP locale
    exacte est obligatoire à la place du CSRF Forge fondé sur une session.
    Aucun chemin n'est résolu ou lu ici ; Path adapte uniquement le type d'entrée.
    """
    host = request.header("Host", "")
    if (
        re.fullmatch(r"127\.0\.0\.1(?::[0-9]{1,5})?", host) is None
        or request.header("Origin") != f"http://{host}"
        or request.header("Sec-Fetch-Site") not in (None, "same-origin")
    ):
        return _render(error="Origine de la requête non autorisée.", status=403)
    if request.header("Content-Type", "").split(";", 1)[0] != (
        "application/x-www-form-urlencoded"
    ):
        return _render(error="Format de formulaire non pris en charge.", status=415)
    path = request.form("path")
    if path is None or not path or path.isspace():
        return _render(error="Saisissez le chemin du projet.", status=400)
    if len(path) > MAX_PATH_LENGTH:
        return _render(
            error="Le chemin dépasse la limite de 4096 caractères.", status=400
        )
    try:
        result = registry.get("project-inspector").run(Path(path))
    except (
        ProjectRootNotFoundError,
        ProjectRootNotDirectoryError,
        ProjectRootResolutionError,
    ) as error:
        return _render(path, error=str(error), status=400)
    # Le registre est hétérogène : on vérifie le résultat au point de consommation.
    if not isinstance(result, ProjectInspection):
        raise TypeError("project-inspector doit retourner ProjectInspection.")
    return _render(path, result=result)
