"""Mode analyse : page, actions et traces (FD-INSPECT-001, étape 2).

Même RealPreviewRuntime que la preview réelle, démarré avec inspect=True :
l'application tourne avec les sondes de child_inspect.py et le proxy injecte
le script d'inspection dans ses pages. Aucune sélection de route : la page
part de / et l'on navigue partout.

La page reçoit, par postMessage depuis l'origine du proxy, un identifiant de
trace ; elle demande la trace à GET /inspect/trace, que le serveur lit
auprès de l'enfant. La trace vient du code du projet : elle n'est affichée
qu'en texte, et les seuls liens sont des URL de Forge Design construites ici.
"""

from typing import Any, cast
from urllib.parse import urlencode

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.real_preview import RealPreviewError
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
            "warning": REAL_PREVIEW_WARNING,
            "error": error,
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


def inspect_action(
    request: Request,
    context: CurrentProjectContext,
    runtime: RealPreviewRuntime,
    *,
    stop: bool,
) -> Response:
    """POST Start/Stop, sans aucun champ."""
    try:
        check_editor_post(request, context)
        if editor_form_fields(request):
            raise EditorHttpError(400, "Champs de formulaire inattendus.")
        if stop:
            if not runtime.stop():
                raise EditorHttpError(500, "Analyse impossible à arrêter.")
        else:
            assert context.root is not None
            try:
                runtime.start(context.root, inspect=True)
            except RealPreviewError as error:
                raise EditorHttpError(409, str(error)) from None
    except EditorHttpError as error:
        return render_inspect(
            context, runtime, error=error.message, status=error.status
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
