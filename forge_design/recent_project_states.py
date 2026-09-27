"""Instantanés des récents pour l'accueil, sans ouverture ni persistance."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.recent_projects import RecentProject
from forge_design.tools.project_inspector import ProjectInspection

RecentProjectStatus = Literal["available", "missing", "invalid", "unavailable"]


@dataclass(frozen=True)
class RecentProjectState:
    """État ponctuel ; is_current compare les racines sans actualiser le contexte."""

    project: RecentProject
    status: RecentProjectStatus
    inspection: ProjectInspection | None = None
    is_current: bool = False


def inspect_recent_projects(
    projects: tuple[RecentProject, ...],
    registry: ToolRegistry,
    current_root: Path | None = None,
) -> tuple[RecentProjectState, ...]:
    """Inspecter séquentiellement le tuple borné fourni par RecentProjects.

    Aucun accès au store ni au contexte mutable. Les seules erreurs absorbées
    sont celles du contrat de résolution du Project Inspector.
    """
    if not projects:
        return ()
    tool = registry.get("project-inspector")
    states: list[RecentProjectState] = []
    for project in projects:
        inspection = None
        status: RecentProjectStatus
        try:
            result = tool.run(Path(project.path))
        except ProjectRootNotFoundError:
            status = "missing"
        except ProjectRootNotDirectoryError:
            status = "invalid"
        except ProjectRootResolutionError:
            status = "unavailable"
        else:
            if not isinstance(result, ProjectInspection):
                raise TypeError("Project Inspector doit retourner ProjectInspection.")
            inspection = result
            status = "available" if result.valid else "invalid"
        states.append(
            RecentProjectState(
                project, status, inspection, Path(project.path) == current_root
            )
        )
    return tuple(states)
