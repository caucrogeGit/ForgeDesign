"""Projet courant en mémoire, propriété d'une instance d'application."""

from pathlib import Path

from forge_design.tools.project_inspector import ProjectInspection


class CurrentProjectContext:
    """Conserver uniquement un diagnostic valide fourni par Project Inspector."""

    def __init__(self) -> None:
        self._inspection: ProjectInspection | None = None

    @property
    def inspection(self) -> ProjectInspection | None:
        return self._inspection

    @property
    def root(self) -> Path | None:
        return self._inspection.root if self._inspection is not None else None

    def set_project(self, inspection: ProjectInspection) -> None:
        """Accepter la racine canonique du Tool, sans nouvelle lecture du projet."""
        if not inspection.valid:
            raise ValueError("Un projet courant doit être reconnu par Inspector.")
        self._inspection = inspection

    def clear(self) -> None:
        self._inspection = None
