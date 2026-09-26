"""Invariant du contexte : racine et diagnostic restent une seule valeur."""

from pathlib import Path

import pytest

from forge_design.current_project import CurrentProjectContext
from forge_design.tools.project_inspector import ProjectInspection


def test_context_contract(tmp_path: Path) -> None:
    context = CurrentProjectContext()
    assert context.root is None and context.inspection is None
    diagnostic = ProjectInspection(tmp_path.resolve(), True, None, None, (), ())
    context.set_project(diagnostic)
    assert context.inspection is diagnostic and context.root == diagnostic.root
    with pytest.raises(ValueError):
        context.set_project(ProjectInspection(tmp_path, False, None, None, (), ()))
    assert context.inspection is diagnostic
    other = CurrentProjectContext()
    other.clear()
    assert context.inspection is diagnostic and other.root is None
    context.clear()
    assert context.root is None and context.inspection is None
