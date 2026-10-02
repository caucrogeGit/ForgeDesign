"""Éditeur Web de .design.json : HTTP, lecture, appels editor/*, sauvegarde.

Sans état serveur : chaque requête relit le Design et son contrat. Chaque
action réussie est sauvegardée aussitôt par write_design avec la révision lue,
puis redirigée (POST/Redirect/GET). Aucune règle d'édition n'est codée ici.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any, cast
from urllib.parse import urlencode

from core.http.request import Request
from core.http.response import Response
from pydantic import ValidationError

from forge_design.contracts.models import ViewContract
from forge_design.contracts.reader import read_view_contract
from forge_design.current_project import CurrentProjectContext
from forge_design.design.io import (
    DesignReadResult,
    DesignWriteConflictError,
    DesignWriteError,
    InvalidDesignForWriteError,
    design_source,
    read_design,
    write_design,
)
from forge_design.design.models import (
    DesignFile,
    DesignNode,
    DesignNodeType,
    PageRoot,
    PropValue,
    TableColumn,
)
from forge_design.design.nesting import ALLOWED_CHILDREN, can_contain
from forge_design.editor import (
    DesignEditResult,
    NodePath,
    append_design_block,
    move_design_block,
    remove_design_block,
    set_design_binding,
    set_design_props,
    set_design_visibility,
    set_table_columns,
)
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceReadError
from forge_design.json_strict import loads_strict_json
from forge_design.limits import (
    MAX_DESIGN_DEPTH,
    MAX_DESIGN_NODES,
    MAX_SOURCE_PATH_LENGTH,
)
from forge_design.web.rendering import render_page
from forge_design.web.security import is_local_action
from forge_design.web.tailwind_classes import (
    CLASS_KEY,
    SUGGESTIONS,
    ClassNotEditableError,
    Props,
    add_class,
    current_classes,
    parse_class_tokens,
    remove_class,
    set_classes,
)

# Champs de formulaire locaux : bien en deçà de la limite de corps Forge (1 Mo).
MAX_EDITOR_FIELD_CHARS = 64 * 1024

_PROJECT_ERRORS = (
    ProjectRootNotFoundError,
    ProjectRootNotDirectoryError,
    ProjectRootResolutionError,
    NotForgeProjectError,
)
_FORM = "application/x-www-form-urlencoded"
# Une action = un ensemble exact de champs : jamais plusieurs propriétés à la fois.
_ACTION_FIELDS: Mapping[str, frozenset[str]] = {
    "append": frozenset({"action", "design", "parent", "block_type"}),
    "remove": frozenset({"action", "design", "path"}),
    "move": frozenset({"action", "design", "path", "destination"}),
    "binding": frozenset({"action", "design", "path", "binding"}),
    "visibility": frozenset({"action", "design", "path", "visible_if"}),
    "props": frozenset({"action", "design", "path", "props"}),
    "columns": frozenset({"action", "design", "path", "columns"}),
    "tailwind_set": frozenset({"action", "design", "path", "classes"}),
    "tailwind_add": frozenset({"action", "design", "path", "class_token"}),
    "tailwind_remove": frozenset({"action", "design", "path", "class_token"}),
}
_CONTRACT_ACTIONS = frozenset({"binding", "visibility", "columns"})
_NOTICES = {
    "saved": "Modification enregistrée.",
    "noop": "Aucune modification.",
}


class _HttpError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class EditorNodeView:
    path: NodePath
    path_value: str
    depth: int
    type: DesignNodeType
    binding: str | None
    visible_if: str | None
    props: tuple[tuple[str, PropValue], ...]
    columns: tuple[tuple[str, str], ...] | None
    child_count: int
    # Rendu en listes imbriquées sans récursion Jinja ni style inline (CSP).
    opens: bool = False
    close_levels: int = 0


@dataclass(frozen=True)
class ContractState:
    path: str
    contract: ViewContract | None
    messages: tuple[str, ...]


def format_node_path(path: NodePath) -> str:
    """() → "", (0,) → "0", (0, 2) → "0.2"."""
    return ".".join(str(index) for index in path)


def parse_node_path(value: str) -> NodePath:
    """Forme canonique stricte : entiers décimaux sans zéro initial, séparés par "."."""
    if value == "":
        return ()
    if len(value) > MAX_SOURCE_PATH_LENGTH:
        raise ValueError("Chemin de bloc trop long.")
    parts = value.split(".")
    if len(parts) > MAX_DESIGN_DEPTH:
        raise ValueError("Chemin de bloc trop profond.")
    for part in parts:
        if (
            not part.isascii()
            or not part.isdigit()
            or (len(part) > 1 and part[0] == "0")
        ):
            raise ValueError("Chemin de bloc non canonique.")
    return tuple(int(part) for part in parts)


def editor_url(design: str, node: NodePath = (), notice: str | None = None) -> str:
    params = {"design": design}
    if node:
        params["node"] = format_node_path(node)
    if notice is not None:
        params["notice"] = notice
    return "/editor?" + urlencode(params)


def _project_tree(design: DesignFile) -> tuple[tuple[EditorNodeView, ...], bool]:
    """Projection plate en ordre préfixe, bornée par MAX_DESIGN_NODES."""
    rows: list[EditorNodeView] = []
    stack: list[tuple[DesignNode | PageRoot, NodePath]] = [(design.root, ())]
    while stack:
        if len(rows) >= MAX_DESIGN_NODES:
            return _nest(rows), True
        node, path = stack.pop()
        children = node.children or []
        rows.append(
            EditorNodeView(
                path,
                format_node_path(path),
                len(path),
                node.type,
                node.binding,
                node.visible_if,
                tuple((node.props or {}).items()),
                None
                if node.columns is None
                else tuple((column.label, column.binding) for column in node.columns),
                len(children),
            )
        )
        if len(path) < MAX_DESIGN_DEPTH:
            stack.extend(
                (child, (*path, index))
                for index, child in reversed(list(enumerate(children)))
            )
    return _nest(rows), False


def _nest(rows: list[EditorNodeView]) -> tuple[EditorNodeView, ...]:
    """Ouvrir une liste si le suivant est un enfant, sinon fermer jusqu'à son niveau."""
    nested: list[EditorNodeView] = []
    for index, row in enumerate(rows):
        next_depth = rows[index + 1].depth if index + 1 < len(rows) else 0
        opens = next_depth > row.depth
        close = 0 if opens else row.depth - next_depth
        nested.append(replace(row, opens=opens, close_levels=close))
    return tuple(nested)


