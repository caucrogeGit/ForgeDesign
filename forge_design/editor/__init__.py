"""Éditeur de Design en mémoire : structure et propriétés, sans I/O ni Web."""

from forge_design.editor.properties import (
    set_design_binding,
    set_design_props,
    set_design_visibility,
    set_field_definition,
    set_table_columns,
)
from forge_design.editor.structure import (
    DesignEditIssue,
    DesignEditResult,
    NodePath,
    append_design_block,
    move_design_block,
    remove_design_block,
)

__all__ = [
    "NodePath",
    "DesignEditIssue",
    "DesignEditResult",
    "append_design_block",
    "remove_design_block",
    "move_design_block",
    "set_design_binding",
    "set_design_visibility",
    "set_design_props",
    "set_table_columns",
    "set_field_definition",
]
