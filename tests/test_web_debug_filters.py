"""Contrats GET stateless, DOM et relecture du journal."""

from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode

import pytest
from test_debug_errors import encoded, journal
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.forge.debug_errors import DebugErrorsResult, read_debug_errors
from forge_design.recent_projects import RecentProjects
from forge_design.tools.debug_center import DebugCenterTool


def lines(html: str) -> list[int]:
    document = SvgDocument()
    document.feed(html)
    return [
        int(attrs["data-event-line"] or "0")
        for tag, attrs in document.tags
        if tag == "tr" and "data-event-line" in attrs
    ]


def fixture(root: Path) -> Path:
    return journal(
        root,
        encoded(
            id="duplicate",
            timestamp="2026-09-29T10:00:00Z",
            category="template",
            route="/users",
        )
        + b"broken\n"
        + encoded(
            id="duplicate",
            timestamp="2026-09-29T12:00:00Z",
            level="WARNING",
            request={"path": "/fallback"},
        )
        + encoded(timestamp="invalid", category="database", message="column"),
    )


@pytest.mark.parametrize(
    "query,expected",
    [
        ("", [3, 1, 4]),
        ("order=oldest", [1, 3, 4]),
        ("level=ERROR", [1, 4]),
        ("category=template", [1]),
        ("q=USERS", [1]),
        ("level=ERROR&category=database&q=column", [4]),
        ("q=missing", []),
        ("q=&q=users", [1]),
        ("q=&q=", [3, 1, 4]),
        ("level=&level=ERROR", [1, 4]),
    ],
)
def test_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str, expected: list[int]
) -> None:
    root = project(tmp_path / "project")
    fixture(root)
    calls: list[Path] = []

    def run(self: DebugCenterTool, path: Path) -> DebugErrorsResult:
        calls.append(path)
        return read_debug_errors(path)

    monkeypatch.setattr(DebugCenterTool, "run", run)
    with running(RecentProjects(tmp_path / "config/recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        before = {
            p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
            for p in tmp_path.rglob("*")
            if p.is_file()
        }
        status, html, headers = call(app, "/debug?" + query)
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert calls == [root] and lines(html) == expected
        assert f"{len(expected)} événements affichés sur 3" in html
        assert "debug.json_invalid" in html and "ligne 2" in html
        assert ("Aucun événement ne correspond aux filtres." in html) == (not expected)
        assert "Aucune erreur runtime enregistrée." not in html
        assert "<script" not in html
        assert before == {
            p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
            for p in tmp_path.rglob("*")
            if p.is_file()
        }
        assert lines(call(app, "/debug")[1]) == [3, 1, 4]


@pytest.mark.parametrize(
    "query",
    [
        "level=error",
        "level=FATAL",
        "category=security",
        "order=random",
        "foo=bar",
        "q=" + "x" * 257,
        urlencode({"q": "ß" * 129}),
        "q=a&q=a",
        "level=ERROR&level=INFO",
        "category=http&category=http",
        "order=newest&order=oldest",
    ],
)
def test_invalid_before_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    root = project(tmp_path / "project")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Tool must not run")

    monkeypatch.setattr(DebugCenterTool, "run", forbidden)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        for opened in (False, True):
            if opened:
                call(app, "/inspector", method="POST", value=str(root))
            status, html, headers = call(app, "/debug?" + query)
            assert status == 400 and headers["Cache-Control"] == "no-store"
            assert 'role="alert"' in html


def test_dom_xss_partial_and_reread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    hostile = '"><script>alert(1)</script>&'
    path = journal(
        root,
        encoded(
            id=hostile,
            route=hostile,
            exception_type=hostile,
            message=hostile,
            timestamp="2026-09-29T10:00:00Z",
        )
        + encoded(
            message="Authorization: Bearer very-secret", request={"path": "/fallback"}
        ),
    )

    def run(self: DebugCenterTool, root: Path) -> DebugErrorsResult:
        return replace(read_debug_errors(root), truncated=True)

    monkeypatch.setattr(DebugCenterTool, "run", run)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        assert "Aucun projet ouvert." in call(app, "/debug?q=users")[1]
        call(app, "/inspector", method="POST", value=str(root))
        html = call(app, "/debug")[1]
        assert "Lecture partielle du journal." in html and "/fallback" in html
        assert "very-secret" not in html and "<script" not in html
        document = SvgDocument()
        document.feed(html)
        assert any(a.get("data-event-id") == hostile for _, a in document.tags)
        assert html.count("&lt;script&gt;") == 4
        html = call(
            app,
            "/debug?"
            + urlencode(
                {
                    "q": hostile,
                    "level": "ERROR",
                    "category": "runtime",
                    "order": "oldest",
                }
            ),
        )[1]
        document = SvgDocument()
        document.feed(html)
        assert any(
            a.get("name") == "q" and a.get("value") == hostile.casefold()
            for _, a in document.tags
        )
        assert any(
            t == "form" and a.get("action") == "/debug" and a.get("method") == "get"
            for t, a in document.tags
        )
        for value in ("ERROR", "runtime", "oldest"):
            assert any(
                t == "option" and a.get("value") == value and "selected" in a
                for t, a in document.tags
            )
        assert "Aucun événement ne correspond" in call(app, "/debug?q=very-secret")[1]
        assert call(app, "/debug?" + urlencode({"q": "ß" * 128}))[0] == 200
        path.write_bytes(path.read_bytes() + encoded(timestamp="2026-09-30T10:00:00Z"))
        html = call(app, "/debug?level=ERROR")[1]
        assert lines(html) == [3, 1, 2] and "3 événements affichés sur 3" in html
        assert call(app, "/debug", method="POST")[0] == 405
