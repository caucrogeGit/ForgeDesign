"""Rendu des pages packagées avec le renderer public Forge."""

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from importlib.resources import as_file, files

from core.http.request import Request
from core.http.response import Response
from integrations.jinja2.renderer import (  # pyright: ignore[reportMissingTypeStubs]
    Jinja2Renderer,
)


@dataclass(frozen=True)
class ShellModules:
    """Ce que le shell affiche des modules de l'application (FD-MODULES-002)."""

    navigation: tuple[object, ...] = ()
    diagnostics: tuple[object, ...] = ()


# Valeur posée par l'application pendant une requête seulement (valeur par défaut :
# aucun module). Ce n'est pas un registre : chaque application pose la sienne.
_SHELL: ContextVar[ShellModules] = ContextVar(
    "forge_design_shell_modules", default=ShellModules()
)


def with_shell(
    handler: Callable[[Request], Response], shell: ShellModules
) -> Callable[[Request], Response]:
    """Exécuter un handler avec la zone Modules de son application."""

    def handle(request: Request) -> Response:
        token = _SHELL.set(shell)
        try:
            return handler(request)
        finally:
            _SHELL.reset(token)

    return handle


def render_page(
    template: str, context: dict[str, object], *, status: int = 200
) -> Response:
    """Rendre un nom de template interne, jamais un chemin fourni par HTTP."""
    shell = _SHELL.get()
    page = {
        "module_navigation": shell.navigation,
        "module_diagnostics": shell.diagnostics,
        **context,
    }
    with as_file(files("forge_design.web").joinpath("templates")) as templates:
        html = Jinja2Renderer(str(templates)).render(template, page)
    return Response.html(html, status=status)
