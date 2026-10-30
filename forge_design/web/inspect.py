"""Mode analyse : page, actions et traces (FD-INSPECT-001, étape 2).

Même RealPreviewRuntime que la preview réelle, démarré avec inspect=True :
l'application tourne avec les sondes de child_inspect.py et le proxy injecte
le script d'inspection dans ses pages. Aucune sélection de route : la page
part de / et l'on navigue partout.

Base d'analyse (étape 3) : un projet qui a une base (DB_NAME) ne démarre
qu'avec sa copie jetable, recopiée au premier lancement puis à la demande.

La page reçoit, par postMessage depuis l'origine du proxy, un identifiant de
trace ; elle demande la trace à GET /inspect/trace, que le serveur lit
auprès de l'enfant. La trace vient du code du projet : elle n'est affichée
qu'en texte, et les seuls liens sont des URL de Forge Design construites ici.
"""

from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlencode

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.real_preview import RealPreviewError
from forge_design.real_preview.analysis_database import (
    AnalysisDatabase,
    check_analysis_database,
    copy_analysis_database,
    creation_sql,
)
from forge_design.web.editor import (
    EditorHttpError,
    check_editor_post,
    editor_form_fields,
    editor_frame_policy,
)
from forge_design.web.real_preview import (
    REAL_PREVIEW_WARNING,
    STATE_LABELS,
    RealPreviewRuntime,
)
from forge_design.web.rendering import render_page

INSPECT_PAGE = "/inspect"
_VIEWS_PREFIX = "mvc/views/"


def _source_url(path: str, line: object = None) -> str:
    query: dict[str, str] = {"path": path}
    if isinstance(line, int) and not isinstance(line, bool) and line > 0:
        query["line"] = str(line)
    return f"/source?{urlencode(query)}"


def _relative_file(value: object) -> str | None:
    """Chemin relatif simple, sinon None : jamais d'URL ni de chemin absolu."""
    if not isinstance(value, str) or not value or len(value) > 1024:
        return None
    if value.startswith("/") or "\\" in value or "\0" in value:
        return None
    if any(part in ("", ".", "..") for part in value.split("/")):
        return None
    return value


