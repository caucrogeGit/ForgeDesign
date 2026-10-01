"""Socle interne de l'éditeur : chemins, revalidation, reconstruction.

Partagé par structure.py (arbre) et properties.py (configuration d'un nœud).
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from forge_design.design import nesting
from forge_design.design.models import DesignFile, DesignNode, PageRoot
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_NODES

NodePath = tuple[int, ...]
"""Indices d'enfants depuis la racine : () est la page, (0, 2) le 3e enfant du 1er."""


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


class Refused(Exception):
    def __init__(self, code: str, message: str, path: NodePath) -> None:
        super().__init__(message)
        self.issue = DesignEditIssue("editor." + code, message, path)


def count_nodes(design: DesignFile) -> int:
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
            raise Refused("invalid_design", "Design hors limites.", ())
        if not isinstance(node, (DesignNode, PageRoot)):
            raise Refused("invalid_design", "Nœud de design invalide.", ())
        count += 1
        if node.children:
            stack.append((iter(node.children), depth + 1))
    return count


def revalidated(design: object) -> tuple[DesignFile, dict[str, Any], int]:
    """Ne pas croire le modèle reçu : ses listes internes restent mutables."""
    if not isinstance(design, DesignFile):
        raise Refused("invalid_design", "Un DesignFile est attendu.", ())
    count = count_nodes(design)
    try:
        data = design.model_dump(exclude_unset=True)
        model = DesignFile.model_validate(data)
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        raise Refused("invalid_design", "Design non conforme.", ()) from error
    if not nesting.validate_design_nesting(model).valid:
        raise Refused("invalid_design", "Imbrication initiale invalide.", ())
    # data provient du dump : dicts et listes neufs, sans lien avec l'entrée.
    return model, data, count


def check_path(path: object) -> NodePath:
    if not isinstance(path, tuple):
        raise Refused("invalid_path", "Le chemin doit être un tuple d'indices.", ())
    items: tuple[object, ...] = path  # pyright: ignore[reportUnknownVariableType]
    indices: list[int] = []
    for index in items:
        # bool est un int Python, pas un indice d'arbre.
        if type(index) is not int:
            raise Refused("invalid_path", "Indice de chemin invalide.", ())
        indices.append(index)
    return tuple(indices)


def resolve(root: dict[str, Any], path: NodePath) -> dict[str, Any]:
    """NodePath → nœud du dump ; indices négatifs ou hors bornes refusés."""
    node = root
    for depth, index in enumerate(path):
        children: list[dict[str, Any]] = node.get("children") or []
        if not 0 <= index < len(children):
            raise Refused(
                "path_not_found", "Aucun bloc à cet emplacement.", path[: depth + 1]
            )
        node = children[index]
    return node


def rebuilt(data: dict[str, Any], path: NodePath) -> DesignFile:
    """Le résultat n'est rendu que s'il est un Design valide et bien imbriqué."""
    try:
        model = DesignFile.model_validate(data)
    except (ValidationError, ValueError, TypeError, RecursionError) as error:
        raise Refused("invalid_result", "Résultat d'édition invalide.", path) from error
    if not nesting.validate_design_nesting(model).valid:
        raise Refused("invalid_result", "Résultat d'édition mal imbriqué.", path)
    return model


def refusal(design: DesignFile, refused: Refused) -> DesignEditResult:
    return DesignEditResult(design, False, None, (refused.issue,))
