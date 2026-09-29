"""Inventaire et lecture brute des templates, sans état ni rendu cible."""

from datetime import UTC, datetime
from urllib.parse import urlencode

from core.http.request import Request
from core.http.response import Response

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceReadError, source_parts
from forge_design.forge.template_structure import analyze_template_structure
from forge_design.forge.templates import TemplatesResult, read_template_source
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.template_navigation import resolve_template_references
from forge_design.tools.template_tree import build_template_tree, flatten_template_tree
from forge_design.web.rendering import render_page

_PROJECT_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
)


def template_url(path: str) -> str:
    return "/templates/view?" + urlencode({"path": path})


def template_tree_url(path: str) -> str:
    return "/templates/tree?" + urlencode({"path": path})


def modified_date(modified_ns: int) -> str:
    try:
        return datetime.fromtimestamp(modified_ns // 1_000_000_000, UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except (ValueError, OverflowError, OSError):
        return "Date hors plage"


def parse_template_path(request: Request) -> str:
    if set(request.params) != {"path"} or len(request.params["path"]) != 1:
        raise ValueError("Un unique paramètre path non vide est requis.")
    path = request.query("path", "")
    source_parts("mvc/views/" + path)
    return path


def show_templates(
    request: Request, context: CurrentProjectContext, registry: ToolRegistry
) -> Response:
    result = None
    error = None
    status = 200
    if context.root is not None:
        try:
            result = registry.get("template-viewer").run(context.root)
        except _PROJECT_ERRORS as exc:
            error, status = str(exc), 409
        else:
            if not isinstance(result, TemplatesResult):
                raise TypeError("template-viewer doit retourner TemplatesResult.")
    return render_page(
        "templates.html",
        {
            "active_page": "templates",
            "current_project": context.inspection,
            "result": result,
            "error": error,
            "template_url": template_url,
            "modified_date": modified_date,
        },
        status=status,
    )


def show_template(request: Request, context: CurrentProjectContext) -> Response:
    return _show_detail(request, context, tree_view=False)


def show_template_tree(request: Request, context: CurrentProjectContext) -> Response:
    return _show_detail(request, context, tree_view=True)


def _show_detail(
    request: Request, context: CurrentProjectContext, *, tree_view: bool
) -> Response:
    source = None
    error = None
    status = 200
    try:
        path = parse_template_path(request)
    except ValueError as exc:
        error, status = str(exc), 400
    else:
        if context.root is None:
            error, status = "Aucun projet ouvert.", 409
        else:
            try:
                source = read_template_source(context.root, path)
            except _PROJECT_ERRORS as exc:
                error, status = str(exc), 409
            except FileNotFoundError:
                error, status = "Template absent.", 404
            except SourceReadError as exc:
                error, status = str(exc), 409
    structure = analyze_template_structure(source.text) if source is not None else None
    tree = (
        build_template_tree(structure) if tree_view and structure is not None else None
    )
    return render_page(
        "template_tree.html" if tree_view else "template_view.html",
        {
            "active_page": "templates",
            "current_project": context.inspection,
            "source": source,
            "structure": structure,
            "tree": tree,
            "navigation": resolve_template_references(
                context.root, structure.dependencies
            )
            if context.root is not None and structure is not None
            else (),
            "navigation_labels": {
                "available": "Local",
                "dynamic": "Non résolue statiquement",
                "invalid-path": "Chemin refusé",
                "missing": "Non disponible dans mvc/views/",
                "unreadable": "Source locale inaccessible",
            },
            "tree_rows": flatten_template_tree(tree) if tree is not None else (),
            "template_url": template_url,
            "template_tree_url": template_tree_url,
            "error": error,
            "modified_date": modified_date,
        },
        status=status,
    )
