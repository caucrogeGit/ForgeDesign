"""Cinquième Tool explicite, sans lecture au démarrage."""

from pathlib import Path

import pytest

from forge_design.app import create_tool_registry
from forge_design.forge.templates import TemplatesResult
from forge_design.tools import template_viewer
from forge_design.web.server import create_application


def test_contract_and_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    result = TemplatesResult((), (), False, False)

    def read(root: Path) -> TemplatesResult:
        calls.append(root)
        return result

    monkeypatch.setattr(template_viewer, "read_templates", read)
    tool = template_viewer.TemplateViewerTool()
    create_application()
    assert not calls
    assert [t.id for t in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
    assert tool.id == "template-viewer" and tool.name == "Template Viewer"
    assert tool.description == "Lire les templates locaux d’un projet Forge."
    assert tool.run(tmp_path) is result and calls == [tmp_path]