def _read_contract(context: CurrentProjectContext, design: DesignFile) -> ContractState:
    path = design.source_contract
    assert context.root is not None
    try:
        result = read_view_contract(context.root, path)
    except FileNotFoundError:
        return ContractState(path, None, ("Contrat introuvable.",))
    except SourceReadError:
        return ContractState(path, None, ("Chemin de contrat refusé.",))
    if result.contract is None:
        return ContractState(
            path,
            None,
            tuple(issue.message for issue in result.issues) or ("Contrat invalide.",),
        )
    return ContractState(path, result.contract, ())


def _read(context: CurrentProjectContext, design_path: str) -> DesignReadResult:
    if context.root is None:
        raise _HttpError(409, "Aucun projet ouvert.")
    if len(design_path) > MAX_SOURCE_PATH_LENGTH or design_source(design_path) is None:
        raise _HttpError(400, "Chemin de Design refusé.")
    try:
        return read_design(context.root, design_path)
    except FileNotFoundError:
        raise _HttpError(404, "Design introuvable.") from None
    except SourceReadError:
        raise _HttpError(400, "Chemin de Design refusé.") from None
    except _PROJECT_ERRORS:
        raise _HttpError(409, "Projet courant indisponible.") from None


def _find(rows: tuple[EditorNodeView, ...], path: NodePath) -> EditorNodeView | None:
    return next((row for row in rows if row.path == path), None)


