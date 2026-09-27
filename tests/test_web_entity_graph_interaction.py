"""Ressource locale, contrat DOM et interaction sans dépendance navigateur."""

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
        "JSON.parse",
    ):
        assert forbidden not in script
    for expected in (
        "textContent",
        "data-entity-graph",
        "aria-pressed",
        '"Enter"',
        '" "',
        '"Escape"',
        "preventDefault()",
        "dataset.edgeLabel",
    ):
        assert expected in script


def test_script_execution() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible ; contrats HTTP et source conservés.")
    root = Path(__file__).resolve().parents[1]
    script = root / "forge_design/web/static/entity-graph.js"
    subprocess.run([node, "--check", str(script)], check=True, timeout=10)
    result = subprocess.run(
        [node, str(root / "tests/js/entity_graph_dom.cjs"), str(script)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert "isolation : OK" in result.stdout


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
        assert scripts == [{"src": "/entity-graph.js", "defer": None}]
        assert '<script src="/entity-graph.js" defer></script>' in html
        nodes = [attrs for _, attrs in dom.tags if "data-node-id" in attrs]
        edges = [attrs for _, attrs in dom.tags if "data-source-id" in attrs]
        assert len(nodes) == 3 and len(edges) == 2
        identities = {n["data-node-id"] for n in nodes}
        assert all(
            e["data-source-id"] in identities and e["data-target-id"] in identities
            for e in edges
        )
        assert all(
            n["role"] == "button"
            and n["tabindex"] == "0"
            and n["aria-pressed"] == "false"
            for n in nodes
        )
        assert nodes[0]["data-node-label"] == nodes[0]["data-node-table"] == hostile
        assert edges[0]["data-edge-label"] == hostile
        assert nodes[-1]["data-node-kind"] == "pivot"
        assert nodes[0]["aria-label"] == "Entité " + hostile
        for attr in (
            "data-entity-graph",
            "data-selection-status",
            "data-selection-details",
            "data-selection-clear",
            "data-selection-relations",
        ):
            assert any(attr in attrs for _, attrs in dom.tags)
        assert "<script>alert" not in html and "&lt;script&gt;alert" in html
        assert "<noscript>" in html and "Désélectionner" in html and "<table>" in html
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
