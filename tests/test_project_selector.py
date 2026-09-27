"""Orchestration unique de sélection et ordre des mutations."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_recent_project_states import InspectorDouble

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.project_selector import ProjectSelector
from forge_design.recent_projects import RecentProjects, RecentProjectsError
from forge_design.tools.project_inspector import ProjectInspection


def setup_selector(tmp_path: Path, result: object) -> ProjectSelector:
    registry = ToolRegistry()
    registry.register(InspectorDouble({tmp_path / "input": result}))
    context = CurrentProjectContext()
    previous = ProjectInspection(tmp_path / "previous", True, None, None, (), ())
    context.set_project(previous)
    store = RecentProjects(tmp_path / "config/recent.json")
    store.add(previous.root)
    return ProjectSelector(registry, context, store)


def test_selection_canonical_replacement_recency_and_isolation(tmp_path: Path) -> None:
    inspection = ProjectInspection(tmp_path / "canonical", True, None, None, (), ())
    selector = setup_selector(tmp_path, inspection)
    other = setup_selector(tmp_path / "other", inspection)
    selector.recent_projects.add(inspection.root)
    selector.recent_projects.add(tmp_path / "previous")
    result = selector.open(tmp_path / "input")
    assert result.status == "selected" and result.inspection is inspection
    assert selector.context.inspection is inspection
    assert [p.path for p in selector.recent_projects.list()] == [
        str(inspection.root),
        str(tmp_path / "previous"),
    ]
    assert other.context.root == tmp_path / "other/previous"
    assert len(other.recent_projects.list()) == 1
    for obj, attr in ((result, "status"), (selector, "context")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, None)


def test_persistence_failure_after_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inspection = ProjectInspection(tmp_path / "canonical", True, None, None, (), ())
    selector = setup_selector(tmp_path, inspection)
    before = selector.recent_projects.path.read_bytes()

    def fail(root: Path) -> None:
        assert root == inspection.root and selector.context.inspection is inspection
        raise RecentProjectsError("write refused")

    monkeypatch.setattr(selector.recent_projects, "add", fail)
    result = selector.open(tmp_path / "input")
    assert result.status == "selected" and result.recent_warning == "write refused"
    assert selector.recent_projects.path.read_bytes() == before


@pytest.mark.parametrize(
    "failure,status",
    [
        (ProjectRootNotFoundError("missing"), "not-found"),
        (ProjectRootNotDirectoryError("file"), "not-directory"),
        (ProjectRootResolutionError("resolution"), "resolution-error"),
        (False, "invalid"),
        (RuntimeError("unexpected"), None),
        (object(), None),
    ],
)
def test_failures_preserve_context_and_history(
    tmp_path: Path, failure: object, status: str | None
) -> None:
    if failure is False:
        failure = ProjectInspection(tmp_path / "invalid", False, None, None, (), ())
    selector = setup_selector(tmp_path, failure)
    current = selector.context.inspection
    file = selector.recent_projects.path
    before = file.read_bytes(), file.stat().st_mtime_ns
    if status is None:
        with pytest.raises(
            RuntimeError if isinstance(failure, RuntimeError) else TypeError
        ):
            selector.open(tmp_path / "input")
    else:
        assert selector.open(tmp_path / "input").status == status
    assert selector.context.inspection is current
    assert before == (file.read_bytes(), file.stat().st_mtime_ns)
