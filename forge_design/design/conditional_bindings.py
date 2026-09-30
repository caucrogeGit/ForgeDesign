"""Validation pure des références booléennes de visibilité."""

from collections.abc import Iterator
from dataclasses import dataclass

from forge_design.contracts.models import ViewContract
from forge_design.design.models import DesignFile, DesignNode, DesignNodeType, PageRoot
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES


@dataclass(frozen=True)
class ConditionalBindingIssue:
    code: str
    message: str
    location: tuple[str | int, ...]
    node_type: DesignNodeType
    # Un marqueur peut viser un nœud sans visible_if.
    binding: str | None


@dataclass(frozen=True)
class ConditionalBindingResult:
    valid: bool
    issues: tuple[ConditionalBindingIssue, ...]
    truncated: bool = False


def _binding_error(
    node: DesignNode | PageRoot, contract: ViewContract
) -> tuple[str, str] | None:
    binding = node.visible_if
    if binding is None:
        return None
    variable = contract.context.get(binding)
    if variable is None:
        return "unknown_variable", "Variable inconnue dans le contexte."
    if variable.type != "boolean":
        return "type_mismatch", "Type de variable incompatible ; boolean attendu."
    return None


def validate_conditional_bindings(
    design: DesignFile, contract: ViewContract
) -> ConditionalBindingResult:
    """Parcours préfixe borné, racine comprise à profondeur zéro.

    Pas de revalidation Pydantic/nesting, de dump ou de résolution de fichier.
    Les dictionnaires du contrat servent directement d'index.
    """
    issues: list[ConditionalBindingIssue] = []
    stack: list[
        tuple[Iterator[tuple[int, DesignNode | PageRoot]], tuple[str | int, ...], int]
    ] = [(iter(enumerate((design.root,))), (), 0)]
    inspected = 0
    while stack:
        iterator, parent_path, depth = stack[-1]
        entry = next(iterator, None)
        if entry is None:
            stack.pop()
            continue
        index, node = entry
        path = (*parent_path, "children", index) if parent_path else ("root",)
        reason = None
        if inspected >= MAX_DESIGN_NODES:
            reason = "nombre de nœuds"
        elif depth > MAX_DESIGN_DEPTH:
            reason = "profondeur"
        else:
            inspected += 1
            error = _binding_error(node, contract)
            if error is not None:
                if len(issues) >= MAX_DESIGN_ISSUES:
                    reason = "nombre de diagnostics"
                else:
                    code, message = error
                    issues.append(
                        ConditionalBindingIssue(
                            "design.condition." + code,
                            message,
                            (*path, "visible_if"),
                            node.type,
                            node.visible_if,
                        )
                    )
        if reason is not None:
            if len(issues) == MAX_DESIGN_ISSUES:
                issues.pop()
            issues.append(
                ConditionalBindingIssue(
                    "design.condition.analysis_truncated",
                    f"Analyse interrompue : limite de {reason} atteinte.",
                    path,
                    node.type,
                    node.visible_if,
                )
            )
            return ConditionalBindingResult(False, tuple(issues), truncated=True)
        if node.children:
            stack.append((iter(enumerate(node.children)), path, depth + 1))
    return ConditionalBindingResult(not issues, tuple(issues))
