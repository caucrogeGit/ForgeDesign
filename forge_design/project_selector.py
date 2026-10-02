"""Sélection explicite : inspection, contexte runtime, puis historique local."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.recent_projects import RecentProjects, RecentProjectsError
from forge_design.tools.project_inspector import ProjectInspection

SelectionStatus = Literal[
    "selected", "invalid", "not-found", "not-directory", "resolution-error", "busy"
]


@dataclass(frozen=True)
class ProjectSelectionResult:
    status: SelectionStatus
    inspection: ProjectInspection | None = None
    error: str | None = None
    recent_warning: str | None = None


@dataclass(frozen=True)
class ProjectSelector:
    registry: ToolRegistry
    context: CurrentProjectContext
    recent_projects: RecentProjects
    # Appelé seulement quand un candidat valide va remplacer un autre projet :
    # False conserve le projet courant (statut "busy"). Ex. arrêt de la preview.
    before_change: Callable[[], bool] | None = None

    def open(self, path: Path) -> ProjectSelectionResult:
        """Réinspecter ; conserver le courant sur échec de validation uniquement."""
        try:
            inspection = self.registry.get("project-inspector").run(path)
        except ProjectRootNotFoundError as error:
            return ProjectSelectionResult("not-found", error=str(error))
        except ProjectRootNotDirectoryError as error:
            return ProjectSelectionResult("not-directory", error=str(error))
        except ProjectRootResolutionError as error:
            return ProjectSelectionResult("resolution-error", error=str(error))
        if not isinstance(inspection, ProjectInspection):
            raise TypeError("project-inspector doit retourner ProjectInspection.")
        if not inspection.valid:
            return ProjectSelectionResult("invalid", inspection)
        if (
            self.before_change is not None
            and self.context.root != inspection.root
            and not self.before_change()
        ):
            return ProjectSelectionResult(
                "busy",
                inspection,
                error="La preview réelle du projet courant n'a pas pu être arrêtée.",
            )
        self.context.set_project(inspection)
        warning = None
        try:
            self.recent_projects.add(inspection.root)
        except RecentProjectsError as error:
            warning = str(error)
        return ProjectSelectionResult("selected", inspection, recent_warning=warning)
