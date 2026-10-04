"""Flux runtime : Graphic Core et repli SVG, sans étapes inventées ni lecture."""

import re
from pathlib import Path

import pytest
from test_debug_errors import encoded, journal
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.forge.debug_errors import DebugErrorsResult, read_debug_errors
from forge_design.recent_projects import RecentProjects
from forge_design.tools.debug_center import DebugCenterTool

# Depuis FD-GRAPHICS-008, seuls le bloc JSON inerte de la scène et le client
# du Graphic Core sont admis ; tout autre <script> trahirait une injection.
ALLOWED_SCRIPTS = {
    '<script type="application/json" data-graphic-scene>',
    '<script type="module" src="/debug-flow.js">',
}


def foreign_scripts(html: str) -> list[str]:
    return [
        tag
        for tag in re.findall(r"<script\b[^>]*>", html)
        if tag not in ALLOWED_SCRIPTS
    ]


@pytest.mark.parametrize(
    "fields,expected",
    [
        (
            ("request", "route", "controller", "sql", "template"),
            ["request", "router", "controller", "sql", "template"],
        ),
        (("request", "controller", "sql"), ["request", "controller", "sql"]),
        (("template",), ["template"]),
        ((), []),
    ],
)
def test_flow_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fields: tuple[str, ...],
    expected: list[str],
) -> None:
    root = project(tmp_path / "project")
    hostile = "<script>x</script>"
    values: dict[str, object] = {
        key: hostile + " password=secret-value" for key in fields
    }
    if "request" in fields:
        values["request"] = {
            "method": "POST",
            "path": hostile + " token=hidden-value",
            "query": "query-only",
        }
    values["traceback"] = [
        {"file": "mvc/models/user.py", "line": 1, "function": "save"}
    ]
    values["category"] = "database"
    path = journal(root, encoded(**values))
    calls: list[Path] = []

    def run(self: DebugCenterTool, root: Path) -> DebugErrorsResult:
        calls.append(root)
        return read_debug_errors(root)

    monkeypatch.setattr(DebugCenterTool, "run", run)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        status, html, _ = call(app, "/debug/event?line=1&id=same")
        assert status == 409 and "<svg" not in html and not calls
        call(app, "/inspector", method="POST", value=str(root))
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        status, html, headers = call(app, "/debug/event?line=1&id=same")
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert calls == [root] and before == (
            path.read_bytes(),
            path.stat().st_mtime_ns,
        )
        assert (
            not foreign_scripts(html)
            and "secret-value" not in html
            and "hidden-value" not in html
        )
        # Moteur seulement s'il y a des étapes ; sinon ni scène ni client.
        assert (html.count("data-graphic-scene") == 1) == bool(expected)
        assert ('src="/debug-flow.js"' in html) == bool(expected)
        doc = SvgDocument()
        doc.feed(html)
        kinds = [
            a["data-node-kind"]
            for t, a in doc.tags
            if t == "g" and "data-node-kind" in a
        ]
        assert kinds == expected
        assert (
            html.index("Résumé")
            < html.index("Flux runtime")
            < html.index("Requête HTTP")
        )
        assert "mvc/models/user.py" in html and "debug-node-model" not in html
        assert "debug-node-response" not in html and "Traceback" in html
        if expected:
            svg = html[html.index("<svg") : html.index("</svg>")]
            assert "query-only" not in svg and "password=" not in svg.replace(
                "password=[masqué]", ""
            )
            assert "SQL" not in svg or "Requête disponible" in svg
            assert any(
                t == "svg" and a.get("role") == "img" and a.get("aria-labelledby")
                for t, a in doc.tags
            )
            assert "<desc" in svg and "<title" in svg and "<marker" in svg
            assert svg.count('class="debug-flow-edge"') == len(expected) - 1
            xs = [int(a["x"] or "0") for t, a in doc.tags if t == "rect"]
            assert xs == sorted(xs) and len(set(xs)) == len(expected)
        else:
            assert "<svg" not in html
            assert "Aucun flux structuré disponible pour cet événement." in html
        for url, expected_status in (
            ("/debug/event?line=x&id=same", 400),
            ("/debug/event?line=99&id=same", 404),
        ):
            status, html, headers = call(app, url)
            assert status == expected_status and "<svg" not in html
            assert headers["Cache-Control"] == "no-store"
