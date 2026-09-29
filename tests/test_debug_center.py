"""Délégation explicite du quatrième Tool."""

from pathlib import Path

import pytest

from forge_design.app import create_tool_registry
from forge_design.forge.debug_errors import DebugErrorsResult
from forge_design.tools import debug_center
from forge_design.web.server import create_application


def test_contract_and_delegation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    result = DebugErrorsResult()

    def read(root: Path) -> DebugErrorsResult:
        calls.append(root)
        return result

    monkeypatch.setattr(debug_center, "read_debug_errors", read)
    tool = debug_center.DebugCenterTool()
    create_application()
    assert not calls
    assert [t.id for t in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
    ]
    assert tool.id == "debug-center" and tool.name == "Debug Center"
    assert (
        tool.description
        == "Lire les erreurs runtime de développement d’un projet Forge."
    )
    assert tool.run(tmp_path) is result and calls == [tmp_path]
