"""Adaptateur du Bridge des contrats d’entités."""

from dataclasses import dataclass, field
from pathlib import Path

from forge_design.forge.entities import EntitiesResult, read_entities


@dataclass(frozen=True)
class EntityExplorerTool:
    id: str = field(default="entity-explorer", init=False)
    name: str = field(default="Entity Explorer", init=False)
    description: str = field(
        default="Inspecter les entités déclarées d’un projet Forge.", init=False
    )

    def run(self, project_root: Path) -> EntitiesResult:
        return read_entities(project_root)
