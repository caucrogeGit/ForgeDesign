"""Adaptateur du Bridge des erreurs runtime."""

from dataclasses import dataclass, field
from pathlib import Path

from forge_design.forge.debug_errors import DebugErrorsResult, read_debug_errors


@dataclass(frozen=True)
class DebugCenterTool:
    id: str = field(default="debug-center", init=False)
    name: str = field(default="Debug Center", init=False)
    description: str = field(
        default="Lire les erreurs runtime de développement d’un projet Forge.",
        init=False,
    )

    def run(self, project_root: Path) -> DebugErrorsResult:
        return read_debug_errors(project_root)
