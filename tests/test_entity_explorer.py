"""Tool typé et rendu HTTP indépendant de Route Explorer."""

from pathlib import Path

import pytest
from test_entities import contract, entity
from test_web_recent_projects import call, project, running

from forge_design.forge.entities import EntitiesResult
from forge_design.platform.tool import Tool
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.recent_projects import RecentProjects
from forge_design.tools import entity_explorer
from forge_design.tools.entity_explorer import EntityExplorerTool


def test_tool_contract_delegation(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = EntitiesResult()
    calls: list[Path] = []

    def read(root: Path) -> EntitiesResult:
        calls.append(root)
        return expected

    monkeypatch.setattr(entity_explorer, "read_entities", read)
    tool: Tool[EntitiesResult] = EntityExplorerTool()
    assert tool.id == "entity-explorer" and tool.name == "Entity Explorer"
    assert tool.description == "Inspecter les entités déclarées d’un projet Forge."
    assert tool.run(Path("/project")) is expected and calls == [Path("/project")]


def test_http_entities_and_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    data = contract()
    data["name"] = "<script>Contact</script>"
    data["fields"] = [
        {
            "name": "title",
            "type": "string",
            "max_length": 255,
            "default": "<script>default</script>",
        }
    ]
    target = entity(root, "contact", data)
    entity(root, "broken", {}).write_text("{")
    (root / "mvc/routes/__init__.py").write_text(
        "def register_routes(router):\n    pass\n"
    )
    store = RecentProjects(tmp_path / "config/recent.json")
    gets: list[str] = []
    original = ToolRegistry.get

    def get(self: ToolRegistry, tool_id: str) -> Tool[object]:
        gets.append(tool_id)
        return original(self, tool_id)

    monkeypatch.setattr(ToolRegistry, "get", get)
    with running(store) as app:
        status, html, headers = call(app, "/entities")
        assert status == 200 and "Aucun projet ouvert." in html and gets == []
        assert headers["Cache-Control"] == "no-store"
        assert call(app, "/entities", method="POST")[0] == 405
        call(app, "/inspector", method="POST", value=str(root))
        gets.clear()
        before = target.read_bytes(), target.stat().st_mtime_ns
        status, html, headers = call(app, "/entities")
        assert gets == ["entity-explorer"]
        assert status == 200 and headers["Cache-Control"] == "no-store"
        for value in (
            "<table>",
            "<details>",
            "title",
            "string",
            "255",
            "Timestamps",
            "Soft delete",
            "Diagnostics",
            "mvc/entities/contact/contact.json",
        ):
            assert value in html
        assert '<a href="/entities" aria-current="page">' in html
        assert "&lt;script&gt;Contact" in html and "<script>" not in html
        assert "/source?" not in html
        assert before == (target.read_bytes(), target.stat().st_mtime_ns)
        target.write_text("{")
        assert "Aucune entité interprétable." in call(app, "/entities")[1]
        assert call(app, "/routes")[0] == 200
        assert "Aucun projet ouvert." not in call(app, "/entities")[1]
