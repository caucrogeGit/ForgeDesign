"""Minicarte : module générique servi par Forge, CSS sans métier, aucun canvas."""

import re
from pathlib import Path

from forge_design.web.server import GRAPHICS_MODULES

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "forge_design/web/static"
PREFIXES = (".gx-stage", ".gx-minimap")


def _minimap_css() -> str:
    css = (STATIC / "shell.css").read_text(encoding="utf-8")
    lines = css[css.index("FD-GRAPHICS-007") :].splitlines()[1:]
    block: list[str] = []
    for line in lines:
        if not line.startswith(PREFIXES):
            break
        block.append(line)
    assert block
    return "\n".join(block)


def test_module_is_in_the_closed_list() -> None:
    assert "minimap" in GRAPHICS_MODULES
    assert (STATIC / "graphics/minimap.js").read_text().startswith("// Graphic Core")


def test_minimap_css_is_generic_local_and_respects_hidden() -> None:
    css = _minimap_css()
    assert ".gx-minimap[hidden] { display: none; }" in css
    assert ".gx-stage { position: relative; }" in css
    assert "position: absolute" in css and "position: fixed" not in css
    assert "max-width: 40%" in css
    classes = set(re.findall(r"\.(gx-minimap[a-z-]*)", css))
    assert classes == {
        "gx-minimap",
        "gx-minimap-svg",
        "gx-minimap-scene",
        "gx-minimap-edges",
        "gx-minimap-nodes",
        "gx-minimap-viewport",
    }
    for word in ("route", "entity", "pivot", "handler", "controller", "template"):
        assert word not in css, word


def test_minimap_is_svg_without_canvas_text_or_globals() -> None:
    source = (STATIC / "graphics/minimap.js").read_text(encoding="utf-8")
    forbidden = (
        "getContext",
        'createElement("canvas")',
        "textContent",
        "document.querySelector",
        "window.",
    )
    for word in forbidden:
        assert word not in source, word
    assert "createElementNS" in source
    # Aucune variable de module mutable : seulement des constantes et des fonctions.
    assert not re.search(r"^(let|var) ", source, re.MULTILINE)
