"""Résolution locale des seules références fournies, sans lecture ni parsing cible."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from forge_design.forge.source import (
    SourceReadError,
    inspect_project_source,
    template_source,
)
from forge_design.forge.template_structure import TemplateReference
from forge_design.limits import MAX_TEMPLATE_REFERENCES

NavigationStatus = Literal[
    "available", "dynamic", "invalid-path", "missing", "unreadable"
]


@dataclass(frozen=True)
class TemplateNavigation:
    reference: TemplateReference
    status: NavigationStatus
    target_path: str | None = None


def reference_rejection(reference: TemplateReference) -> TemplateNavigation | None:
    """Partie pure : une expression dynamique n'est jamais convertie en chemin."""
    if reference.dynamic or reference.path is None:
        return TemplateNavigation(reference, "dynamic")
    if template_source(reference.path) is None:
        return TemplateNavigation(reference, "invalid-path")
    return None


def resolve_template_references(
    root: Path, references: tuple[TemplateReference, ...]
) -> tuple[TemplateNavigation, ...]:
    """root canonique courant ; au plus 512 références, cache limité à cet appel.

    available confirme une ouverture régulière et bornée, pas l'UTF-8 ou la syntaxe.
    Ces derniers contrôles restent ceux de la consultation ultérieure de la source.
    """
    if len(references) > MAX_TEMPLATE_REFERENCES:
        raise ValueError("Trop de références pour une résolution locale.")
    states: dict[str, NavigationStatus] = {}
    result: list[TemplateNavigation] = []
    for reference in references:
        rejected = reference_rejection(reference)
        if rejected is not None:
            result.append(rejected)
            continue
        assert reference.path is not None
        path = reference.path
        if path not in states:
            try:
                inspect_project_source(root, "mvc/views/" + path)
            except FileNotFoundError:
                states[path] = "missing"
            except SourceReadError:
                states[path] = "unreadable"
            else:
                states[path] = "available"
        status = states[path]
        result.append(
            TemplateNavigation(
                reference, status, path if status == "available" else None
            )
        )
    return tuple(result)
