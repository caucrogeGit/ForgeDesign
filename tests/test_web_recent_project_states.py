"""États HTTP, registre partagé et révalidation sans écriture au GET."""

from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_recent_project_states import InspectorDouble
from test_web_recent_projects import call, project, running

from forge_design.forge.project_root import ProjectRootResolutionError
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.recent_projects import RecentProjects
from forge_design.tools.project_inspector import ProjectInspection
from forge_design.web import server as web_server


class RecentEntries(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.entries: list[tuple[str, list[str]]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "li" and "data-recent-status" in values:
            self.entries.append((values["data-recent-status"] or "", []))
        if tag == "form" and self.entries:
            self.entries[-1][1].append(values.get("action") or "")


def snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


def test_states_actions_versions_and_nonwriting_get(tmp_path: Path) -> None:
    known = project(tmp_path / "known")
    unknown = project(tmp_path / "unknown")
    (unknown / "requirements.txt").unlink()
    missing = tmp_path / "missing"
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    store = RecentProjects(tmp_path / "config/recent.json")
    for root in (invalid, missing, unknown, known):
        store.add(root)
    open_action, remove = "/project/open-recent", "/project/recent/remove"
    with running(store) as app:
        before = snapshot(tmp_path)
        status, html, headers = call(app)
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert "Aucun projet ouvert." in html
        assert "Forge 1.0.0rc9" in html and "Version Forge indéterminée" in html
        assert "Projet introuvable" in html and "Projet non reconnu" in html
        assert RecentEntries(html).entries == [
            ("available", [open_action, remove]),
            ("available", [open_action, remove]),
            ("missing", [remove]),
            ("invalid", [remove]),
        ]
        assert snapshot(tmp_path) == before
        assert call(app, open_action, method="POST", value=str(known))[0] == 200
        before = snapshot(tmp_path)
        html = call(app)[1]
        assert "— Ouvert" in html
        assert RecentEntries(html).entries[0] == ("available", [remove])
        assert snapshot(tmp_path) == before
        # L'accueil constate la dégradation, sans fermer/actualiser le courant.
        (known / "app.py").unlink()
        before = snapshot(tmp_path)
        html = call(app)[1]
        assert "Aucun projet ouvert." not in html and "— Ouvert" in html
        assert RecentEntries(html).entries[0] == ("invalid", [remove])
        assert snapshot(tmp_path) == before
        for root in (missing, invalid, unknown):
            status, html, _ = call(app, remove, method="POST", value=str(root))
            assert status == 200 and "Aucun projet ouvert." not in html
        assert [p.path for p in store.list()] == [str(known)]


def test_get_uses_composed_registry_ten_calls_and_isolated_apps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RecentProjects(tmp_path / "config/recent.json")
    roots = [tmp_path / str(i) for i in range(10)]
    for root in reversed(roots):
        store.add(root)
    inspector = InspectorDouble(
        {root: ProjectInspection(root, True, None, None, (), ()) for root in roots}
    )
    registry = ToolRegistry()
    registry.register(inspector)
    monkeypatch.setattr(web_server, "create_tool_registry", lambda: registry)
    with (
        running(store) as app,
        running(RecentProjects(tmp_path / "other.json")) as other,
    ):
        assert inspector.calls == []  # Construction sans inspection implicite.
        assert call(other)[0] == 200 and inspector.calls == []
        assert call(app)[0] == 200 and inspector.calls == roots
        assert call(app)[0] == 200 and inspector.calls == roots * 2
        assert "Aucun projet ouvert." in call(other)[1]
        assert inspector.calls == roots * 2


def test_controlled_error_is_per_entry_and_not_exposed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RecentProjects(tmp_path / "config/recent.json")
    roots = [tmp_path / str(i) for i in range(2)]
    for root in reversed(roots):
        store.add(root)
    inspector = InspectorDouble(
        {
            roots[0]: ProjectRootResolutionError("private error content"),
            roots[1]: ProjectInspection(roots[1], True, None, None, (), ()),
        }
    )
    registry = ToolRegistry()
    registry.register(inspector)
    monkeypatch.setattr(web_server, "create_tool_registry", lambda: registry)
    with running(store) as app:
        status, html, headers = call(app)
        assert status == 200 and "Non disponible" in html
        assert "private error content" not in html
        assert headers["Cache-Control"] == "no-store"
        entries = RecentEntries(html).entries
        assert entries[0] == ("unavailable", ["/project/recent/remove"])
        assert entries[1][0] == "available" and inspector.calls == roots
