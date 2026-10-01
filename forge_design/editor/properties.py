"""Configuration d'une propriété existante d'un bloc, en mémoire, sans I/O.

Une fonction par propriété ; None supprime la clé. Les règles contractuelles
viennent des validateurs de design/, appliqués au seul bloc édité : une erreur
préexistante ailleurs ne bloque pas une correction locale.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from pydantic import ValidationError

from forge_design.contracts.models import ViewContract
from forge_design.design.bindings import validate_design_bindings
from forge_design.design.conditional_bindings import validate_conditional_bindings
from forge_design.design.models import DesignFile, PropValue, TableColumn
from forge_design.design.table_bindings import validate_table_bindings
from forge_design.editor._tree import (
    DesignEditResult,
    NodePath,
    Refused,
    check_path,
    rebuilt,
    refusal,
    resolve,
    revalidated,
)
from forge_design.limits import MAX_TABLE_COLUMNS

_Check = Callable[[DesignFile, NodePath], None]


def _strict_equal(left: object, right: object) -> bool:
    """1, 1.0 et True sont égaux en Python, pas en JSON ; l'ordre des clés compte."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        left_items: list[tuple[Any, Any]] = list(left.items())  # pyright: ignore[reportUnknownArgumentType]
        right_items: list[tuple[Any, Any]] = list(right.items())  # pyright: ignore[reportUnknownArgumentType]
        return len(left_items) == len(right_items) and all(
            a == b and _strict_equal(x, y)
            for (a, x), (b, y) in zip(left_items, right_items, strict=True)
        )
    if isinstance(left, list) and isinstance(right, list):
        left_list: list[Any] = left  # pyright: ignore[reportUnknownVariableType]
        right_list: list[Any] = right  # pyright: ignore[reportUnknownVariableType]
        return len(left_list) == len(right_list) and all(
            _strict_equal(x, y) for x, y in zip(left_list, right_list, strict=True)
        )
    return left == right


def _contract(contract: object) -> ViewContract:
    """Revalider : les dictionnaires d'un contrat gelé restent mutables."""
    if not isinstance(contract, ViewContract):
        raise Refused("invalid_contract", "Un ViewContract est attendu.", ())
    try:
        data = contract.model_dump(exclude_unset=True, warnings=False)
        return ViewContract.model_validate(data)
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        raise Refused("invalid_contract", "Contrat non conforme.", ()) from error


def _text(value: object, code: str, label: str, path: NodePath) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise Refused(code, f"{label} doit être une chaîne non vide ou None.", path)
    # str.__str__ rend un str exact, même pour une sous-classe.
    return str.__str__(value)


def _projected(model: DesignFile, path: NodePath) -> DesignFile:
    """Design minimal portant le seul bloc édité, sans ses enfants.

    Les règles de binding, condition et colonnes ne dépendent que du bloc et du
    contrat : ni erreur ni troncature d'un autre bloc ne peut s'y mêler.
    """
    node: Any = model.root
    for index in path:
        node = node.children[index]
    isolated: dict[str, Any] = node.model_dump(exclude_unset=True, exclude={"children"})
    root: dict[str, Any] = (
        {**isolated, "children": []}
        if not path
        else {
            "type": "page",
            "children": [isolated],
        }
    )
    data = model.model_dump(exclude_unset=True, exclude={"root"})
    return DesignFile.model_validate({**data, "root": root})


def _configure(
    design: DesignFile,
    node_path: NodePath,
    key: str,
    value: object,
    invalid_code: str,
    check: _Check | None = None,
    guard: Callable[[dict[str, Any]], None] | None = None,
) -> DesignEditResult:
    _, data, _ = revalidated(design)
    node = resolve(data["root"], node_path)
    if guard is not None and value is not None:
        guard(node)
    if _strict_equal(node.get(key), value):
        return DesignEditResult(design, False, node_path, ())
    if value is None:
        node.pop(key, None)
    else:
        node[key] = value
    try:
        DesignFile.model_validate(data)
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        raise Refused(
            invalid_code, "Valeur refusée par le modèle Design.", node_path
        ) from error
    model = rebuilt(data, node_path)
    if check is not None and value is not None:
        check(model, node_path)
    return DesignEditResult(model, True, node_path, ())


def set_design_binding(
    design: DesignFile, *, path: NodePath, binding: str | None, contract: ViewContract
) -> DesignEditResult:
    """Lier un bloc à une variable ou action du contrat ; None supprime le binding."""
    try:
        node_path = check_path(path)
        valid_contract = _contract(contract)
        value = _text(binding, "invalid_binding", "Le binding", node_path)

        def check(model: DesignFile, node_path: NodePath) -> None:
            result = validate_design_bindings(
                _projected(model, node_path), valid_contract
            )
            if result.truncated:
                raise Refused(
                    "analysis_truncated", "Analyse des bindings tronquée.", node_path
                )
            for issue in result.issues:
                code = (
                    "binding_not_supported"
                    if issue.code == "design.binding.unsupported"
                    else "invalid_binding"
                )
                raise Refused(code, issue.message, node_path)

        return _configure(design, node_path, "binding", value, "invalid_binding", check)
    except Refused as refused:
        return refusal(design, refused)


