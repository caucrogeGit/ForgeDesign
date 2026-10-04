"""Hôte Web des modules : navigation, pages GET exactes, assets, lecture par l'hôte."""

import json
import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

import pytest
from module_support import activation, prefix, witness_module, write_resource
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project

from forge_design.modules import ModuleActivation
from forge_design.recent_projects import RecentProjects
from forge_design.web.server import ForgeDesignServer, create_server

HOSTILE = "</script><svg onload=alert(1)>"
CORE_NAV = [
    "/",
    "/inspector",
    "/routes",
    "/entities",
    "/debug",
    "/templates",
    "/editor",
]


@contextmanager
def serving(
    tmp_path: Path, modules: ModuleActivation | None
) -> Generator[ForgeDesignServer, None, None]:
    store = RecentProjects(tmp_path / "config/recent.json")
    with create_server(port=0, recent_projects=store, modules=modules) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)


def navigation(html: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Liens de la navigation principale et de la zone Modules, dans l'ordre."""

    def zone(label: str) -> str:
        match = re.search(
            rf'<nav[^>]*aria-label="{label}"[^>]*>(.*?)</nav>', html, re.S
        )
        return match.group(1) if match else ""

    core = re.findall(r'<a href="([^"]+)"', zone("Navigation principale"))
    modules = [
        (href, "page" if current else "None")
        for href, current in re.findall(
            r'<a href="([^"]+)"( aria-current="page")?', zone("Modules")
        )
    ]
    return core, modules


def scripts(html: str) -> list[dict[str, str | None]]:
    doc = SvgDocument()
    doc.feed(html)
    return [attrs for tag, attrs in doc.tags if tag == "script"]


def resource(module_id: str, path: str, **extra: str) -> str:
    return f"/modules/{module_id}/resource?" + urlencode(
        {"type": "document", "path": path, **extra}
    )


def test_without_modules_nothing_is_exposed(tmp_path: Path) -> None:
    with serving(tmp_path, None) as app:
        status, html, _ = call(app, "/")
        core, modules = navigation(html)
        assert status == 200 and core == CORE_NAV and modules == []
        assert 'aria-label="Modules"' not in html
        assert "Modules non chargés" not in html
        for url in ("/modules/witness/", "/modules/", "/modules/witness/resource"):
            assert call(app, url)[0] == 404
        assert call(app, "/module-resource.js")[0] == 200


def test_absent_and_incompatible_modules_are_diagnosed_not_fatal(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    future = replace(witness_module("future"), api_version=99)
    modules = activation(("fd_absent", None), ("pkg_future", future))
    with serving(tmp_path, modules) as app:
        status, html, _ = call(app, "/")
        assert status == 200 and navigation(html)[1] == []
        assert "Modules non chargés" in html
        assert "fd_absent" in html and "module-missing" in html
        assert "pkg_future" in html and "api-incompatible" in html
        assert "Traceback" not in html
        assert call(app, "/modules/future/")[0] == 404
        # Les diagnostics restent sur l'accueil : les autres pages ne les répètent pas.
        assert "Modules non chargés" not in call(app, "/routes")[1]


def test_module_pages_resources_and_assets(tmp_path: Path) -> None:
    root = project(tmp_path / "projet")
    demo = write_resource(root, "witness", "demo", title=HOSTILE)
    nested = write_resource(root, "witness", "dossier/autre")
    modules = activation(
        ("pkg_witness", witness_module(probe=lambda: {"spice": False}))
    )
    with serving(tmp_path, modules) as app:
        status, html, headers = call(app, "/modules/witness/")
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert "Aucun projet ouvert." in html
        core, entries = navigation(html)
        assert core == CORE_NAV and entries == [("/modules/witness/", "page")]
        assert "script-src 'self'" in headers["Content-Security-Policy"]
        assert (
            '<link rel="stylesheet" href="/modules/witness/assets/witness.css">' in html
        )
        assert "Moteur de simulation" in html and "spice" in html
        call(app, "/inspector", method="POST", value=str(root))
        status, html, _ = call(app, "/modules/witness/")
        assert status == 200
        # Ordre lexical déterministe : « demo » précède « dossier/ ».
        assert html.index(demo) < html.index(nested)
        assert resource("witness", demo).replace("&", "&amp;") in html
        # Page ressource : métadonnées, scène inerte, client générique.
        status, html, headers = call(app, resource("witness", demo))
        assert status == 200 and headers["Cache-Control"] == "no-store"
        for text in (
            "witness",
            "document",
            demo,
            "Version du format",
            "0.1",
            "sha256:",
            "valide",
        ):
            assert text in html, text
        assert "La visualisation graphique nécessite JavaScript." in html
        assert scripts(html) == [
            {"type": "application/json", "data-graphic-scene": None},
            {"type": "module", "src": "/module-resource.js"},
        ]
        payload = html.split("data-graphic-scene>", 1)[1].split("</script>", 1)[0]
        assert "<" not in payload and ">" not in payload
        scene = json.loads(payload)
        assert [n["id"] for n in scene["nodes"]] == ["A", "B", "C"]
        assert scene["nodes"][0]["label"] == HOSTILE
        assert "<svg onload" not in html
        for word in ("Enregistrer", "Modifier", "Créer", "Supprimer", "<form"):
            assert word not in html.split("<main>", 1)[1], word
        # Asset exact, MIME fixé par le cœur ; tout le reste est 404.
        status, body, headers = call(app, "/modules/witness/assets/witness.css")
        assert status == 200 and headers["Content-Type"] == "text/css; charset=utf-8"
        assert ".gx-scene" in body
        for url in (
            "/modules/witness/assets/autre.css",
            "/modules/witness/assets/../../shell.css",
            "/modules/witness/assets/%2e%2e/witness.css",
            "/modules/witness/foo",
            "/modules/witness",
            "/modules/unknown/",
            "/modules/witness/actions/save",
        ):
            assert call(app, url)[0] == 404, url
        for url in ("/modules/witness/", "/modules/witness/resource"):
            assert call(app, url, method="POST")[0] == 405, url


@pytest.mark.parametrize(
    "query,status,message",
    [
        ({"type": "document"}, 400, "Chemin absent"),
        ({"path": "x"}, 400, "Type de ressource absent"),
        ({"type": "autre", "path": "x"}, 400, "Type de ressource inconnu"),
        ({"type": "document", "path": "x", "extra": "1"}, 400, "Paramètre inconnu"),
        ({"type": "document", "path": "x" * 5000}, 400, "trop long"),
        ({"type": "document", "path": "../../config.py"}, 400, "resource-refused"),
        (
            {"type": "document", "path": "mvc/witness/absent.witness.json"},
            404,
            "resource-not-found",
        ),
    ],
)
def test_resource_query_is_strict(
    tmp_path: Path, query: dict[str, str], status: int, message: str
) -> None:
    root = project(tmp_path / "projet")
    with serving(tmp_path, activation(("pkg", witness_module()))) as app:
        call(app, "/inspector", method="POST", value=str(root))
        got, html, headers = call(app, "/modules/witness/resource?" + urlencode(query))
        assert got == status and message in html
        assert headers["Cache-Control"] == "no-store"
        assert str(root) not in html.split("<main>", 1)[1]
        assert "data-graphic-scene" not in html


def test_duplicate_parameter_and_missing_project(tmp_path: Path) -> None:
    with serving(tmp_path, activation(("pkg", witness_module()))) as app:
        url = "/modules/witness/resource?type=document&type=document&path=x"
        assert call(app, url)[0] == 400
        status, html, _ = call(app, resource("witness", "mvc/witness/a.witness.json"))
        assert status == 409 and "Aucun projet ouvert." in html


def test_invalid_versions_and_failing_projection_are_displayed(tmp_path: Path) -> None:
    root = project(tmp_path / "projet")
    invalid = write_resource(root, "witness", "invalid", raw=b"{not json")
    future = write_resource(root, "witness", "future", version="9.9")
    good = write_resource(root, "witness", "good")

    def crash(document: object) -> object:
        raise RuntimeError("bug")

    modules = activation(
        ("pkg_ok", witness_module()),
        ("pkg_crash", witness_module("crashy", scene=crash)),
    )
    write_resource(root, "crashy", "good")
    with serving(tmp_path, modules) as app:
        call(app, "/inspector", method="POST", value=str(root))
        status, html, _ = call(app, resource("witness", invalid))
        assert (
            status == 200
            and "invalid-resource" in html
            and "data-graphic-scene" not in html
        )
        status, html, _ = call(app, resource("witness", future))
        assert status == 200 and "unsupported-version" in html and "9.9" in html
        status, html, _ = call(
            app, resource("crashy", f"{prefix('crashy')}/good.crashy.json")
        )
        assert status == 200
        assert "Projection graphique du module en échec (RuntimeError)." in html
        assert "Traceback" not in html and "data-graphic-scene" not in html
        # Le serveur continue de servir normalement.
        assert call(app, resource("witness", good))[0] == 200


def test_two_modules_are_isolated_and_ordered(tmp_path: Path) -> None:
    root = project(tmp_path / "projet")
    a = write_resource(root, "witness-a", "un")
    b = write_resource(root, "witness-b", "deux")
    modules = activation(
        ("pkg_b", witness_module("witness-b", label="Témoin B")),
        ("pkg_a", witness_module("witness-a", label="Témoin A")),
    )
    with serving(tmp_path, modules) as app:
        call(app, "/inspector", method="POST", value=str(root))
        html = call(app, "/routes")[1]
        assert [href for href, _ in navigation(html)[1]] == [
            "/modules/witness-b/",
            "/modules/witness-a/",
        ]
        page_a = call(app, "/modules/witness-a/")[1]
        page_b = call(app, "/modules/witness-b/")[1]
        assert a in page_a and b not in page_a
        assert b in page_b and a not in page_b
        assert call(app, "/modules/witness-a/assets/witness-a.css")[0] == 200
        assert call(app, "/modules/witness-a/assets/witness-b.css")[0] == 404
        # Une ressource d'un module n'est pas lisible par l'autre (espace de sources).
        assert call(app, resource("witness-a", b))[0] == 400


def test_project_change_uses_the_current_context_without_reactivation(
    tmp_path: Path,
) -> None:
    first = project(tmp_path / "premier")
    second = project(tmp_path / "second")
    one = write_resource(first, "witness", "un")
    two = write_resource(second, "witness", "deux")
    imported: list[str] = []
    descriptor = witness_module()

    from types import SimpleNamespace

    from forge_design.modules import DESCRIPTOR_ATTRIBUTE, activate_modules

    def importer(name: str) -> object:
        imported.append(name)
        return SimpleNamespace(**{DESCRIPTOR_ATTRIBUTE: descriptor})

    with serving(tmp_path, activate_modules(("pkg",), importer)) as app:
        call(app, "/inspector", method="POST", value=str(first))
        assert one in call(app, "/modules/witness/")[1]
        call(app, "/inspector", method="POST", value=str(second))
        html = call(app, "/modules/witness/")[1]
        assert two in html and one not in html
    assert imported == ["pkg"]


def test_web_layer_never_touches_project_files_or_the_tool_registry() -> None:
    """Lecture par l'hôte seulement ; aucun module enregistré comme Tool."""
    root = Path(__file__).resolve().parents[1] / "forge_design"
    web = (root / "web/modules.py").read_text(encoding="utf-8")
    for forbidden in (
        "open(",
        ".read_bytes(",
        ".read_text(",
        "os.",
        "scandir",
        "Path(",
    ):
        assert forbidden not in web, forbidden
    server = (root / "web/server.py").read_text(encoding="utf-8")
    assert "registry.register" not in server and "ToolRegistry(" not in server
    assert "ModuleHost(" in server and "create_tool_registry()" in server
