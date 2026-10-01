"""Ajout, suppression et déplacement de blocs dans un DesignFile en mémoire, sans I/O.

Chaque opération revalide l'entrée, travaille sur une copie issue de model_dump,
puis reconstruit et revalide un nouveau DesignFile. L'entrée n'est jamais mutée.
"""

from typing import Any, get_args

from forge_design.design import nesting
from forge_design.design.models import DesignFile, DesignNodeType
from forge_design.editor._tree import (
    DesignEditIssue,
    DesignEditResult,
    NodePath,
    Refused,
    check_path,
    rebuilt,
    refusal,
    resolve,
    revalidated,
)
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_NODES

__all__ = [
    "NodePath",
    "DesignEditIssue",
    "DesignEditResult",
    "append_design_block",
    "remove_design_block",
    "move_design_block",
]

_BLOCK_TYPES: frozenset[str] = frozenset(get_args(DesignNodeType))


def _detach(root: dict[str, Any], path: NodePath) -> dict[str, Any]:
    """Retirer le nœud (path non vide, déjà résolu) et le rendre avec son sous-arbre.

    Un bloc autre que la page qui perd son dernier enfant perd sa clé children.
    """
    parent = resolve(root, path[:-1])
    children: list[dict[str, Any]] = parent["children"]
    node = children.pop(path[-1])
    if not children and len(path) > 1:
        del parent["children"]
    return node


def _adjust_path_after_removal(path: NodePath, removed: NodePath) -> NodePath:
    """Chemin de l'arbre initial → même nœud après retrait de removed.

    Seul l'indice du niveau de removed peut changer : il baisse de 1 si path
    passe par un frère suivant de removed. path ne doit pas être dans removed.
    """
    level = len(removed) - 1
    if len(path) <= level or path[:level] != removed[:level]:
        return path
    if path[level] == removed[level]:
        raise ValueError("Le chemin est dans le sous-arbre retiré.")
    if path[level] < removed[level]:
        return path
    return (*path[:level], path[level] - 1, *path[level + 1 :])


def _relative_height(node: dict[str, Any]) -> int:
    """Profondeur maximale des descendants sous node (0 pour une feuille), bornée."""
    height = 0
    stack: list[tuple[dict[str, Any], int]] = [(node, 0)]
    while stack:
        current, depth = stack.pop()
        height = max(height, depth)
        if depth < MAX_DESIGN_DEPTH:
            children: list[dict[str, Any]] = current.get("children") or []
            stack.extend((child, depth + 1) for child in children)
    return height


def append_design_block(
    design: DesignFile, *, parent: NodePath, block_type: DesignNodeType
) -> DesignEditResult:
    """Ajouter DesignNode(type=block_type) en dernier enfant de parent."""
    try:
        parent_path = check_path(parent)
        kind: object = block_type
        if kind not in _BLOCK_TYPES:
            raise Refused("unknown_block_type", "Type de bloc inconnu.", parent_path)
        if kind == "page":
            raise Refused(
                "root_type_not_insertable",
                "Une page ne peut pas être un bloc enfant.",
                parent_path,
            )
        _, data, count = revalidated(design)
        target = resolve(data["root"], parent_path)
        if not nesting.can_contain(target["type"], block_type):
            raise Refused(
                "child_not_allowed",
                f'Le bloc "{target["type"]}" ne peut pas contenir "{block_type}".',
                parent_path,
            )
        if count >= MAX_DESIGN_NODES:
            raise Refused("node_limit", "Nombre maximal de blocs atteint.", parent_path)
        if len(parent_path) + 1 > MAX_DESIGN_DEPTH:
            raise Refused("depth_limit", "Profondeur maximale atteinte.", parent_path)
        children: list[dict[str, Any]] = target.setdefault("children", [])
        affected = (*parent_path, len(children))
        children.append({"type": block_type})
        return DesignEditResult(rebuilt(data, affected), True, affected, ())
    except Refused as refused:
        return refusal(design, refused)


def remove_design_block(design: DesignFile, *, path: NodePath) -> DesignEditResult:
    """Supprimer le bloc et tout son sous-arbre ; jamais la racine."""
    try:
        node_path = check_path(path)
        if not node_path:
            raise Refused(
                "root_not_removable",
                "La racine de page ne peut pas être supprimée.",
                (),
            )
        _, data, _ = revalidated(design)
        resolve(data["root"], node_path)
        _detach(data["root"], node_path)
        parent_path = node_path[:-1]
        return DesignEditResult(rebuilt(data, parent_path), True, parent_path, ())
    except Refused as refused:
        return refusal(design, refused)


def move_design_block(
    design: DesignFile, *, source: NodePath, destination: NodePath
) -> DesignEditResult:
    """Déplacer source et son sous-arbre en dernier enfant de destination.

    Les deux chemins désignent l'arbre initial ; destination est recalculée
    après le retrait de source. Déjà dernier enfant de destination : no-op.
    """
    try:
        source_path = check_path(source)
        target_path = check_path(destination)
        if not source_path:
            raise Refused(
                "root_not_movable", "La racine de page ne peut pas être déplacée.", ()
            )
        _, data, _ = revalidated(design)
        root = data["root"]
        moved = resolve(root, source_path)
        target = resolve(root, target_path)
        # Avant tout retrait : un bloc ne peut pas entrer dans son propre sous-arbre.
        if target_path[: len(source_path)] == source_path:
            raise Refused(
                "destination_inside_source",
                "Un bloc ne peut pas devenir son propre descendant.",
                target_path,
            )
        siblings: list[dict[str, Any]] = target.get("children") or []
        if target_path == source_path[:-1] and source_path[-1] == len(siblings) - 1:
            return DesignEditResult(design, False, source_path, ())
        if not nesting.can_contain(target["type"], moved["type"]):
            raise Refused(
                "child_not_allowed",
                f'Le bloc "{target["type"]}" ne peut pas contenir "{moved["type"]}".',
                target_path,
            )
        if len(target_path) + 1 + _relative_height(moved) > MAX_DESIGN_DEPTH:
            raise Refused("depth_limit", "Profondeur maximale dépassée.", target_path)
        node = _detach(root, source_path)
        adjusted = _adjust_path_after_removal(target_path, source_path)
        children: list[dict[str, Any]] = resolve(root, adjusted).setdefault(
            "children", []
        )
        affected = (*adjusted, len(children))
        children.append(node)
        return DesignEditResult(rebuilt(data, affected), True, affected, ())
    except Refused as refused:
        return refusal(design, refused)
