"""Contrat Tool vérifié statiquement par Pyright et exercé via ses consommateurs."""

from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from typing import assert_type

import pytest

from forge_design.forge.project_root import ProjectRootNotFoundError
from forge_design.platform.tool import Tool
from forge_design.tools import project_inspector
from forge_design.tools.project_inspector import (
    ProjectInspection,
    ProjectInspectorTool,
    inspect_project,
)


def inspect_via_contract(
    tool: Tool[ProjectInspection], root: Path
) -> ProjectInspection:
    return tool.run(root)


def test_inspector_metadata() -> None:
    tool: Tool[ProjectInspection] = ProjectInspectorTool()
    assert tool.id == "project-inspector"
    assert tool.name == "Project Inspector"
    assert (
        tool.description == "Reconnaître un projet Forge et lire sa version déclarée."
    )


@pytest.mark.parametrize("attribute", ["id", "name", "description"])
def test_metadata_immutable(attribute: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(ProjectInspectorTool(), attribute, "changed")


@pytest.mark.parametrize("valid", [True, False])
def test_run_matches_business_api(tmp_path: Path, valid: bool) -> None:
    if valid:
        for name in ("app.py", "bootstrap.py", "config.py"):
            (tmp_path / name).touch()
        (tmp_path / "mvc/routes").mkdir(parents=True)
        (tmp_path / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    result = inspect_via_contract(ProjectInspectorTool(), tmp_path)
    assert_type(result, ProjectInspection)
    assert result == inspect_project(tmp_path)
    assert result.valid is valid


def test_delegates_once_without_bridge_logic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = ProjectInspection(tmp_path, True, None, None, (), ("diagnostic",))
    calls: list[Path] = []

    def inspect(root: Path) -> ProjectInspection:
        calls.append(root)
        return expected

    monkeypatch.setattr(project_inspector, "inspect_project", inspect)
    # Un chemin inexistant permet aussi de détecter une validation ajoutée au wrapper.
    root = tmp_path / "not-resolved"
    assert inspect_via_contract(ProjectInspectorTool(), root) is expected
    assert calls == [root]


def test_root_error_preserved(tmp_path: Path) -> None:
    with pytest.raises(ProjectRootNotFoundError):
        inspect_via_contract(ProjectInspectorTool(), tmp_path / "missing")


@dataclass(frozen=True)
class FakeTool:
    id: str = "fake-tool"
    name: str = "Fake Tool"
    description: str = "Retourner le nom du chemin sans accéder au projet."

    def run(self, project_root: Path) -> str:
        return project_root.name


def run_text_tool(tool: Tool[str], root: Path) -> str:
    return tool.run(root)


def test_minimal_fake_tool(tmp_path: Path) -> None:
    result = run_text_tool(FakeTool(), tmp_path / "example")
    assert_type(result, str)
    assert result == "example"