def _mapping(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def trace_links(trace: object) -> dict[str, Any]:
    """Liens de Forge Design pour une trace : handler et templates."""
    templates_links: dict[str, str] = {}
    links: dict[str, Any] = {"handler": None, "templates": templates_links}
    data = _mapping(trace)
    if data is None:
        return links
    handler = _mapping(data.get("handler"))
    if handler is not None:
        file = _relative_file(handler.get("file"))
        if file is not None:
            links["handler"] = _source_url(file, handler.get("line"))
    templates = data.get("templates")
    for item in cast("list[object]", templates) if isinstance(templates, list) else []:
        template = _mapping(item)
        if template is None:
            continue
        file = _relative_file(template.get("file"))
        identifier = template.get("id")
        if file is None or not isinstance(identifier, int):
            continue
        if file.startswith(_VIEWS_PREFIX):
            view = file[len(_VIEWS_PREFIX) :]
            url = f"/templates/view?{urlencode({'path': view})}"
        else:
            url = _source_url(file)
        templates_links[str(identifier)] = url
    return links


def render_inspect(
    context: CurrentProjectContext,
    runtime: RealPreviewRuntime,
    *,
    error: str | None = None,
    error_sql: str | None = None,
    notice: str | None = None,
    status: int = 200,
) -> Response:
    """Page du mode analyse ; frame-src élargi au seul proxy actif."""
    current = runtime.status()
    same = current.project_root is not None and current.project_root == context.root
    active = same and current.inspect
    state = current.state if active else "stopped"
    origin = current.proxy_origin if active and state == "running" else None
    response = render_page(
        "inspect.html",
        {
            "active_page": "inspect",
            "current_project": context.inspection,
            "enabled": runtime.enabled and context.root is not None,
            "state": state,
            "state_label": STATE_LABELS[state],
            "run_error": current.error if active else None,
            "logs": current.logs if active and state == "failed" else (),
            "proxy_origin": origin,
            "frame_url": f"{origin}/" if origin is not None else None,
            "can_start": runtime.enabled
            and context.root is not None
            and state in ("stopped", "failed"),
            "can_stop": state in ("running", "starting"),
            "can_copy": runtime.enabled and context.root is not None,
            "database": current.database if active else None,
            "warning": REAL_PREVIEW_WARNING,
            "error": error,
            "error_sql": error_sql,
            "notice": notice,
        },
        status=status,
    )
    if origin is not None:
        response.headers["Content-Security-Policy"] = editor_frame_policy(origin)
    return response


def show_inspect(
    request: Request, context: CurrentProjectContext, runtime: RealPreviewRuntime
) -> Response:
    """GET : état et cadre du mode analyse ; ne démarre jamais rien."""
    if request.params:
        return render_inspect(
            context, runtime, error="Paramètres invalides.", status=400
        )
    return render_inspect(context, runtime)


class _DatabaseError(EditorHttpError):
    def __init__(self, message: str, sql: str | None = None) -> None:
        super().__init__(409, message)
        self.sql = sql


def _database_error(database: AnalysisDatabase) -> _DatabaseError:
    if database.status == "missing":
        return _DatabaseError(
            f"La base d'analyse {database.target} n'existe pas sur le serveur. "
            "Le compte d'administration du projet ne peut pas la créer : "
            "un administrateur du serveur doit lancer ceci.",
            creation_sql(database),
        )
    if database.status == "none":
        return _DatabaseError("Le projet n'a pas de base (DB_NAME) : rien à recopier.")
    return _DatabaseError(f"Base d'analyse : {database.error or database.status}.")


def _analysis_database(root: Path) -> str | None:
    """Nom de la copie à imposer à l'enfant ; None si le projet n'a pas de base."""
    database = check_analysis_database(root)
    if database.status == "none":
        return None
    if database.status == "empty":
        database = copy_analysis_database(root)
    if database.status != "ready":
        raise _database_error(database)
    return database.target


def _start(root: Path, runtime: RealPreviewRuntime, database: str | None) -> None:
    try:
        runtime.start(root, inspect=True, database=database)
    except RealPreviewError as error:
        raise EditorHttpError(409, str(error)) from None


def _copy(root: Path, runtime: RealPreviewRuntime) -> str:
    """Arrêter l'analyse en cours, recopier, relancer ; message de réussite."""
    current = runtime.status()
    running = (
        current.inspect
        and current.project_root == root
        and current.state in ("running", "starting")
    )
    if running and not runtime.stop():
        raise EditorHttpError(500, "Analyse impossible à arrêter.")
    database = copy_analysis_database(root)
    if database.status != "ready":
        raise _database_error(database)
    if running:
        _start(root, runtime, database.target)
    rows = f"{database.rows or 0:,}".replace(",", "\u202f")
    seconds = ""
    if database.seconds is not None:
        seconds = f" en {database.seconds:.1f}".replace(".", ",") + "\u00a0s"
    return (
        f"Base {database.target} recopiée depuis {database.source} : "
        f"{database.tables} tables, {rows} lignes{seconds}."
    )


def inspect_action(
    request: Request,
    context: CurrentProjectContext,
    runtime: RealPreviewRuntime,
    *,
    action: Literal["start", "stop", "copy"],
) -> Response:
    """POST Start/Stop/Recopier, sans aucun champ."""
    try:
        check_editor_post(request, context)
        if editor_form_fields(request):
            raise EditorHttpError(400, "Champs de formulaire inattendus.")
        if action == "stop":
            if not runtime.stop():
                raise EditorHttpError(500, "Analyse impossible à arrêter.")
        else:
            assert context.root is not None
            if action == "copy":
                notice = _copy(context.root, runtime)
                return render_inspect(context, runtime, notice=notice)
            _start(context.root, runtime, _analysis_database(context.root))
    except EditorHttpError as error:
        sql = error.sql if isinstance(error, _DatabaseError) else None
        return render_inspect(
            context, runtime, error=error.message, error_sql=sql, status=error.status
        )
    return Response(303, b"", headers={"Location": INSPECT_PAGE})


def _json(payload: object, status: int = 200) -> Response:
    response = Response.json(payload, status=status)
    response.headers["Cache-Control"] = "no-store"
    return response


def inspect_trace(
    request: Request, context: CurrentProjectContext, runtime: RealPreviewRuntime
) -> Response:
    """GET /inspect/trace?id=<n> : trace de l'enfant et liens de Forge Design."""
    params = request.params
    if set(params) != {"id"} or len(params["id"]) != 1:
        return _json({"error": "Paramètre id attendu."}, 400)
    current = runtime.status()
    if context.root is None or current.project_root != context.root:
        return _json({"error": "Aucune analyse pour ce projet."}, 409)
    trace = runtime.fetch_trace(params["id"][0])
    if trace is None:
        return _json({"error": "Trace introuvable."}, 404)
    return _json({"trace": trace, "links": trace_links(trace)})