def set_design_visibility(
    design: DesignFile,
    *,
    path: NodePath,
    visible_if: str | None,
    contract: ViewContract,
) -> DesignEditResult:
    """Conditionner l'affichage à une variable booléenne ; None la supprime."""
    try:
        node_path = check_path(path)
        valid_contract = _contract(contract)
        value = _text(visible_if, "invalid_condition", "La condition", node_path)

        def check(model: DesignFile, node_path: NodePath) -> None:
            result = validate_conditional_bindings(
                _projected(model, node_path), valid_contract
            )
            if result.truncated:
                raise Refused(
                    "analysis_truncated", "Analyse des conditions tronquée.", node_path
                )
            for issue in result.issues:
                raise Refused("invalid_condition", issue.message, node_path)

        return _configure(
            design, node_path, "visible_if", value, "invalid_condition", check
        )
    except Refused as refused:
        return refusal(design, refused)


def set_design_props(
    design: DesignFile, *, path: NodePath, props: Mapping[str, PropValue] | None
) -> DesignEditResult:
    """Remplacer les props du bloc par une copie ; None les supprime.

    Le contrat Design (clés non vides, scalaires finis) s'applique, pas les
    seules props connues du générateur.
    """
    try:
        node_path = check_path(path)
        value: dict[object, object] | None = None
        raw = cast(object, props)  # contrôle runtime malgré le typage
        if raw is not None:
            if not isinstance(raw, Mapping):
                raise Refused(
                    "invalid_props", "Les props doivent être un mapping.", node_path
                )
            try:
                # Copie : le mapping de l'appelant ne doit jamais être conservé.
                value = dict(cast(Mapping[object, object], raw))
            except (TypeError, ValueError) as error:
                raise Refused(
                    "invalid_props", "Props illisibles.", node_path
                ) from error
        return _configure(design, node_path, "props", value, "invalid_props")
    except Refused as refused:
        return refusal(design, refused)


def set_table_columns(
    design: DesignFile,
    *,
    path: NodePath,
    columns: Sequence[TableColumn] | None,
    contract: ViewContract,
) -> DesignEditResult:
    """Remplacer les colonnes d'une table ; None les supprime, [] reste [].

    Des colonnes exigent un binding de table vers une variable list du contrat.
    """
    try:
        node_path = check_path(path)
        valid_contract = _contract(contract)
        value: list[dict[str, Any]] | None = None
        raw = cast(object, columns)  # contrôle runtime malgré le typage
        if raw is not None:
            if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
                raise Refused(
                    "invalid_table_column",
                    "Les colonnes doivent être une séquence.",
                    node_path,
                )
            items = list(cast(Sequence[object], raw))
            if len(items) > MAX_TABLE_COLUMNS:
                raise Refused(
                    "column_limit", f"Au plus {MAX_TABLE_COLUMNS} colonnes.", node_path
                )
            value = []
            for item in items:
                if not isinstance(item, TableColumn):
                    raise Refused(
                        "invalid_table_column",
                        "Chaque colonne doit être une TableColumn.",
                        node_path,
                    )
                # Copie revalidée ensuite par Pydantic avec le Design.
                value.append(item.model_dump())

        def guard(node: dict[str, Any]) -> None:
            if node["type"] != "table":
                raise Refused(
                    "columns_not_supported",
                    "Seul un bloc table accepte des colonnes.",
                    node_path,
                )

        def check(model: DesignFile, node_path: NodePath) -> None:
            result = validate_table_bindings(
                _projected(model, node_path), valid_contract
            )
            if result.truncated:
                raise Refused(
                    "analysis_truncated", "Analyse des colonnes tronquée.", node_path
                )
            (table,) = result.tables
            if table.status not in {"resolved", "fields_unavailable"}:
                raise Refused(
                    "invalid_table_binding",
                    "Les colonnes exigent un binding vers une variable list.",
                    node_path,
                )
            for issue in result.issues:
                code = (
                    "invalid_table_column"
                    if issue.code == "design.table.unknown_field"
                    else "invalid_table_binding"
                )
                raise Refused(code, issue.message, node_path)

        return _configure(
            design, node_path, "columns", value, "invalid_table_column", check, guard
        )
    except Refused as refused:
        return refusal(design, refused)
