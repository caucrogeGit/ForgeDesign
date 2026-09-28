"""Vue source en lecture seule, indépendante de Route Explorer."""

from urllib.parse import urlencode

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.source import (
    SourceLocation,
    SourceReadError,
    read_project_source,
    source_parts,
)
from forge_design.web.rendering import render_page


def source_url(source: SourceLocation | str) -> str:
    if isinstance(source, str):
        source = SourceLocation(source)
    params = {"path": source.path}
    if source.line is not None:
        params["line"] = str(source.line)
    return "/source?" + urlencode(params)


def source_available(source: SourceLocation | None) -> bool:
    """Autorisation lexicale seulement ; le fichier sera vérifié à l'ouverture."""
    if source is None:
        return False
    try:
        source_parts(source.path)
    except SourceReadError:
        return False
    return True


def show_source(request: Request, context: CurrentProjectContext) -> Response:
    path = request.query("path", "")
    requested_line = request.query("line")
    line: int | None = None
    error = None
    message = None
    status = 200
    rows: list[tuple[int, str]] = []
    active_page = None
    if context.root is None:
        error, status = "Aucun projet ouvert.", 409
    elif requested_line is not None and (
        not requested_line.isascii()
        or not requested_line.isdigit()
        or len(requested_line) > 9
        or int(requested_line) < 1
    ):
        error, status = "Numéro de ligne invalide.", 400
    else:
        line = int(requested_line) if requested_line is not None else None
        try:
            parts = source_parts(path)
            active_page = "entities" if parts[1] == "entities" else "routes"
            content = read_project_source(context.root, path)
            lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            if len(lines) > 1 and lines[-1] == "":
                lines.pop()
            if line is not None and line > len(lines):
                message = "La ligne demandée n’est plus disponible."
            if line is not None and line <= len(lines):
                start, end = max(1, line - 20), min(len(lines), line + 20)
            else:
                start, end = 1, len(lines)
            rows = [(number, lines[number - 1]) for number in range(start, end + 1)]
        except FileNotFoundError:
            error, status = "Source introuvable.", 404
        except SourceReadError as exc:
            error, status = str(exc), 400
    return render_page(
        "source.html",
        {
            "active_page": active_page,
            "current_project": context.inspection,
            "path": path,
            "line": line,
            "rows": rows,
            "error": error,
            "message": message,
        },
        status=status,
    )
