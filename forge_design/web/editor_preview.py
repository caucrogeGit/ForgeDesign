"""Document de prévisualisation encadré par l'éditeur, en lecture seule.

Réutilise exclusivement generate_preview_data et render_preview : aucun second
renderer, aucun Jinja cible, aucun backend Forge. La réponse porte sa propre
politique, plus stricte que la politique Forge par défaut, sauf sur un point :
l'encadrement en même origine, nécessaire à l'iframe de l'éditeur.
"""

import re

from core.http.request import Request
from core.http.response import Response
from markupsafe import Markup

from forge_design.current_project import CurrentProjectContext
from forge_design.limits import MAX_SOURCE_PATH_LENGTH
from forge_design.preview import (
    PREVIEW_VIEWPORTS,
    generate_preview_data,
    render_preview,
)
from forge_design.web.editor import (
    PREVIEW_MODE_LABELS,
    EditorHttpError,
    load_contract,
    load_design,
    parse_preview_mode,
)
from forge_design.web.rendering import render_page

_LOCAL_HOST = re.compile(r"127\.0\.0\.1:[0-9]{1,5}")


def preview_frame_policy(host: str) -> str:
    """CSP du document encadré : rien d'actif, encadrable par l'éditeur seul.

    Dans une iframe sandbox sans allow-same-origin, l'origine du document est
    opaque : l'origine locale exacte est ajoutée à style-src pour que la feuille
    de style se charge quelle que soit l'interprétation de 'self'.
    """
    style = "'self'" + (f" http://{host}" if _LOCAL_HOST.fullmatch(host) else "")
    return (
        "default-src 'none'; "
        f"style-src {style}; "
        "img-src 'self' data:; "
        "frame-ancestors 'self'; "
        "base-uri 'none'; "
        "form-action 'none'"
    )


def _frame(
    request: Request, context: CurrentProjectContext, **page: object
) -> Response:
    status = page.pop("status", 200)
    assert isinstance(status, int)
    response = render_page(
        "preview_frame.html",
        {
            "html": None,
            "error": None,
            "data_issues": (),
            "render_issues": (),
            "data_complete": True,
            "render_complete": True,
            "mode": None,
            "mode_label": None,
            "width_px": None,
            "current_project": context.inspection,
            **page,
        },
        status=status,
    )
    # Définis ici, ces en-têtes priment sur les défauts Forge (setdefault).
    response.headers["Content-Security-Policy"] = preview_frame_policy(
        request.header("Host", "")
    )
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


def show_editor_preview(request: Request, context: CurrentProjectContext) -> Response:
    if context.root is None:
        return _frame(request, context, error="Aucun projet ouvert.", status=409)
    params = request.params
    if (
        not set(params) <= {"design", "mode"}
        or "design" not in params
        or any(len(values) != 1 for values in params.values())
    ):
        return _frame(
            request,
            context,
            error="Paramètres de prévisualisation invalides.",
            status=400,
        )
    design_path = request.query("design", "")
    if len(design_path) > MAX_SOURCE_PATH_LENGTH:
        return _frame(request, context, error="Chemin de Design refusé.", status=400)
    try:
        mode = parse_preview_mode(request.query("mode"))
    except ValueError as error:
        return _frame(request, context, error=str(error), status=400)
    labels = dict(PREVIEW_MODE_LABELS)
    page: dict[str, object] = {
        "mode": mode,
        "mode_label": labels[mode],
        "width_px": PREVIEW_VIEWPORTS[mode].width_px,
    }
    try:
        read = load_design(context, design_path)
    except EditorHttpError as error:
        return _frame(
            request, context, error=error.message, status=error.status, **page
        )
    design = read.design
    if design is None:
        return _frame(
            request,
            context,
            error="Prévisualisation indisponible : Design invalide.",
            **page,
        )
    contract = load_contract(context, design).contract
    if contract is None:
        return _frame(
            request,
            context,
            error="Prévisualisation indisponible : contrat absent ou invalide.",
            **page,
        )
    data = generate_preview_data(contract)
    rendered = render_preview(design, data.data)
    return _frame(
        request,
        context,
        # Seule chaîne marquée sûre : la sortie du renderer interne, qui échappe
        # valeurs, libellés et classes et n'émet que des balises en liste blanche.
        html=Markup(rendered.html),
        data_issues=data.issues,
        render_issues=rendered.issues,
        data_complete=data.complete,
        render_complete=rendered.complete,
        **page,
    )
