"""Frontière Forge MVC / Graphic Core : un seul serveur Forge, moteur navigateur."""

import re
from pathlib import Path

from forge_design.web.server import GRAPHICS_MODULES

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "forge_design"


def _sources() -> dict[Path, str]:
    return {path: path.read_text() for path in PACKAGE.rglob("*.py")}


def test_single_forge_mvc_composition() -> None:
    routers = [p for p, text in _sources().items() if re.search(r"\bRouter\(\)", text)]
    assert routers == [PACKAGE / "web/server.py"]
    server = (PACKAGE / "web/server.py").read_text()
    assert server.count("Router()") == 1
    assert "create_wsgi_app(application)" in server
    for path, text in _sources().items():
        # Aucun micro-serveur parallèle pour l'application Web de Forge Design.
        # Exception documentée hors de web/ : le proxy de preview réelle
        # (real_preview/proxy.py, FD-REALPREVIEW-003) relaie l'application cible.
        if path.is_relative_to(PACKAGE / "web"):
            assert "http.server" not in text, path
            assert "BaseHTTPRequestHandler" not in text, path


def test_graphics_assets_are_fixed_forge_routes() -> None:
    server = (PACKAGE / "web/server.py").read_text()
    assert GRAPHICS_MODULES == (
        "detail-level",
        "engine",
        "geometry",
        "minimap",
        "model",
        "scene",
        "svg-renderer",
        "viewport",
    )
    assert 'router.add(\n            "GET", f"/graphics/{module}.js"' in server
    static = PACKAGE / "web/static/graphics"
    assert sorted(p.stem for p in static.glob("*.js")) == sorted(GRAPHICS_MODULES)


def test_engine_has_no_server_side_counterpart() -> None:
    # Le moteur est du JavaScript navigateur : aucun module Python ne le duplique.
    for path, text in _sources().items():
        assert "createGraphicEngine" not in text, path
    assert not list(PACKAGE.rglob("*.mjs")) and not (ROOT / "package.json").exists()
