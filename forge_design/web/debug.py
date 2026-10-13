"""Page Debug Center, sans activation ni cache de projet."""

from collections.abc import Callable

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.checked_root import CheckedForgeRoot, check_forge_root
from forge_design.forge.debug_errors import DebugErrorsResult
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.runtime_diagnostics import (
    ForgeDiagnosticRun,
    run_forge_diagnostic,
)
from forge_design.limits import (
    FORGE_DIAGNOSTIC_TIMEOUT_SECONDS,
    MAX_FILTER_QUERY_LENGTH,
    MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_filters import (
    CATEGORIES,
    LEVELS,
    DebugFilter,
    filter_debug_events,
)
from forge_design.web.debug_detail import debug_event_url
from forge_design.web.debug_filters import parse_debug_filters
from forge_design.web.rendering import render_page
from forge_design.web.security import is_local_action

_PROJECT_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
)


def show_debug(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    """Journal runtime ; le GET n'exécute jamais le diagnostic Forge."""
    filters = DebugFilter()
    try:
        filters = parse_debug_filters(request)
    except ValueError as exc:
        return _render_debug(context, registry, filters, error=str(exc), status=400)
    return _render_debug(context, registry, filters)


def _render_debug(
    context: CurrentProjectContext,
    registry: ToolRegistry,
    filters: DebugFilter,
    *,
    error: str | None = None,
    status: int = 200,
    diagnostic: ForgeDiagnosticRun | None = None,
    diagnostic_error: str | None = None,
) -> Response:
    result = None
    if context.root is not None and error is None:
        try:
            result = registry.get("debug-center").run(context.root)
        except _PROJECT_ERRORS as exc:
            error, status = str(exc), 409 if status == 200 else status
        else:
            if not isinstance(result, DebugErrorsResult):
                raise TypeError("debug-center doit retourner DebugErrorsResult.")
    return render_page(
        "debug.html",
        {
            "active_page": "debug",
            "current_project": context.inspection,
            "result": result,
            "error": error,
            "filters": filters,
            "levels": LEVELS,
            "categories": CATEGORIES,
            "debug_event_url": debug_event_url,
            "query_limit": MAX_FILTER_QUERY_LENGTH,
            "view": filter_debug_events(result, filters)
            if result is not None
            else None,
            "diagnostic": diagnostic,
            "diagnostic_error": diagnostic_error,
            "diagnostic_limit_kib": MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES // 1024,
            "diagnostic_timeout": int(FORGE_DIAGNOSTIC_TIMEOUT_SECONDS),
        },
        status=status,
    )


def run_forge_diagnostic_action(
    request: Request,
    context: CurrentProjectContext,
    registry: ToolRegistry,
    *,
    runner: Callable[[CheckedForgeRoot], ForgeDiagnosticRun] | None = None,
) -> Response:
    """POST explicite : exécuter une fois le diagnostic officiel du projet courant.

    Aucun champ, aucun paramètre : la commande, l'interpréteur, le dossier et
    l'environnement sont fixés par Forge Design ; la racine vient du contexte.
    Rendu direct, sans persistance ni redirection.
    """
    filters = DebugFilter()

    def refused(message: str, status: int) -> Response:
        return _render_debug(
            context, registry, filters, diagnostic_error=message, status=status
        )

    if not is_local_action(request):
        return refused("Origine de la requête non autorisée.", 403)
    content_type = request.header("Content-Type", "").split(";", 1)[0]
    if content_type != "application/x-www-form-urlencoded":
        return refused("Format de formulaire non pris en charge.", 415)
    if request.params or getattr(request, "body", None):
        return refused("Ce formulaire n’accepte aucun paramètre.", 400)
    if context.root is None:
        return refused("Aucun projet sélectionné : diagnostic non lancé.", 409)
    try:
        checked = check_forge_root(context.root)
    except _PROJECT_ERRORS as exc:
        return refused(f"Diagnostic non lancé : {exc}", 409)
    run = (runner or run_forge_diagnostic)(checked)
    return _render_debug(context, registry, filters, diagnostic=run)
