"""Validation pure et bornée des relations parent/enfant du design v0.1."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from forge_design.design.models import DesignFile, DesignNode, DesignNodeType, PageRoot
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES

ALLOWED_CHILDREN: Mapping[DesignNodeType, frozenset[DesignNodeType]] = MappingProxyType(
    {
        "page": frozenset({"section", "table"}),
        "section": frozenset(
            {"container", "grid", "card", "form", "table", "alert", "text"}
        ),
        "container": frozenset({"grid", "card", "form", "table", "text", "button"}),
        "card": frozenset({"title", "text", "form", "button", "grid"}),
        "form": frozenset({"field", "button", "alert"}),
        "table": frozenset({"empty_state"}),
        "grid": frozenset(),
        "title": frozenset(),
        "text": frozenset(),
        "button": frozenset(),
        "field": frozenset(),
        "alert": frozenset(),
        "empty_state": frozenset(),
    }
)


@dataclass(frozen=True)
class DesignNestingIssue:
    code: str
    message: str
    path: tuple[str | int, ...]
    parent_type: DesignNodeType
    child_type: DesignNodeType


@dataclass(frozen=True)
class DesignNestingResult:
    valid: bool
    issues: tuple[DesignNestingIssue, ...]
    truncated: bool = False


def can_contain(parent: DesignNodeType, child: DesignNodeType) -> bool:
    return child in ALLOWED_CHILDREN[parent]


def validate_design_nesting(design: DesignFile) -> DesignNestingResult:
    """Parcours préfixe ; racine comptée, profondeur racine zéro.

    Les itérateurs évitent d'empiler tous les enfants d'un nœud très large.
    L'entrée doit être un modèle structurellement valide ; aucun dump/revalidation.
    """
    issues: list[DesignNestingIssue] = []
    stack: list[
        tuple[
            DesignNode | PageRoot,
            Iterator[tuple[int, DesignNode]],
            tuple[str | int, ...],
            int,
        ]
    ] = [(design.root, iter(enumerate(design.root.children)), ("root",), 0)]
    inspected = 1
    while stack:
        parent, children, parent_path, parent_depth = stack[-1]
        entry = next(children, None)
        if entry is None:
            stack.pop()
            continue
        index, child = entry
        path = (*parent_path, "children", index)
        depth = parent_depth + 1
        reason = None
        if inspected >= MAX_DESIGN_NODES:
            reason = "nombre de nœuds"
        elif depth > MAX_DESIGN_DEPTH:
            reason = "profondeur"
        else:
            inspected += 1
            if not can_contain(parent.type, child.type):
                if len(issues) >= MAX_DESIGN_ISSUES:
                    reason = "nombre de diagnostics"
                else:
                    issues.append(
                        DesignNestingIssue(
                            "design.nesting.child_not_allowed",
                            (
                                f'Le bloc "{parent.type}" ne peut pas contenir '
                                f'"{child.type}".'
                            ),
                            path,
                            parent.type,
                            child.type,
                        )
                    )
        if reason is not None:
            # La borne inclut le marqueur : conserver le préfixe des diagnostics.
            if len(issues) == MAX_DESIGN_ISSUES:
                issues.pop()
            issues.append(
                DesignNestingIssue(
                    "design.nesting.analysis_truncated",
                    f"Analyse interrompue : limite de {reason} atteinte.",
                    path,
                    parent.type,
                    child.type,
                )
            )
            return DesignNestingResult(False, tuple(issues), truncated=True)
        if child.children:
            stack.append((child, iter(enumerate(child.children)), path, depth))
    return DesignNestingResult(not issues, tuple(issues))