def _render(
    context: CurrentProjectContext,
    *,
    design_path: str | None = None,
    read: DesignReadResult | None = None,
    selected_path: NodePath = (),
    error: str | None = None,
    issues: tuple[str, ...] = (),
    message: str | None = None,
    status: int = 200,
) -> Response:
    page: dict[str, object] = {
        "active_page": "editor",
        "editor_url": editor_url,
        "current_project": context.inspection,
        "design_path": design_path,
        "error": error,
        "issues": issues,
        "message": message,
        "read_issues": (),
        "rows": (),
        "truncated": False,
        "selected": None,
        "contract_state": None,
    }
    if read is not None:
        page["read_issues"] = tuple(issue.message for issue in read.issues)
    design = read.design if read is not None else None
    if design is not None and context.root is not None:
        rows, truncated = _project_tree(design)
        selected = _find(rows, selected_path) or _find(rows, ())
        state = _read_contract(context, design)
        page.update(
            {
                "rows": rows,
                "truncated": truncated,
                "selected": selected,
                "contract_state": state,
                "editable": not read.issues if read is not None else False,
            }
        )
        if selected is not None:
            page.update(_selection_context(rows, selected, state.contract))
    return render_page("editor.html", page, status=status)


def _selection_context(
    rows: tuple[EditorNodeView, ...],
    selected: EditorNodeView,
    contract: ViewContract | None,
) -> dict[str, object]:
    path = selected.path
    allowed = ALLOWED_CHILDREN[selected.type]
    destinations = (
        ()
        if not path
        else tuple(
            row
            for row in rows
            if row.path[: len(path)] != path and can_contain(row.type, selected.type)
        )
    )
    variables: tuple[tuple[str, str], ...] = ()
    booleans: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    if contract is not None:
        variables = tuple(
            (name, variable.type) for name, variable in sorted(contract.context.items())
        )
        booleans = tuple(name for name, kind in variables if kind == "boolean")
        actions = tuple(sorted(contract.actions or {}))
    props = dict(selected.props)
    try:
        classes = current_classes(props)
        class_editable = True
    except ClassNotEditableError:
        classes, class_editable = None, False
    columns = (
        None
        if selected.columns is None
        else [
            {"label": label, "binding": binding} for label, binding in selected.columns
        ]
    )
    return {
        "child_types": tuple(sorted(allowed)),
        "destinations": destinations,
        "variables": variables,
        "booleans": booleans,
        "actions": actions,
        "props_json": json.dumps(props, ensure_ascii=False) if selected.props else "",
        "class_editable": class_editable,
        "classes_value": classes or "",
        "class_tokens": parse_class_tokens(classes or "") if class_editable else (),
        "class_raw": json.dumps(props.get(CLASS_KEY), ensure_ascii=False),
        "tailwind_suggestions": SUGGESTIONS,
        "columns_json": ""
        if columns is None
        else json.dumps(columns, ensure_ascii=False, indent=2),
    }


def show_editor(request: Request, context: CurrentProjectContext) -> Response:
    if context.root is None:
        return _render(context, error="Aucun projet ouvert.", status=409)
    params = request.params
    if not set(params) <= {"design", "node", "notice"} or any(
        len(values) != 1 for values in params.values()
    ):
        return _render(context, error="Paramètres de l'éditeur invalides.", status=400)
    design_path = request.query("design")
    if design_path is None:
        return _render(context)
    notice = request.query("notice")
    if notice is not None and notice not in _NOTICES:
        return _render(context, error="Paramètres de l'éditeur invalides.", status=400)
    try:
        node = parse_node_path(request.query("node", ""))
    except ValueError as error:
        return _render(context, design_path=design_path, error=str(error), status=400)
    try:
        read = _read(context, design_path)
    except _HttpError as error:
        return _render(
            context, design_path=design_path, error=error.message, status=error.status
        )
    if read.design is not None:
        rows, _ = _project_tree(read.design)
        if _find(rows, node) is None:
            return _render(
                context,
                design_path=design_path,
                read=read,
                error="Aucun bloc à cet emplacement.",
                status=400,
            )
    return _render(
        context,
        design_path=design_path,
        read=read,
        selected_path=node,
        message=_NOTICES.get(notice or ""),
    )


