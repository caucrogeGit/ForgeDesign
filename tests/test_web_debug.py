"""Page serveur minimale du Debug Center."""

from pathlib import Path

import pytest
from test_debug_errors import encoded, journal
from test_web_recent_projects import call, project, running

from forge_design.forge.debug_errors import DebugErrorsResult, read_debug_errors
from forge_design.recent_projects import RecentProjects
from forge_design.tools.debug_center import DebugCenterTool


def test_debug_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []

    def run(self: DebugCenterTool, root: Path) -> DebugErrorsResult:
        calls.append(root)
        return read_debug_errors(root)

    monkeypatch.setattr(DebugCenterTool, "run", run)
    root = project(tmp_path / "project")
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        status, html, headers = call(app, "/debug")
        assert status == 200 and "Aucun projet ouvert." in html and not calls
        assert headers["Cache-Control"] == "no-store"
        assert call(app, "/inspector", method="POST", value=str(root))[0] == 200
        assert "Aucune erreur runtime enregistrée." in call(app, "/debug")[1]
        assert calls == [root]
        path = journal(
            root,
            encoded(message="<script>alert(1)</script>")
            + b"broken\n"
            + encoded(message="Authorization: Bearer very-secret"),
        )
        before = (path.read_bytes(), path.stat().st_size, path.stat().st_mtime_ns)
        status, html, headers = call(app, "/debug")
        assert status == 200 and len(calls) == 2
        assert (
            "2 événements affichés sur 2" in html and "1 anomalies de lecture" in html
        )
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "very-secret" not in html and "[masqué]" in html
        assert "debug.json_invalid" in html and "ligne 2" in html
        assert '<a href="/debug" aria-current="page">' in html
        assert "<script" not in html and headers["Cache-Control"] == "no-store"
        assert before == (
            path.read_bytes(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        path.write_bytes(path.read_bytes() + encoded())
        assert "3 événements affichés sur 3" in call(app, "/debug")[1]
        assert call(app, "/debug", method="POST")[0] == 405
        assert call(app, "/source?path=storage/logs/errors.dev.jsonl")[0] == 400
