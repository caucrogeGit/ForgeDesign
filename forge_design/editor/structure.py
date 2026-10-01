"""Ajout, suppression et déplacement de blocs dans un DesignFile en mémoire, sans I/O.

Chaque opération revalide l'entrée, travaille sur une copie issue de model_dump,
puis reconstruit et revalide un nouveau DesignFile. L'entrée n'est jamais mutée.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, get_args

from pydantic import ValidationError

from forge_design.design import nesting
from forge_design.design.models import DesignFile, DesignNode, DesignNodeType, PageRoot
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_NODES

NodePath = tuple[int, ...]
"""Indices d'enfants depuis la racine : () est la page, (0, 2) le 3e enfant du 1er."""

_BLOCK_TYPES: frozenset[str] = frozenset(get_args(DesignNodeType))


@dataclass(frozen=True)
class DesignEditIssue:
    code: str
    message: str
    path: NodePath


@dataclass(frozen=True)
class DesignEditResult:
    design: DesignFile
    changed: bool
    affected_path: NodePath | None
    issues: tuple[DesignEditIssue, ...]


class _Refused(Exception):
    def __init__(self, code: str, message: str, path: NodePath) -> None:
        super().__init__(message)
        self.issue = DesignEditIssue("editor." + code, message, path)


def _count_nodes(design: DesignFile) -> int:
    """Parcours borné avant model_dump : un arbre muté peut contenir un cycle."""
    stack: list[tuple[Iterator[object], int]] = [(iter((design.root,)), 0)]
    count = 0
    while stack:
        iterator, depth = stack[-1]
        node = next(iterator, None)
        if node is None:
            stack.pop()
            continue
        if count >= MAX_DESIGN_NODES or depth > MAX_DESIGN_DEPTH:
            raise _Refused("invalid_design", "Design hors limites.", ())
        if not isinstance(node, (DesignNode, PageRoot)):
            raise _Refused("invalid_design", "Nœud de design invalide.", ())
        count += 1
        if node.children:
            stack.append((iter(node.children), depth + 1))
    return count


def _revalidated(design: object) -> tuple[DesignFile, dict[str, Any], int]:
    """Ne pas croire le modèle reçu : ses listes internes restent mutables."""
    if not isinstance(design, DesignFile):
        raise _Refused("invalid_design", "Un DesignFile est attendu.", ())
    count = _count_nodes(design)
    try:
        data = design.model_dump(exclude_unset=True)
        model = DesignFile.model_validate(data)
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        raise _Refused("invalid_design", "Design non conforme.", ()) from error
    if not nesting.validate_design_nesting(model).valid:
        raise _Refused("invalid_design", "Imbrication initiale invalide.", ())
    # data provient du dump : dicts et listes neufs, sans lien avec l'entrée.
    return model, data, count


def _check_path(path: object) -> NodePath:
    if not isinstance(path, tuple):
        raise _Refused("invalid_path", "Le chemin doit être un tuple d'indices.", ())
    items: tuple[object, ...] = path  # pyright: ignore[reportUnknownVariableType]
    indices: list[int] = []
    for index in items:
        # bool est un int Python, pas un indice d'arbre.
        if type(index) is not int:
            raise _Refused("invalid_path", "Indice de chemin invalide.", ())
        indices.append(index)
    return tuple(indices)


def _resolve(root: dict[str, Any], path: NodePath) -> dict[str, Any]:
    """NodePath → nœud du dump ; indices négatifs ou hors bornes refusés."""
    node = root
    for depth, index in enumerate(path):
        children: list[dict[str, Any]] = node.get("children") or []
        if not 0 <= index < len(children):
            raise _Refused(
                "path_not_found", "Aucun bloc à cet emplacement.", path[: depth + 1]
            )
        node = children[index]
    return node


def _detach(root: dict[str, Any], path: NodePath) -> dict[str, Any]:
    """Retirer le nœud (path non vide, déjà résolu) et le rendre avec son sous-arbre.

    Un bloc autre que la page qui perd son dernier enfant perd sa clé children.
    """
    parent = _resolve(root, path[:-1])
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


def _rebuilt(data: dict[str, Any], path: NodePath) -> DesignFile:
    """Le résultat n'est rendu que s'il est un Design valide et bien imbriqué."""
    try:
        model = DesignFile.model_validate(data)
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        raise _Refused(
            "invalid_result", "Résultat d'édition invalide.", path
        ) from error
    if not nesting.validate_design_nesting(model).valid:
        raise _Refused("invalid_result", "Résultat d'édition mal imbriqué.", path)
    return model


