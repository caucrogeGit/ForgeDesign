"""Projection arborescente pure de la structure déjà analysée, sans reparsing."""

from dataclasses import dataclass

from forge_design.forge.template_structure import (
    TemplateBlock,
    TemplateReference,
    TemplateStructure,
)


@dataclass(frozen=True)
class TemplateHtmlNode:
    tag: str
    line: int
    children: tuple["TemplateHtmlNode", ...] = ()


@dataclass(frozen=True)
class TemplateTree:
    dependencies: tuple[TemplateReference, ...]
    blocks: tuple[TemplateBlock, ...]
    html: tuple[TemplateHtmlNode, ...]
    partial: bool
    truncated: bool


@dataclass(frozen=True)
class TemplateTreeRow:
    tag: str
    line: int
    depth: int
    has_children: bool
    close_levels: int


def build_template_tree(structure: TemplateStructure) -> TemplateTree:
    """O(n), sans récursion ; un saut rejoint le parent disponible le plus proche.

    La pile conserve les profondeurs d'origine : deux sauts au même niveau restent
    frères. Une profondeur négative viole le contrat et lève ValueError.
    """
    children: list[list[int]] = []
    roots: list[int] = []
    stack: list[tuple[int, int]] = []
    for index, element in enumerate(structure.html_elements):
        if element.depth < 0:
            raise ValueError("La profondeur HTML ne peut pas être négative.")
        children.append([])
        while stack and stack[-1][0] >= element.depth:
            stack.pop()
        if stack:
            children[stack[-1][1]].append(index)
        else:
            roots.append(index)
        stack.append((element.depth, index))
    # Tous les enfants ont un index supérieur : gel du bas vers le haut.
    frozen: dict[int, TemplateHtmlNode] = {}
    for index in range(len(children) - 1, -1, -1):
        element = structure.html_elements[index]
        frozen[index] = TemplateHtmlNode(
            element.tag, element.line, tuple(frozen[child] for child in children[index])
        )
    return TemplateTree(
        structure.dependencies,
        structure.blocks,
        tuple(frozen[index] for index in roots),
        structure.partial,
        structure.truncated,
    )


def flatten_template_tree(tree: TemplateTree) -> tuple[TemplateTreeRow, ...]:
    """Parcours préfixe et nombres de fermetures pour des ul/li sans macro récursive."""
    pending = [(node, 0) for node in reversed(tree.html)]
    visited: list[tuple[TemplateHtmlNode, int]] = []
    while pending:
        node, depth = pending.pop()
        visited.append((node, depth))
        pending.extend((child, depth + 1) for child in reversed(node.children))
    return tuple(
        TemplateTreeRow(
            node.tag,
            node.line,
            depth,
            bool(node.children),
            max(0, depth - (visited[index + 1][1] if index + 1 < len(visited) else 0)),
        )
        for index, (node, depth) in enumerate(visited)
    )
