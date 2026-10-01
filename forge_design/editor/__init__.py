"""Éditeur structurel de Design en mémoire, sans I/O ni Web."""

from forge_design.editor.structure import (
    DesignEditIssue,
    DesignEditResult,
    NodePath,
    append_design_block,
    remove_design_block,
)

__all__ = [
    "NodePath",
    "DesignEditIssue",
    "DesignEditResult",
    "append_design_block",
    "remove_design_block",
]
