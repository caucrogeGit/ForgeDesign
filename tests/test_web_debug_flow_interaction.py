"""Debug Center sur le Graphic Core : ressource Forge, contrat DOM et scène sûre."""

import json
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest
from test_debug_errors import encoded, journal
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.recent_projects import RecentProjects

ROOT = Path(__file__).resolve().parents[1]
HOSTILE = "</text><script>alert(1)</script>"
SQL = "SELECT name FROM users WHERE id = 42 -- sql-only-value"


def test_script_contract() -> None:
    script = files("forge_design.web").joinpath("static/debug-flow.js").read_text()
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
        "setInterval",
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "eval(",
        "new Function",
        "http://",
        "https://",
        "location.",
        ".style.",
        "createElementNS",
        "classList",
        "zoom",
        "minimap",
        "detailLevel",
    ):
        assert forbidden not in script, forbidden
    for expected in (
        'import { createGraphicEngine } from "./graphics/engine.js";',
        "JSON.parse(source.textContent)",
        "data-debug-flow",
        "Étape sélectionnée : ",
    ):
        assert expected in script


def test_client_suite_runs_with_the_shared_engine() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible ; contrats HTTP et source conservés.")
    subprocess.run(
        [node, "--check", str(ROOT / "forge_design/web/static/debug-flow.js")],
        check=True,
        timeout=10,
    )
    result = subprocess.run(
        [node, "--test", str(ROOT / "tests/js/graphics/debug-client.test.mjs")],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_http_scene_fallback_and_asset(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    journal(
        root,
        encoded(
            route=HOSTILE,
            controller="Home.index",
            sql=SQL,
            template="home.html",
            request={"method": "GET", "path": "/", "query": "q=1"},
        )
        + encoded(id="empty", message="sans étape"),
    )
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        status, html, headers = call(app, "/debug/event?line=1&id=same")
        assert status == 200
        assert "script-src 'self'" in headers["Content-Security-Policy"]
        assert "unsafe-inline" not in headers["Content-Security-Policy"]
        dom = SvgDocument()
        dom.feed(html)
        scripts = [attrs for tag, attrs in dom.tags if tag == "script"]
        assert scripts == [
            {"type": "application/json", "data-graphic-scene": None},
            {"type": "module", "src": "/debug-flow.js"},
        ]
        fallback = [a for _, a in dom.tags if "data-graphic-fallback" in a]
        assert len(fallback) == 1 and "hidden" not in fallback[0]
        assert any("data-debug-flow" in a for _, a in dom.tags)
        assert any("data-graphic-host" in a for _, a in dom.tags)
        assert "Ce schéma ne constitue pas une trace d’exécution." in html
        payload = html.split("data-graphic-scene>", 1)[1].split("</script>", 1)[0]
        assert "<" not in payload and ">" not in payload and "&" not in payload
        scene = json.loads(payload)
        fallback_ids = [
            a["id"] for t, a in dom.tags if t == "g" and "data-node-kind" in a
        ]
        assert (
            [n["id"] for n in scene["nodes"]]
            == fallback_ids
            == [
                "debug-node-request",
                "debug-node-router",
                "debug-node-controller",
                "debug-node-sql",
                "debug-node-template",
            ]
        )
        assert scene["nodes"][1]["label"] == "Route — " + HOSTILE
        # La requête SQL complète reste dans sa section, jamais dans la scène.
        assert "sql-only-value" not in payload and "SELECT" not in payload
        assert "sql-only-value" in html
        assert "Requête disponible" in payload
        # Le texte hostile du repli est échappé par Jinja.
        assert "<script>alert(1)</script>" not in html
        status, body, headers = call(app, "/debug-flow.js")
        assert status == 200
        assert headers["Content-Type"] == "text/javascript; charset=utf-8"
        assert "mountDebugFlow" in body
        # Aucune étape : ni scène, ni client, ni hôte de moteur.
        status, html, _ = call(app, "/debug/event?line=2&id=empty")
        assert status == 200
        assert "Aucun flux structuré disponible pour cet événement." in html
        assert "data-graphic-scene" not in html and "/debug-flow.js" not in html
        assert "data-graphic-host" not in html and "data-debug-flow" not in html
