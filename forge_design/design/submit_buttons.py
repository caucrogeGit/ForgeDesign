"""Validation sémantique des boutons de soumission (FD-INTERACT-004).

submit marque un bouton qui soumet son formulaire parent ; binding reste réservé
aux actions autonomes. Seul le Design est examiné : la validité de l'action du
form parent relève de validate_design_bindings.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from forge_design.design.models import DesignFile, DesignNode, DesignNodeType, PageRoot
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES

Location = tuple[str | int, ...]


@dataclass(frozen=True)
class SubmitButtonIssue:
    code: str
    message: str
    location: Location


@dataclass(frozen=True)
class SubmitButtonValidationResult:
    valid: bool
    issues: tuple[SubmitButtonIssue, ...]
    truncated: bool = False


def _submit_errors(
    node: DesignNode | PageRoot, parent: DesignNodeType | None, location: Location
) -> list[SubmitButtonIssue]:
    if node.submit is None:
        return []
    where = (*location, "submit")
    if node.type != "button":
        return [
            SubmitButtonIssue(
                "design.submit.unsupported_definition",
                "Seul un bloc button peut être un bouton de soumission.",
                where,
            )
        ]
    errors: list[SubmitButtonIssue] = []
    if node.binding is not None:
        errors.append(
            SubmitButtonIssue(
                "design.submit.conflicting_action",
                "Un bouton ne peut pas être à la fois une action et une soumission.",
                where,
            )
        )
    # form → field | button | alert : aucun conteneur intermédiaire légal.
    if parent != "form":
        errors.append(
            SubmitButtonIssue(
                "design.submit.outside_form",
                "Un bouton de soumission doit être un enfant direct d'un form.",
                where,
            )
        )
    return errors


def validate_submit_buttons(design: DesignFile) -> SubmitButtonValidationResult:
    """Parcours préfixe borné, racine comprise à profondeur zéro.

    Plusieurs submits par formulaire sont admis ; un bouton sans binding ni
    submit n'est pas signalé ici.
    """
    issues: list[SubmitButtonIssue] = []
    stack: list[
        tuple[
            Iterator[tuple[int, DesignNode | PageRoot]],
            Location,
            int,
            DesignNodeType | None,
        ]
    ] = [(iter(enumerate((design.root,))), (), 0, None)]
    inspected = 0
    while stack:
        iterator, parent_path, depth, parent_type = stack[-1]
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
            for issue in _submit_errors(node, parent_type, path):
                if len(issues) >= MAX_DESIGN_ISSUES:
                    reason = "nombre de diagnostics"
                    break
                issues.append(issue)
        if reason is not None:
            # La borne inclut le marqueur : conserver le préfixe des diagnostics.
            if len(issues) == MAX_DESIGN_ISSUES:
                issues.pop()
            issues.append(
                SubmitButtonIssue(
                    "design.submit.analysis_truncated",
                    f"Analyse interrompue : limite de {reason} atteinte.",
                    path,
                )
            )
            return SubmitButtonValidationResult(False, tuple(issues), truncated=True)
        if node.children:
            stack.append((iter(enumerate(node.children)), path, depth + 1, node.type))
    return SubmitButtonValidationResult(not issues, tuple(issues))
