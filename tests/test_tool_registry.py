"""Enregistrement explicite et collection hétérogène de Tools."""

from dataclasses import dataclass
from pathlib import Path
from typing import assert_type

import pytest

from forge_design.platform.tool import Tool
from forge_design.platform.tool_registry import (
    DuplicateToolError,
    ToolRegistry,
    UnknownToolError,
)
from forge_design.tools.project_inspector import ProjectInspectorTool, inspect_project


@dataclass(frozen=True)
class FakeTool:
    id: str = "fake-tool"
    name: str = "Fake Tool"
    description: str = "Retourner un nom sans accéder au projet."

    def run(self, project_root: Path) -> str:
        return project_root.name


def test_empty() -> None:
    assert ToolRegistry().list() == ()


def test_register_get_list() -> None:
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)
    assert registry.get("fake-tool") is tool
    assert registry.list() == (tool,)
    assert_type(registry.get("fake-tool"), Tool[object])
    assert_type(registry.list(), tuple[Tool[object], ...])


def test_insertion_order() -> None:
    registry = ToolRegistry()
    first, second = FakeTool("z-tool"), FakeTool("a-tool")
    registry.register(first)
    registry.register(second)
    assert registry.list() == (first, second)
    assert registry.list() == registry.list()
    assert registry.get("a-tool") is second


@pytest.mark.parametrize("same_instance", [True, False])
def test_duplicate_does_not_replace(same_instance: bool) -> None:
    registry = ToolRegistry()
    original = FakeTool()
    registry.register(original)
    duplicate = original if same_instance else FakeTool(name="Other")
    with pytest.raises(DuplicateToolError, match="fake-tool"):
        registry.register(duplicate)
    assert registry.get("fake-tool") is original
    assert registry.list() == (original,)


def test_unknown() -> None:
    registry = ToolRegistry()
    with pytest.raises(UnknownToolError) as error:
        registry.get("missing")
    assert error.value.args == ("missing",)
    assert registry.list() == ()


@pytest.mark.parametrize(
    "tool_id",
    [
        "",
        " ",
        "Upper",
        "snake_case",
        "-tool",
        "tool-",
        "two--parts",
        "a/b",
        "é-tool",
        "1tool",
    ],
)
def test_invalid_identifier(tool_id: str) -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="kebab-case"):
        registry.register(FakeTool(tool_id))
    assert registry.list() == ()


def test_single_word_and_digits() -> None:
    registry = ToolRegistry()
    registry.register(FakeTool("tool"))
    registry.register(FakeTool("tool-2"))
    assert tuple(tool.id for tool in registry.list()) == ("tool", "tool-2")


def test_snapshot_is_immutable_and_detached() -> None:
    registry = ToolRegistry()
    first, second = FakeTool("first"), FakeTool("second")
    registry.register(first)
    snapshot = registry.list()
    with pytest.raises(TypeError):
        # Vérification dynamique volontaire d'une opération interdite par le type.
        snapshot[0] = second  # pyright: ignore[reportIndexIssue]
    registry.register(second)
    assert snapshot == (first,)
    assert registry.list() == (first, second)


def test_inspector_and_fake_after_lookup(tmp_path: Path) -> None:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).touch()
    (tmp_path / "mvc/routes").mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    registry = ToolRegistry()
    registry.register(ProjectInspectorTool())
    registry.register(FakeTool())
    result = registry.get("project-inspector").run(tmp_path)
    assert_type(result, object)
    assert result == inspect_project(tmp_path)
    assert registry.get("fake-tool").run(tmp_path) == tmp_path.name


def test_registry_does_not_run_tools() -> None:
    class NeverRun(FakeTool):
        def run(self, project_root: Path) -> str:
            raise AssertionError("Registry must not execute Tools")

    registry = ToolRegistry()
    tool = NeverRun()
    registry.register(tool)
    assert registry.get(tool.id) is tool
    assert registry.list() == (tool,)


def test_independent_registries() -> None:
    first, second = ToolRegistry(), ToolRegistry()
    first.register(FakeTool())
    assert second.list() == ()
