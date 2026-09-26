"""Diagnostic de projet en lecture seule, composé à partir du Forge Bridge."""

from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import read_forge_version


@dataclass(frozen=True)
class ProjectInspection:
    """Validité structurelle, version déclarée et diagnostics du Bridge."""

    root: Path
    valid: bool
    forge_version: str | None
    forge_version_source: str | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def inspect_project(root: str | PathLike[str]) -> ProjectInspection:
    """Inspecter une racine sans importer le projet ni décider de sa compatibilité.

    Les erreurs de résolution restent propagées. Une structure non reconnue
    retourne son diagnostic sans lecture de version. Tout problème de version
    devient un avertissement, sans changer la validité structurelle.
    Les contrôles successifs du Bridge supposent un filesystem stable ; leurs
    exceptions inattendues ne sont pas masquées.
    """
    canonical = resolve_project_root(root)
    structure = detect_forge_project(canonical)
    if not structure.valid:
        return ProjectInspection(
            canonical, False, None, None, structure.errors, structure.warnings
        )

    version = read_forge_version(canonical)
    warnings = structure.warnings
    if version.status != "found":
        labels = {
            "absent": "Version Forge absente ou indéterminable.",
            "unreadable": "Version Forge illisible.",
            "conflict": "Déclarations de version Forge contradictoires.",
        }
        warnings += (labels[version.status],) + version.details
    return ProjectInspection(
        canonical,
        structure.valid,
        version.version,
        version.source,
        structure.errors,
        warnings,
    )
