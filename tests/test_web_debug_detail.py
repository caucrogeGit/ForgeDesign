"""Contrat du détail, liens, données masquées et relecture stateless."""

import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from core.http.request import Request
from test_debug_errors import encoded, journal
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.current_project import CurrentProjectContext
from forge_design.forge.debug_errors import DebugErrorsResult, read_debug_errors
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import MAX_DEBUG_LINE_BYTES
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.recent_projects import RecentProjects
from forge_design.tools.debug_center import DebugCenterTool
from forge_design.tools.project_inspector import ProjectInspection
from forge_design.web import debug_detail


def request(query: str) -> Request:
    return Request(
        SimpleNamespace(
            command="GET",
            path="/debug/event?" + query,
            headers={},
            client_address=("127.0.0.1", 1234),
        )
    )


INVALID = [
    "id=x",
    "line=1",
    "line=&id=x",
    "line=1&id=",
    "line=0&id=x",
    "line=-1&id=x",
    "line=abc&id=x",
    "line=1000000000&id=x",
    "line=+1&id=x",
    urlencode({"line": "١", "id": "x"}),
    "line=1&id=x&foo=bar",
    "line=1&line=1&id=x",
    "line=1&id=x&id=x",
]


@pytest.mark.parametrize("query", INVALID)
def test_invalid_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    root = project(tmp_path / "project")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Must validate before Tool")

    monkeypatch.setattr(DebugCenterTool, "run", forbidden)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        for opened in (False, True):
            if opened:
                call(app, "/inspector", method="POST", value=str(root))
            status, html, headers = call(app, "/debug/event?" + query)
            assert status == 400 and headers["Cache-Control"] == "no-store"
            assert 'role="alert"' in html


def test_parser_bounds_and_unchanged_id() -> None:
    identifier = ' É /?&+" '
    assert debug_detail.parse_debug_detail(
        request(urlencode({"line": "0001", "id": identifier}))
    ) == (1, identifier)
    assert debug_detail.parse_debug_detail(request("line=&line=1&id=&id=x")) == (1, "x")
    assert debug_detail.parse_debug_detail(request("line=999999999&id=x")) == (
        999999999,
        "x",
    )
    assert (
        len(
            debug_detail.parse_debug_detail(
                request("line=1&id=" + "x" * MAX_DEBUG_LINE_BYTES)
            )[1]
        )
        == MAX_DEBUG_LINE_BYTES
    )
    with pytest.raises(ValueError):
        debug_detail.parse_debug_detail(
            request("line=1&id=" + "x" * (MAX_DEBUG_LINE_BYTES + 1))
        )


def links(html: str) -> list[str]:
    document = SvgDocument()
    document.feed(html)
    return [
        a["href"] or ""
        for t, a in document.tags
        if t == "a" and a.get("href") and (a["href"] or "").startswith("/debug/event?")
    ]


def test_occurrences_append_rewrite_and_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    path = journal(
        root,
        encoded(id="same &/?+", message="first-event")
        + encoded(id="same &/?+", message="second-event", safe_for_display=True),
    )
    calls: list[Path] = []

    def run(self: DebugCenterTool, root: Path) -> DebugErrorsResult:
        calls.append(root)
        return read_debug_errors(root)

    monkeypatch.setattr(DebugCenterTool, "run", run)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        status, html, headers = call(app, "/debug/event?line=1&id=x")
        assert status == 409 and "Aucun projet ouvert." in html and not calls
        assert headers["Cache-Control"] == "no-store"
        call(app, "/inspector", method="POST", value=str(root))
        html = call(app, "/debug?level=ERROR")[1]
        urls = links(html)
        assert len(urls) == 2 and urls[0] != urls[1]
        assert parse_qs(urlsplit(urls[0]).query) == {"line": ["1"], "id": ["same &/?+"]}
        assert "2 événements affichés sur 2" in html and ">Détail<" in html
        for index, url in enumerate(urls):
            before_calls = len(calls)
            before = {
                p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
                for p in tmp_path.rglob("*")
                if p.is_file()
            }
            status, html, headers = call(app, url)
            assert status == 200 and len(calls) == before_calls + 1
            assert headers["Cache-Control"] == "no-store"
            assert ("first-event" in html) == (index == 0)
            assert ("second-event" in html) == (index == 1)
            assert ("<dd>Oui</dd>" if index else "<dd>Non</dd>") in html
            assert "Aucune information de requête disponible." in html
            assert "Aucune traceback structurée disponible." in html
            assert 'href="/debug" aria-current="page"' in html
            assert "Retour au Debug Center" in html and "route-filters" not in html
            assert before == {
                p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
                for p in tmp_path.rglob("*")
                if p.is_file()
            }
        path.write_bytes(path.read_bytes() + encoded(id="new"))
        assert call(app, urls[0])[0] == 200
        assert call(app, "/debug/event?line=3&id=new")[0] == 200
        path.write_bytes(encoded(id="new") + encoded(id="same &/?+"))
        before_calls = len(calls)
        status, html, headers = call(app, urls[0])
        assert status == 404 and len(calls) == before_calls + 1
        assert "Cet événement n’est plus disponible" in html
        assert headers["Cache-Control"] == "no-store"
        assert call(app, "/debug/event?line=2&id=new")[0] == 404
        assert call(app, "/debug/event?line=99&id=new")[0] == 404
        assert call(app, urls[0], method="POST")[0] == 405


