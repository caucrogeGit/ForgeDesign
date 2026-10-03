"""Ressource locale, contrat DOM et interaction sans dépendance navigateur."""

import json
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest
from test_entities import contract, entity
from test_entity_relations import many, write
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.recent_projects import RecentProjects


def test_script_contract() -> None:
    script = files("forge_design.web").joinpath("static/entity-graph.js").read_text()
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "document.cookie",
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "eval(",
        "new Function",
        "http://",
        "https://",
        "location.",
        "history.",
        ".style.",
        "createElementNS",
        "classList",
        "data-node-id",
        'addEventListener("keydown"',
    ):
        assert forbidden not in script, forbidden
    for expected in (
        'import { createGraphicEngine } from "./graphics/engine.js";',
        "JSON.parse(source.textContent)",
        "textContent",
        "data-entity-graph",
        "engine.edge(",
    ):
        assert expected in script


def test_client_suites_run_with_the_shared_engine() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible ; contrats HTTP et source conservés.")
    root = Path(__file__).resolve().parents[1]
    script = root / "forge_design/web/static/entity-graph.js"
    subprocess.run([node, "--check", str(script)], check=True, timeout=10)
    result = subprocess.run(
        [node, "--test", str(root / "tests/js/graphics/entity-client.test.mjs")],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_http_interaction_and_asset(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    hostile = '<script>alert(1)</script>"\\'
    data = contract()
    data.update(name=hostile, table=hostile)
    entity(root, "article", data)
    other = contract()
    other.update(name="Tag", table="tag")
    entity(root, "tag", other)
    declaration = many()
    declaration.update({"from": hostile, "name": hostile})
    write(root / "mvc/entities/relations.json", [declaration])
    with running(RecentProjects(tmp_path / "config/recent.json")) as app:
        assert "/entity-graph.js" not in call(app, "/entities")[1]
        call(app, "/inspector", method="POST", value=str(root))
        status, html, headers = call(app, "/entities")
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert "script-src 'self'" in headers["Content-Security-Policy"]
        assert "unsafe-inline" not in headers["Content-Security-Policy"]
        dom = SvgDocument()
        dom.feed(html)
        scripts = [attrs for tag, attrs in dom.tags if tag == "script"]
        assert scripts == [
            {"type": "application/json", "data-graphic-scene": None},
            {"type": "module", "src": "/entity-graph.js"},
        ]
        # Repli statique livré visible ; aucune identité ni interaction exposée.
        fallback = [a for _, a in dom.tags if "data-graphic-fallback" in a]
        assert len(fallback) == 1 and "hidden" not in fallback[0]
        assert not any("data-node-id" in attrs for _, attrs in dom.tags)
        assert not any(attrs.get("role") == "button" for _, attrs in dom.tags)
        payload = html.split("data-graphic-scene>", 1)[1].split("</script>", 1)[0]
        assert "<" not in payload and ">" not in payload and "&" not in payload
        scene = json.loads(payload)
        nodes, edges = scene["nodes"], scene["edges"]
        assert len(nodes) == 3 and len(edges) == 2
        identities = {n["id"] for n in nodes}
        assert all(
            e["source"] in identities and e["target"] in identities for e in edges
        )
        assert nodes[0]["data"]["name"] == nodes[0]["data"]["table"] == hostile
        assert nodes[0]["label"] == "Entité " + hostile
        assert edges[0]["data"] == {"kind": "many_to_many_from", "name": hostile}
        assert nodes[-1]["data"]["kind-label"] == "Pivot"
        assert nodes[-1]["presentation"]["variant"] == "category-2"
        for attr in (
            "data-entity-graph",
            "data-graphic-host",
            "data-graphic-fallback",
            "data-selection-status",
            "data-selection-details",
            "data-selection-clear",
            "data-selection-relations",
        ):
            assert any(attr in attrs for _, attrs in dom.tags)
        assert "<script>alert" not in html and "&lt;script&gt;alert" in html
        assert "La sélection du graphe nécessite JavaScript." in html
        assert "Désélectionner" in html and "<table>" in html
        status, script, headers = call(app, "/entity-graph.js")
        assert (
            status == 200
            and headers["Content-Type"] == "text/javascript; charset=utf-8"
        )
        assert (
            script
            == files("forge_design.web").joinpath("static/entity-graph.js").read_text()
        )
        assert call(app, "/entity-graph.js", method="POST")[0] == 405
