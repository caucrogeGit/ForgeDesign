"""Résolution pure des bindings simples entre deux modèles déjà validés."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from forge_design.contracts.models import ViewContract
from forge_design.design.models import DesignFile, DesignNode, DesignNodeType, PageRoot
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES

_BINDING_RULES: Mapping[DesignNodeType, Literal["string", "list", "action"]] = (
    MappingProxyType(
        {"title": "string", "text": "string", "table": "list", "button": "action"}
    )
)


@dataclass(frozen=True)
class DesignBindingIssue:
    code: str
    message: str
    location: tuple[str | int, ...]
    node_type: DesignNodeType
    # Un marqueur d'analyse peut viser un nœud sans binding.
    binding: str | None


@dataclass(frozen=True)
class DesignBindingResult:
    valid: bool
    issues: tuple[DesignBindingIssue, ...]
    truncated: bool = False


def _binding_error(
    node: DesignNode | PageRoot, contract: ViewContract
) -> tuple[str, str] | None:
    binding = node.binding
    if binding is None:
        return None
    rule = _BINDING_RULES.get(node.type)
    if rule is None:
        return "unsupported", "Binding non supporté pour ce type de bloc."
    if rule == "action":
        if contract.actions is None or binding not in contract.actions:
            return "unknown_action", "Action inconnue dans le contrat."
        return None
    variable = contract.context.get(binding)
    if variable is None:
        return "unknown_variable", "Variable inconnue dans le contexte."
    if variable.type != rule:
        return "type_mismatch", f"Type de variable incompatible ; {rule} attendu."
    return None


def validate_design_bindings(
    design: DesignFile, contract: ViewContract
) -> DesignBindingResult:
    """Parcours préfixe borné, racine comprise à profondeur zéro.

    Pas de revalidation Pydantic/nesting, de dump ou de résolution de fichier.
    Les dictionnaires du contrat servent directement d'index.
    """
    issues: list[DesignBindingIssue] = []
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
                        DesignBindingIssue(
                            "design.binding." + code,
                            message,
                            (*path, "binding"),
                            node.type,
                            node.binding,
                        )
                    )
        if reason is not None:
            if len(issues) == MAX_DESIGN_ISSUES:
                issues.pop()
            issues.append(
                DesignBindingIssue(
                    "design.binding.analysis_truncated",
                    f"Analyse interrompue : limite de {reason} atteinte.",
                    path,
                    node.type,
                    node.binding,
                )
            )
            return DesignBindingResult(False, tuple(issues), truncated=True)
        if node.children:
            stack.append((iter(enumerate(node.children)), path, depth + 1))
    return DesignBindingResult(not issues, tuple(issues))
