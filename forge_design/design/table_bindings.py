"""Projection pure des tables et validation de leurs colonnes déclarées."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Literal

from forge_design.contracts.models import ViewContextVariable, ViewContract
from forge_design.design.models import DesignFile, DesignNode, PageRoot
from forge_design.limits import (
    MAX_DESIGN_DEPTH,
    MAX_DESIGN_ISSUES,
    MAX_DESIGN_NODES,
    MAX_TABLE_COLUMNS,
)

TableBindingStatus = Literal[
    "no_binding",
    "unresolved_variable",
    "type_mismatch",
    "fields_unavailable",
    "resolved",
]


@dataclass(frozen=True)
class TableColumnBindingInfo:
    index: int
    label: str
    binding: str
    field_type: str | None
    # None : aucune validation possible, distinct de champ déclaré inconnu.
    valid: bool | None


@dataclass(frozen=True)
class TableBindingInfo:
    location: tuple[str | int, ...]
    binding: str | None
    entity: str | None
    available_fields: tuple[str, ...]
    columns: tuple[TableColumnBindingInfo, ...]
    status: TableBindingStatus
    has_empty_state: bool = False


@dataclass(frozen=True)
class TableBindingIssue:
    code: str
    message: str
    location: tuple[str | int, ...]
    table_binding: str | None
    column_binding: str | None = None


@dataclass(frozen=True)
class TableBindingResult:
    valid: bool
    tables: tuple[TableBindingInfo, ...]
    issues: tuple[TableBindingIssue, ...]
    truncated: bool = False


@dataclass(frozen=True)
class SuggestedTableColumn:
    binding: str
    field_type: str
    label: str


def suggest_table_columns(
    variable: ViewContextVariable,
) -> tuple[SuggestedTableColumn, ...]:
    if variable.type != "list":
        raise ValueError("Les suggestions nécessitent une variable list.")
    if variable.fields is None:
        return ()
    return tuple(
        SuggestedTableColumn(key, value, key) for key, value in variable.fields.items()
    )


def validate_table_bindings(
    design: DesignFile, contract: ViewContract
) -> TableBindingResult:
    """Analyse préfixe indépendante des bindings simples et de l'imbrication.

    Les colonnes sont bornées par table. Les états vides sont repérés durant le
    parcours des nœuds, sans balayage supplémentaire non borné des enfants.
    """
    tables: list[TableBindingInfo] = []
    issues: list[TableBindingIssue] = []
    truncated = False
    # Réutiliser les tuples de noms quand plusieurs tables partagent les fields.
    field_names: dict[int, tuple[str, ...]] = {}

    def stop(
        location: tuple[str | int, ...], binding: str | None, column: str | None = None
    ) -> None:
        nonlocal truncated
        truncated = True
        if len(issues) == MAX_DESIGN_ISSUES:
            issues.pop()
        issues.append(
            TableBindingIssue(
                "design.table.analysis_truncated",
                "Limite d'analyse des tableaux atteinte.",
                location,
                binding,
                column,
            )
        )

    def issue(
        code: str,
        message: str,
        location: tuple[str | int, ...],
        binding: str | None,
        column: str | None = None,
    ) -> None:
        if len(issues) == MAX_DESIGN_ISSUES:
            stop(location, binding, column)
        else:
            issues.append(
                TableBindingIssue(
                    "design.table." + code, message, location, binding, column
                )
            )

    stack: list[
        tuple[
            Iterator[tuple[int, DesignNode | PageRoot]],
            tuple[str | int, ...],
            int,
            int | None,
        ]
    ] = [(iter(enumerate((design.root,))), (), 0, None)]
    inspected = 0
    while stack and not truncated:
        iterator, parent_path, depth, parent_table = stack[-1]
        entry = next(iterator, None)
        if entry is None:
            stack.pop()
            continue
        index, node = entry
        path = (*parent_path, "children", index) if parent_path else ("root",)
        if inspected >= MAX_DESIGN_NODES or depth > MAX_DESIGN_DEPTH:
            binding = (
                node.binding
                if node.type == "table"
                else (
                    tables[parent_table].binding if parent_table is not None else None
                )
            )
            stop(path, binding)
            break
        inspected += 1
        if parent_table is not None and node.type == "empty_state":
            tables[parent_table] = replace(tables[parent_table], has_empty_state=True)
        table_index = None
        if node.type == "table":
            variable = (
                contract.context.get(node.binding) if node.binding is not None else None
            )
            fields: dict[str, str] | None = None
            entity = None
            status: TableBindingStatus
            if node.binding is None:
                status = "no_binding"
            elif variable is None:
                status = "unresolved_variable"
            elif variable.type != "list":
                status = "type_mismatch"
            else:
                entity, fields = variable.entity, variable.fields
                status = "fields_unavailable" if fields is None else "resolved"
            available: tuple[str, ...] = ()
            if fields is not None:
                key = id(fields)
                if key not in field_names:
                    field_names[key] = tuple(fields)
                available = field_names[key]
            columns: list[TableColumnBindingInfo] = []
            if status == "fields_unavailable" and node.columns:
                issue(
                    "fields_unavailable",
                    "Structure des champs non décrite dans le contrat.",
                    (*path, "columns"),
                    node.binding,
                )
            if not truncated and node.columns:
                for column_index, column in enumerate(node.columns):
                    column_path = (*path, "columns", column_index, "binding")
                    if column_index >= MAX_TABLE_COLUMNS:
                        stop(column_path, node.binding, column.binding)
                        break
                    field_type = (
                        fields.get(column.binding) if fields is not None else None
                    )
                    valid = column.binding in fields if fields is not None else None
                    columns.append(
                        TableColumnBindingInfo(
                            column_index,
                            column.label,
                            column.binding,
                            field_type,
                            valid,
                        )
                    )
                    if valid is False:
                        issue(
                            "unknown_field",
                            "Champ non déclaré dans la collection.",
                            column_path,
                            node.binding,
                            column.binding,
                        )
                        if truncated:
                            break
            table_index = len(tables)
            tables.append(
                TableBindingInfo(
                    path, node.binding, entity, available, tuple(columns), status
                )
            )
        if not truncated and node.children:
            stack.append((iter(enumerate(node.children)), path, depth + 1, table_index))
    return TableBindingResult(
        not issues and not truncated, tuple(tables), tuple(issues), truncated
    )
