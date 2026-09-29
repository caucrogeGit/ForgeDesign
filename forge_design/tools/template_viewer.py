"""Adaptateur du Bridge des templates physiques locaux."""

from dataclasses import dataclass, field
from pathlib import Path

from forge_design.forge.templates import TemplatesResult, read_templates


@dataclass(frozen=True)
class TemplateViewerTool:
    id: str = field(default="template-viewer", init=False)
    name: str = field(default="Template Viewer", init=False)
    description: str = field(
        default="Lire les templates locaux d’un projet Forge.", init=False
    )

    def run(self, project_root: Path) -> TemplatesResult:
        return read_templates(project_root)
