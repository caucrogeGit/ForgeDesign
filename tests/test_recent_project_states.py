"""Projection des récents via le registre, sans mutation de leur état durable."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.recent_project_states import inspect_recent_projects
from forge_design.recent_projects import RecentProject, RecentProjects
from forge_design.tools.project_inspector import ProjectInspection


class InspectorDouble:
    id = "project-inspector"
    name = "Inspector double"
    description = "Résultats contrôlés et appels enregistrés."

    def __init__(self, results: dict[Path, object]) -> None:
        self.results = results
        self.calls: list[Path] = []

    def run(self, project_root: Path) -> object:
        self.calls.append(project_root)
        result = self.results[project_root]
        if isinstance(result, Exception):
            raise result
        return result


def test_states_registry_order_current_and_immutability(tmp_path: Path) -> None:
    roots = [tmp_path / str(i) for i in range(6)]
    valid = ProjectInspection(roots[0], True, "1.0.0rc9", "requirements.txt", (), ())
    unknown = ProjectInspection(roots[1], True, None, None, (), ("unknown",))
    invalid = ProjectInspection(roots[2], False, None, None, ("invalid",), ())
    results: list[object] = [
        valid,
        unknown,
        invalid,
        ProjectRootNotFoundError(),
        ProjectRootNotDirectoryError(),
        ProjectRootResolutionError(),
    ]
    inspector = InspectorDouble(dict(zip(roots, results)))
    registry = ToolRegistry()
    registry.register(inspector)
    context = CurrentProjectContext()
    context.set_project(valid)
    store = RecentProjects(tmp_path / "config/recent.json")
    for root in reversed(roots):
        store.add(root)
    before = store.path.read_bytes(), store.path.stat().st_mtime_ns
    projects = store.list()
    states = inspect_recent_projects(projects, registry, context.root)
    assert inspector.calls == roots
    assert [s.status for s in states] == [
        "available",
        "available",
        "invalid",
        "missing",
        "invalid",
        "unavailable",
    ]
    assert tuple(s.project for s in states) == projects == store.list()
    assert states[0].inspection is valid and states[1].inspection is unknown
    assert [s.is_current for s in states] == [True, False, False, False, False, False]
    assert context.inspection is valid
    assert before == (store.path.read_bytes(), store.path.stat().st_mtime_ns)
    with pytest.raises(FrozenInstanceError):
        setattr(states[0], "status", "missing")
    # Une nouvelle inspection ne remplace pas le diagnostic courant en mémoire.
    inspector.results[roots[0]] = ProjectRootNotFoundError()
    again = inspect_recent_projects(projects, registry, context.root)
    assert again[0].status == "missing" and again[0].is_current
    assert context.inspection is valid


def test_empty_does_not_even_look_up_tool() -> None:
    assert inspect_recent_projects((), ToolRegistry()) == ()


@pytest.mark.parametrize("result", [RuntimeError("unexpected"), object()])
def test_unexpected_results_are_not_hidden(result: object) -> None:
    root = Path("/project")
    registry = ToolRegistry()
    registry.register(InspectorDouble({root: result}))
    with pytest.raises(RuntimeError if isinstance(result, RuntimeError) else TypeError):
        inspect_recent_projects((RecentProject(str(root)),), registry)