def _refusal(design: DesignFile, refused: _Refused) -> DesignEditResult:
    return DesignEditResult(design, False, None, (refused.issue,))


def append_design_block(
    design: DesignFile, *, parent: NodePath, block_type: DesignNodeType
) -> DesignEditResult:
    """Ajouter DesignNode(type=block_type) en dernier enfant de parent."""
    try:
        parent_path = _check_path(parent)
        kind: object = block_type
        if kind not in _BLOCK_TYPES:
            raise _Refused("unknown_block_type", "Type de bloc inconnu.", parent_path)
        if kind == "page":
            raise _Refused(
                "root_type_not_insertable",
                "Une page ne peut pas être un bloc enfant.",
                parent_path,
            )
        _, data, count = _revalidated(design)
        target = _resolve(data["root"], parent_path)
        if not nesting.can_contain(target["type"], block_type):
            raise _Refused(
                "child_not_allowed",
                f'Le bloc "{target["type"]}" ne peut pas contenir "{block_type}".',
                parent_path,
            )
        if count >= MAX_DESIGN_NODES:
            raise _Refused(
                "node_limit", "Nombre maximal de blocs atteint.", parent_path
            )
        if len(parent_path) + 1 > MAX_DESIGN_DEPTH:
            raise _Refused("depth_limit", "Profondeur maximale atteinte.", parent_path)
        children: list[dict[str, Any]] = target.setdefault("children", [])
        affected = (*parent_path, len(children))
        children.append({"type": block_type})
        return DesignEditResult(_rebuilt(data, affected), True, affected, ())
    except _Refused as refused:
        return _refusal(design, refused)


def remove_design_block(design: DesignFile, *, path: NodePath) -> DesignEditResult:
    """Supprimer le bloc et tout son sous-arbre ; jamais la racine."""
    try:
        node_path = _check_path(path)
        if not node_path:
            raise _Refused(
                "root_not_removable",
                "La racine de page ne peut pas être supprimée.",
                (),
            )
        _, data, _ = _revalidated(design)
        _resolve(data["root"], node_path)
        _detach(data["root"], node_path)
        parent_path = node_path[:-1]
        return DesignEditResult(_rebuilt(data, parent_path), True, parent_path, ())
    except _Refused as refused:
        return _refusal(design, refused)


def move_design_block(
    design: DesignFile, *, source: NodePath, destination: NodePath
) -> DesignEditResult:
    """Déplacer source et son sous-arbre en dernier enfant de destination.

    Les deux chemins désignent l'arbre initial ; destination est recalculée
    après le retrait de source. Déjà dernier enfant de destination : no-op.
    """
    try:
        source_path = _check_path(source)
        target_path = _check_path(destination)
        if not source_path:
            raise _Refused(
                "root_not_movable", "La racine de page ne peut pas être déplacée.", ()
            )
        _, data, _ = _revalidated(design)
        root = data["root"]
        moved = _resolve(root, source_path)
        target = _resolve(root, target_path)
        # Avant tout retrait : un bloc ne peut pas entrer dans son propre sous-arbre.
        if target_path[: len(source_path)] == source_path:
            raise _Refused(
                "destination_inside_source",
                "Un bloc ne peut pas devenir son propre descendant.",
                target_path,
            )
        siblings: list[dict[str, Any]] = target.get("children") or []
        if target_path == source_path[:-1] and source_path[-1] == len(siblings) - 1:
            return DesignEditResult(design, False, source_path, ())
        if not nesting.can_contain(target["type"], moved["type"]):
            raise _Refused(
                "child_not_allowed",
                f'Le bloc "{target["type"]}" ne peut pas contenir "{moved["type"]}".',
                target_path,
            )
        if len(target_path) + 1 + _relative_height(moved) > MAX_DESIGN_DEPTH:
            raise _Refused("depth_limit", "Profondeur maximale dépassée.", target_path)
        node = _detach(root, source_path)
        adjusted = _adjust_path_after_removal(target_path, source_path)
        children: list[dict[str, Any]] = _resolve(root, adjusted).setdefault(
            "children", []
        )
        affected = (*adjusted, len(children))
        children.append(node)
        return DesignEditResult(_rebuilt(data, affected), True, affected, ())
    except _Refused as refused:
        return _refusal(design, refused)
