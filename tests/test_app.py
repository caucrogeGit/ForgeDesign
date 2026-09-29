"""Composition des instances intégrées, sans état partagé ni exécution implicite."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from forge_design.app import create_tool_registry
from forge_design.platform.tool_registry import ToolRegistry, UnknownToolError
from forge_design.tools import project_inspector
from forge_design.tools.entity_explorer import EntityExplorerTool
from forge_design.tools.project_inspector import ProjectInspection, ProjectInspectorTool
from forge_design.tools.route_explorer import RouteExplorerTool


def test_registry_contains_four_tools() -> None:
    registry = create_tool_registry()
    assert isinstance(registry, ToolRegistry)
    assert tuple(tool.id for tool in registry.list()) == (
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
    )
    tool = registry.get("project-inspector")
    assert isinstance(tool, ProjectInspectorTool)
    assert tool is registry.list()[0]


def test_registered_inspector_runs(tmp_path: Path) -> None:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).touch()
    (tmp_path / "mvc/routes").mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    result = create_tool_registry().get("project-inspector").run(tmp_path)
    assert isinstance(result, ProjectInspection)
    assert result.valid and result.errors == ()
    assert result.root == tmp_path.resolve()
    assert result.forge_version == "1.0.0rc9"
    assert result.forge_version_source == "requirements.txt"


@dataclass(frozen=True)
class FakeTool:
    id: str = "test-tool"
    name: str = "Test Tool"
    description: str = "Faux Tool réservé aux tests."

    def run(self, project_root: Path) -> str:
        return project_root.name


def test_compositions_are_independent() -> None:
    first, second = create_tool_registry(), create_tool_registry()
    assert first is not second
    assert first.get("project-inspector") is not second.get("project-inspector")
    first.register(FakeTool())
    assert tuple(tool.id for tool in first.list()) == (
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "test-tool",
    )
    assert tuple(tool.id for tool in second.list()) == (
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
    )
    with pytest.raises(UnknownToolError):
        second.get("test-tool")
    # Une composition ultérieure ne récupère pas l'état modifié de la première.
    assert tuple(tool.id for tool in create_tool_registry().list()) == (
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
    )


def test_composition_does_not_execute_inspector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Composition must not inspect a project")

    monkeypatch.setattr(EntityExplorerTool, "run", forbidden)
    monkeypatch.setattr(RouteExplorerTool, "run", forbidden)
    monkeypatch.setattr(ProjectInspectorTool, "run", forbidden)
    monkeypatch.setattr(project_inspector, "inspect_project", forbidden)
    assert len(create_tool_registry().list()) == 4
