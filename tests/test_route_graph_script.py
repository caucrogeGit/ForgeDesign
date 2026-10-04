"""Graphic Core JavaScript et ses clients (Route, Entity) : contrats et Node."""

import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "forge_design/web/static"
GRAPHICS = (
    "detail-level",
    "engine",
    "geometry",
    "minimap",
    "model",
    "scene",
    "svg-renderer",
    "viewport",
)
SUITES = sorted((ROOT / "tests/js/graphics").glob("*.test.mjs"))


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible ; contrats statiques conservés.")
    return node


def test_packaged_modules_and_static_contract() -> None:
    package = files("forge_design.web")
    for name in GRAPHICS:
        source = package.joinpath(f"static/graphics/{name}.js").read_text()
        assert source.startswith("// Graphic Core")
        for forbidden in (
            "innerHTML",
            "outerHTML",
            "insertAdjacentHTML",
            "eval(",
            "new Function",
            "fetch(",
            "XMLHttpRequest",
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "http://",
            "https://",
            ".style",
            "window.",
            "globalThis",
        ):
            assert forbidden not in source.replace("http://www.w3.org/2000/svg", ""), (
                name,
                forbidden,
            )
    client = package.joinpath("static/route-graph.js").read_text()
    assert 'import { createGraphicEngine } from "./graphics/engine.js";' in client
    assert "textContent" in client and "innerHTML" not in client
    assert "JSON.parse(source.textContent)" in client


@pytest.mark.parametrize(
    "path",
    [STATIC / f"graphics/{name}.js" for name in GRAPHICS]
    + [STATIC / "route-graph.js", STATIC / "entity-graph.js", STATIC / "debug-flow.js"]
    + SUITES
    + [ROOT / "tests/js/graphics/fake-dom.mjs", ROOT / "tests/js/graphics/scenes.mjs"],
    ids=lambda path: path.name,
)
def test_node_check(path: Path) -> None:
    subprocess.run([_node(), "--check", str(path)], check=True, timeout=30)


def test_node_suites() -> None:
    assert len(SUITES) == 13
    result = subprocess.run(
        [_node(), "--test", *map(str, SUITES)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ℹ fail 0" in result.stdout
