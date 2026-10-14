"""Page Debug Center, sans activation ni cache de projet."""

from collections.abc import Callable
from typing import Literal

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
    run_forge_project_audit,
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
    audit: ForgeDiagnosticRun | None = None,
    audit_error: str | None = None,
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
            "audit": audit,
            "audit_error": audit_error,
            "diagnostic_limit_kib": MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES // 1024,
            "diagnostic_timeout": int(FORGE_DIAGNOSTIC_TIMEOUT_SECONDS),
        },
        status=status,
    )


Runner = Callable[[CheckedForgeRoot], ForgeDiagnosticRun]


def run_forge_diagnostic_action(
    request: Request,
    context: CurrentProjectContext,
    registry: ToolRegistry,
    *,
    runner: Runner | None = None,
) -> Response:
    """POST explicite : exécuter une fois ``forge doctor`` sur le projet courant."""
    return _forge_command_action(
        request, context, registry, "diagnostic", runner or run_forge_diagnostic
    )


def run_forge_audit_action(
    request: Request,
    context: CurrentProjectContext,
    registry: ToolRegistry,
    *,
    runner: Runner | None = None,
) -> Response:
    """POST explicite : exécuter une fois ``forge project:audit`` (FD-RUNTIME-002)."""
    return _forge_command_action(
        request, context, registry, "audit", runner or run_forge_project_audit
    )


def _forge_command_action(
    request: Request,
    context: CurrentProjectContext,
    registry: ToolRegistry,
    section: Literal["diagnostic", "audit"],
    runner: Runner,
) -> Response:
    """Gardes communes, puis une exécution ; résultat dans la seule section visée.

    Aucun champ, aucun paramètre : la commande, l'interpréteur, le dossier et
    l'environnement sont fixés par Forge Design ; la racine vient du contexte.
    Rendu direct, sans persistance ni redirection.
    """
    filters = DebugFilter()
    noun = "diagnostic" if section == "diagnostic" else "audit"

    def rendered(
        status: int = 200,
        error: str | None = None,
        run: ForgeDiagnosticRun | None = None,
    ) -> Response:
        if section == "diagnostic":
            return _render_debug(
                context,
                registry,
                filters,
                diagnostic=run,
                diagnostic_error=error,
                status=status,
            )
        return _render_debug(
            context, registry, filters, audit=run, audit_error=error, status=status
        )

    if not is_local_action(request):
        return rendered(403, "Origine de la requête non autorisée.")
    content_type = request.header("Content-Type", "").split(";", 1)[0]
    if content_type != "application/x-www-form-urlencoded":
        return rendered(415, "Format de formulaire non pris en charge.")
    if request.params or getattr(request, "body", None):
        return rendered(400, "Ce formulaire n’accepte aucun paramètre.")
    if context.root is None:
        return rendered(409, f"Aucun projet sélectionné : {noun} non lancé.")
    try:
        checked = check_forge_root(context.root)
    except _PROJECT_ERRORS as exc:
        return rendered(409, f"{noun.capitalize()} non lancé : {exc}")
    return rendered(run=runner(checked))
