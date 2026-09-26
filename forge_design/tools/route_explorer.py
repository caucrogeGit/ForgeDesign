"""Adaptateur Tool pour la lecture des déclarations de routes."""

from dataclasses import dataclass, field
from pathlib import Path

from forge_design.forge.routes import RoutesResult, read_routes


@dataclass(frozen=True)
class RouteExplorerTool:
    id: str = field(default="route-explorer", init=False)
    name: str = field(default="Route Explorer", init=False)
    description: str = field(
        default="Lister les routes déclarées d’un projet Forge.", init=False
    )

    def run(self, project_root: Path) -> RoutesResult:
        return read_routes(project_root)