def test_full_hostile_detail_and_truncated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    hostile = '"><script>alert(1)</script>&'
    frame = {"file": hostile + "file", "line": 4, "function": hostile + "function"}
    values: dict[str, object] = {
        key: hostile
        for key in ("id", "route", "controller", "template", "correlation_id")
    }
    values.update(
        message=hostile + " Authorization: Bearer super-secret",
        hint=hostile + " password=secret123",
        sql=hostile + " password=secret123",
        request={
            "method": "POST",
            "path": hostile,
            "query": hostile + "&password=secret123",
            "post_keys": ["password"],
            "headers": ["Host"],
        },
        location=frame,
        traceback=[frame, {"file": "last-frame", "line": 8, "function": "last"}],
    )
    journal(root, encoded(**values))

    def run(self: DebugCenterTool, root: Path) -> DebugErrorsResult:
        return replace(read_debug_errors(root), truncated=True)

    monkeypatch.setattr(DebugCenterTool, "run", run)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        url = links(call(app, "/debug")[1])[0]
        status, html, headers = call(app, url)
        assert status == 200 and headers["Cache-Control"] == "no-store"
        for text in (
            "Résumé",
            "Requête HTTP",
            "Contexte Forge",
            "Localisation",
            "Traceback",
            "Piste Forge",
            "SQL",
            "Correlation ID",
            "Lecture partielle du journal.",
            '<pre class="source-code"><code>',
            "password",
            "Host",
            "[masqué]",
        ):
            assert text in html
        assert (
            "super-secret" not in html
            and "secret123" not in html
            and "<script" not in html
        )
        assert "schema_version" not in html and "/source?" not in html
        document = SvgDocument()
        document.feed(html)
        assert any(
            a.get("data-event-id") == hostile and a.get("data-event-line") == "1"
            for _, a in document.tags
        )
        assert html.index("file") < html.index("last-frame")
        assert hostile in "".join(document.text)
        status, html, headers = call(app, "/debug/event?line=3000&id=absent")
        assert status == 404 and "Lecture partielle du journal." in html
        assert headers["Cache-Control"] == "no-store"


def test_tool_errors_and_no_raw_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = CurrentProjectContext()
    context.set_project(ProjectInspection(tmp_path, True, None, None, (), ()))
    registry = ToolRegistry()
    registry.register(DebugCenterTool())

    def fail(self: DebugCenterTool, root: Path) -> DebugErrorsResult:
        raise NotForgeProjectError("project-unavailable")

    monkeypatch.setattr(DebugCenterTool, "run", fail)
    response = debug_detail.show_debug_detail(request("line=1&id=x"), context, registry)
    assert response.status == 200  # Same project-error policy as the list.

    def wrong(self: DebugCenterTool, root: Path) -> str:
        return "wrong type"

    monkeypatch.setattr(DebugCenterTool, "run", wrong)
    with pytest.raises(TypeError, match="DebugErrorsResult"):
        debug_detail.show_debug_detail(request("line=1&id=x"), context, registry)
    tree = ast.parse(Path(debug_detail.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "json"
            assert all(
                n.name not in {"read_debug_errors", "redact_debug_text"}
                for n in node.names
            )
        if isinstance(node, ast.Import):
            assert all(n.name != "json" for n in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "asdict", "repr"}