def _fields(request: Request) -> dict[str, str]:
    body: Mapping[str, list[str]] = request.body
    if any(len(values) != 1 for values in body.values()):
        raise _HttpError(400, "Chaque champ doit être fourni une seule fois.")
    fields = {key: values[0] for key, values in body.items()}
    if any(
        len(key) > MAX_EDITOR_FIELD_CHARS or len(value) > MAX_EDITOR_FIELD_CHARS
        for key, value in fields.items()
    ):
        raise _HttpError(400, "Champ de formulaire trop long.")
    return fields


def _check_post(request: Request, context: CurrentProjectContext) -> None:
    if not is_local_action(request):
        raise _HttpError(403, "Origine de la requête non autorisée.")
    if request.header("Content-Type", "").split(";", 1)[0] != _FORM:
        raise _HttpError(415, "Format de formulaire non pris en charge.")
    if context.root is None:
        raise _HttpError(409, "Aucun projet ouvert.")


def _path(fields: Mapping[str, str], key: str) -> NodePath:
    try:
        return parse_node_path(fields[key])
    except ValueError as error:
        raise _HttpError(400, str(error)) from None


def _optional(fields: Mapping[str, str], key: str) -> str | None:
    value = fields[key]
    return None if value == "" else value


def _props(text: str) -> dict[str, Any] | None:
    if text == "":
        return None
    try:
        value = loads_strict_json(text)
    except (ValueError, RecursionError):
        raise _HttpError(400, "Props : JSON invalide.") from None
    if not isinstance(value, dict):
        raise _HttpError(400, "Props : un objet JSON est attendu.")
    return value  # pyright: ignore[reportUnknownVariableType]


def _columns(text: str) -> list[TableColumn] | None:
    if text == "":
        return None
    try:
        value = loads_strict_json(text)
    except (ValueError, RecursionError):
        raise _HttpError(400, "Colonnes : JSON invalide.") from None
    if not isinstance(value, list):
        raise _HttpError(400, "Colonnes : un tableau JSON est attendu.")
    items: list[object] = value  # pyright: ignore[reportUnknownVariableType]
    try:
        return [TableColumn.model_validate(item) for item in items]
    except ValidationError:
        raise _HttpError(
            400, "Colonnes : chaque élément doit avoir label et binding."
        ) from None


def _node_props(design: DesignFile, path: NodePath) -> tuple[bool, Props | None]:
    """Props réelles (None si absentes, distinct de {}) ; False si introuvable."""
    node: DesignNode | PageRoot = design.root
    for index in path:
        children = node.children or []
        if not 0 <= index < len(children):
            return False, None
        node = children[index]
    return True, node.props


def _tailwind(
    action: str, fields: Mapping[str, str], design: DesignFile
) -> DesignEditResult:
    """Nouvelles props où seule "class" change ; set_design_props reste l'autorité."""
    path = _path(fields, "path")
    found, props = _node_props(design, path)
    if not found:
        # Chemin refusé par l'éditeur lui-même (editor.path_not_found).
        return set_design_props(design, path=path, props=None)
    try:
        if action == "tailwind_set":
            updated = set_classes(props, fields["classes"])
        elif action == "tailwind_add":
            updated = add_class(props, fields["class_token"])
        else:
            updated = remove_class(props, fields["class_token"])
    except ClassNotEditableError:
        raise _HttpError(
            422, "props.class n'est pas une chaîne : corrigez-la via le JSON des props."
        ) from None
    except ValueError as error:
        raise _HttpError(400, "Classes : " + str(error)) from None
    return set_design_props(design, path=path, props=updated)


