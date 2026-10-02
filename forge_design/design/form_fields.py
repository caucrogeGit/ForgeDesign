"""Validation sémantique des définitions de champs de formulaire (FD-INTERACT-002).

Le modèle Pydantic porte la structure (name, input_type, label, required) ; ce
module vérifie seulement la place des définitions et l'unicité des noms dans un
même formulaire. L'imbrication (field sous form) reste du ressort de nesting.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from forge_design.design.models import DesignFile, DesignNode, PageRoot
from forge_design.limits import MAX_DESIGN_DEPTH, MAX_DESIGN_ISSUES, MAX_DESIGN_NODES

Location = tuple[str | int, ...]


@dataclass(frozen=True)
class FormFieldIssue:
    code: str
    message: str
    location: Location


@dataclass(frozen=True)
class FormFieldValidationResult:
    valid: bool
    issues: tuple[FormFieldIssue, ...]
    truncated: bool = False


def _definition_error(
    node: DesignNode | PageRoot, location: Location
) -> FormFieldIssue | None:
    if node.type == "field" and node.field is None:
        return FormFieldIssue(
            "design.field.missing_definition",
            "Un bloc field doit déclarer sa définition (name, input_type).",
            location,
        )
    if node.type != "field" and node.field is not None:
        return FormFieldIssue(
            "design.field.unsupported_definition",
            "Seul un bloc field peut porter une définition de champ.",
            (*location, "field"),
        )
    return None


def validate_form_fields(design: DesignFile) -> FormFieldValidationResult:
    """Parcours préfixe borné, racine comprise à profondeur zéro.

    Les noms sont uniques parmi les champs directs d'un même form ; deux
    formulaires distincts peuvent réutiliser un nom.
    """
    issues: list[FormFieldIssue] = []
    # Itérateur des enfants, chemin du parent, profondeur, noms du form parent.
    stack: list[
        tuple[
            Iterator[tuple[int, DesignNode | PageRoot]], Location, int, set[str] | None
        ]
    ] = [(iter(enumerate((design.root,))), (), 0, None)]
    inspected = 0
    while stack:
        iterator, parent_path, depth, form_names = stack[-1]
        entry = next(iterator, None)
        if entry is None:
            stack.pop()
            continue
        index, node = entry
        path = (*parent_path, "children", index) if parent_path else ("root",)
        found: list[FormFieldIssue] = []
        reason = None
        if inspected >= MAX_DESIGN_NODES:
            reason = "nombre de nœuds"
        elif depth > MAX_DESIGN_DEPTH:
            reason = "profondeur"
        else:
            inspected += 1
            error = _definition_error(node, path)
            if error is not None:
                found.append(error)
            if form_names is not None and node.type == "field" and node.field:
                name = node.field.name
                if name in form_names:
                    found.append(
                        FormFieldIssue(
                            "design.field.duplicate_name",
                            "Nom de champ déjà utilisé dans ce formulaire.",
                            (*path, "field", "name"),
                        )
                    )
                form_names.add(name)
            for issue in found:
                if len(issues) >= MAX_DESIGN_ISSUES:
                    reason = "nombre de diagnostics"
                    break
                issues.append(issue)
        if reason is not None:
            # La borne inclut le marqueur : conserver le préfixe des diagnostics.
            if len(issues) == MAX_DESIGN_ISSUES:
                issues.pop()
            issues.append(
                FormFieldIssue(
                    "design.field.analysis_truncated",
                    f"Analyse interrompue : limite de {reason} atteinte.",
                    path,
                )
            )
            return FormFieldValidationResult(False, tuple(issues), truncated=True)
        if node.children:
            names: set[str] | None = set() if node.type == "form" else None
            stack.append((iter(enumerate(node.children)), path, depth + 1, names))
    return FormFieldValidationResult(not issues, tuple(issues))
