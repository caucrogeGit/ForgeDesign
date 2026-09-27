"""Contrats statiques et exécution JS légère sur un double DOM explicite."""

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest


def test_script_static_contract() -> None:
    script = files("forge_design.web").joinpath("static/route-graph.js").read_text()
    for forbidden in (
        "fetch",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "innerHTML",
        "https://",
        "http://",
        "history.",
        "location.",
        "document.cookie",
        "eval(",
        "new Function",
        ".style.",
    ):
        assert forbidden not in script
    for expected in (
        "textContent",
        '"Enter"',
        '" "',
        '"Escape"',
        "preventDefault()",
        "data-route-graph",
        "dataset.sourceId",
        "dataset.targetId",
        "aria-pressed",
    ):
        assert expected in script


def test_script_dom_interaction() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible ; contrats statiques conservés.")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            node,
            str(root / "tests/js/route_graph_dom.cjs"),
            str(root / "forge_design/web/static/route-graph.js"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert "isolation : OK" in result.stdout