def _apply(
    action: str,
    fields: Mapping[str, str],
    design: DesignFile,
    contract: ViewContract | None,
) -> DesignEditResult:
    """Traduire une action HTTP en un unique appel de l'API editor."""
    operations: dict[str, Callable[[], DesignEditResult]] = {
        "append": lambda: append_design_block(
            design,
            parent=_path(fields, "parent"),
            # Valeur HTTP brute : append_design_block refuse tout type inconnu.
            block_type=cast(DesignNodeType, fields["block_type"]),
        ),
        "remove": lambda: remove_design_block(design, path=_path(fields, "path")),
        "move": lambda: move_design_block(
            design,
            source=_path(fields, "path"),
            destination=_path(fields, "destination"),
        ),
        "props": lambda: set_design_props(
            design, path=_path(fields, "path"), props=_props(fields["props"])
        ),
        "tailwind_set": lambda: _tailwind(action, fields, design),
        "tailwind_add": lambda: _tailwind(action, fields, design),
        "tailwind_remove": lambda: _tailwind(action, fields, design),
    }
    if contract is not None:
        operations |= {
            "binding": lambda: set_design_binding(
                design,
                path=_path(fields, "path"),
                binding=_optional(fields, "binding"),
                contract=contract,
            ),
            "visibility": lambda: set_design_visibility(
                design,
                path=_path(fields, "path"),
                visible_if=_optional(fields, "visible_if"),
                contract=contract,
            ),
            "columns": lambda: set_table_columns(
                design,
                path=_path(fields, "path"),
                columns=_columns(fields["columns"]),
                contract=contract,
            ),
        }
    return operations[action]()


def _redirect(url: str) -> Response:
    return Response(303, b"", headers={"Location": url})


def _save(
    context: CurrentProjectContext,
    design_path: str,
    read: DesignReadResult,
    design: DesignFile,
    selected: NodePath,
) -> Response:
    """write_design avec la révision lue ; conflit et échec restent explicites."""
    assert context.root is not None
    try:
        write_design(context.root, design_path, design, expected_revision=read.revision)
    except DesignWriteConflictError:
        return _render(
            context,
            design_path=design_path,
            read=read,
            selected_path=selected,
            error=(
                "Le Design a été modifié depuis sa lecture. "
                "Rechargez la page avant de recommencer."
            ),
            status=409,
        )
    except InvalidDesignForWriteError as error:
        return _render(
            context,
            design_path=design_path,
            read=read,
            selected_path=selected,
            error="Design refusé à l'écriture : défaut interne de l'éditeur.",
            issues=tuple(issue.message for issue in error.issues),
            status=422,
        )
    except DesignWriteError:
        # write_design ne garantit pas l'absence de publication : relire.
        return _render(
            context,
            design_path=design_path,
            selected_path=selected,
            error="Sauvegarde incertaine : relisez le Design avant de réessayer.",
            status=500,
        )
    except _PROJECT_ERRORS:
        return _render(context, error="Projet courant indisponible.", status=409)
    return _redirect(editor_url(design_path, selected, "saved"))


def editor_action(request: Request, context: CurrentProjectContext) -> Response:
    design_path: str | None = None
    read: DesignReadResult | None = None
    try:
        _check_post(request, context)
        fields = _fields(request)
        action = fields.get("action", "")
        expected = _ACTION_FIELDS.get(action)
        if expected is None or frozenset(fields) != expected:
            raise _HttpError(400, "Une seule action complète est attendue.")
        design_path = fields["design"]
        read = _read(context, design_path)
        design = read.design
        if design is None:
            raise _HttpError(409, "Design illisible ou invalide : édition impossible.")
        contract = None
        if action in _CONTRACT_ACTIONS:
            contract = _read_contract(context, design).contract
            if contract is None:
                raise _HttpError(409, "Contrat indisponible : action impossible.")
        result = _apply(action, fields, design, contract)
    except _HttpError as error:
        return _render(
            context,
            design_path=design_path,
            read=read,
            error=error.message,
            status=error.status,
        )
    target = fields.get("parent") or fields.get("path") or ""
    selected = (
        parse_node_path(target)
        if result.affected_path is None
        else result.affected_path
    )
    if result.issues:
        return _render(
            context,
            design_path=design_path,
            read=read,
            selected_path=selected,
            error="Modification refusée.",
            issues=tuple(issue.message for issue in result.issues),
            status=422,
        )
    if not result.changed:
        return _redirect(editor_url(design_path, selected, "noop"))
    return _save(context, design_path, read, result.design, selected)
