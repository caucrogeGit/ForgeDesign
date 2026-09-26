"""Rendu des pages packagées avec le renderer public Forge."""

from importlib.resources import as_file, files

from core.http.response import Response
from integrations.jinja2.renderer import (  # pyright: ignore[reportMissingTypeStubs]
    Jinja2Renderer,
)


def render_page(
    template: str, context: dict[str, object], *, status: int = 200
) -> Response:
    """Rendre un nom de template interne, jamais un chemin fourni par HTTP."""
    with as_file(files("forge_design.web").joinpath("templates")) as templates:
        html = Jinja2Renderer(str(templates)).render(template, context)
    return Response.html(html, status=status)
