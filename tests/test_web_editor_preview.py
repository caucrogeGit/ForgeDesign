"""Prévisualisation encadrée : renderer existant, iframe sandbox, CSP, modes."""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIServer

import pytest
from test_web_editor import (
    DESIGN,
    action,
    design_data,
    get,
    location,
    make_root,
    request,
    serving,
    snapshot,
    write,
)
from test_web_recent_projects import running

import forge_design.preview as preview_package
import forge_design.preview.responsive as responsive
from forge_design.preview import PREVIEW_VIEWPORTS
from forge_design.recent_projects import RecentProjects
from forge_design.web import editor as web_editor
from forge_design.web import editor_preview
from forge_design.web.editor_preview import preview_frame_policy

CONTRACT_FILE = "mvc/views/contacts/list.view.json"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_root(tmp_path)


@pytest.fixture
def app(root: Path, tmp_path: Path) -> Iterator[WSGIServer]:
    with serving(root, tmp_path) as server:
        yield server


def frame(server: WSGIServer, **params: str) -> tuple[int, str, dict[str, str]]:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return request(server, "/editor/preview?" + query, method="GET")


def nominal(
    server: WSGIServer, mode: str = "desktop"
) -> tuple[int, str, dict[str, str]]:
    return frame(server, design=DESIGN, mode=mode)


# Document de prévisualisation.


def test_without_project_409(tmp_path: Path) -> None:
    with running(RecentProjects(tmp_path / "recent.json")) as server:
        status, html, headers = frame(server, design=DESIGN)
        assert status == 409 and "Aucun projet ouvert." in html
        assert headers["Cache-Control"] == "no-store"


def test_nominal_render_with_fake_data(app: WSGIServer) -> None:
    status, html, headers = nominal(app)
    assert status == 200 and headers["Cache-Control"] == "no-store"
    assert 'data-forge-design-preview="page"' in html
    # Binding string : valeur fictive de preview/data.py.
    assert '<h2 data-forge-design-type="title">Exemple</h2>' in html
    # Liste : trois lignes fictives.
    tbody = html.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.count("<tr>") == 3
    assert "Données fictives : complètes" in html and "Rendu : complet" in html
    assert "Aperçu structurel" in html and "rendu final" not in html
    assert html.startswith("<!doctype html>") and '<html lang="fr">' in html
    assert '<link rel="stylesheet" href="/editor-preview.css">' in html


def test_frame_headers(app: WSGIServer) -> None:
    headers = nominal(app)[2]
    policy = headers["Content-Security-Policy"]
    assert policy == preview_frame_policy(f"127.0.0.1:{app.server_port}")
    assert "frame-ancestors 'self'" in policy
    assert "default-src 'none'" in policy and "form-action 'none'" in policy
    assert "script-src" not in policy and "unsafe-inline" not in policy
    assert f"style-src 'self' http://127.0.0.1:{app.server_port}" in policy
    assert headers["X-Frame-Options"] == "SAMEORIGIN"


def test_other_pages_keep_forge_frame_denial(app: WSGIServer) -> None:
    for url in ("/editor?design=" + DESIGN, "/", "/editor-preview.css"):
        headers = request(app, url, method="GET")[2]
        assert headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


@pytest.mark.parametrize(
    ("host", "style"),
    [
        ("127.0.0.1:8765", "style-src 'self' http://127.0.0.1:8765;"),
        ("evil.example", "style-src 'self';"),
        ("127.0.0.1:8765 'unsafe-inline'", "style-src 'self';"),
        ("", "style-src 'self';"),
    ],
)
def test_frame_policy_host(host: str, style: str) -> None:
    assert style in preview_frame_policy(host)


@pytest.mark.parametrize(
    ("mode", "label", "width"),
    [
        ("desktop", "Desktop", 1440),
        ("tablet", "Tablette", 768),
        ("mobile", "Mobile", 390),
    ],
)
def test_modes(app: WSGIServer, mode: str, label: str, width: int) -> None:
    status, html, _ = nominal(app, mode)
    assert status == 200 and f"{label} ({width} px)" in html
    assert PREVIEW_VIEWPORTS[mode].width_px == width  # type: ignore[index]


def test_default_mode_desktop(app: WSGIServer) -> None:
    assert "Desktop (1440 px)" in frame(app, design=DESIGN)[1]


@pytest.mark.parametrize(
    "query",
    [
        f"design={DESIGN}&mode=wide",
        f"design={DESIGN}&mode=Desktop",
        f"design={DESIGN}&mode=desktop&mode=mobile",
        f"design={DESIGN}&design={DESIGN}",
        f"design={DESIGN}&node=0",
        "mode=desktop",
        "",
        "design=" + "a" * 5000 + ".design.json",
        "design=../x.design.json",
    ],
)
def test_invalid_params_400(app: WSGIServer, query: str) -> None:
    assert request(app, "/editor/preview?" + query, method="GET")[0] == 400


def test_design_absent_404(app: WSGIServer) -> None:
    status, html, _ = frame(app, design="missing/x.design.json")
    assert status == 404 and "Design introuvable." in html


def test_design_invalid_unavailable(app: WSGIServer, root: Path) -> None:
    (root / "mvc/views" / DESIGN).write_text('{"version": "9"}')
    status, html, _ = nominal(app)
    assert status == 200
    assert "Prévisualisation indisponible : Design invalide." in html
    assert "data-forge-design-preview" not in html


@pytest.mark.parametrize("content", [None, "{not json", '{"name": "x"}'])
def test_contract_unavailable(app: WSGIServer, root: Path, content: str | None) -> None:
    contract = root / CONTRACT_FILE
    if content is None:
        contract.unlink()
    else:
        contract.write_text(content)
    status, html, _ = nominal(app)
    assert status == 200
    assert "Prévisualisation indisponible : contrat absent ou invalide." in html
    assert "data-forge-design-preview" not in html
    # L'éditeur reste utilisable pour la structure.
    assert 'name="block_type"' in get(app, design=DESIGN)[1]


def test_partial_preview_diagnostics(app: WSGIServer, root: Path) -> None:
    data = design_data()
    data["root"]["children"][0]["props"] = {"class": "p-4", "data-x": "1"}
    write(root, data)
    contract = json.loads((root / CONTRACT_FILE).read_text())
    # "uuid" n'est pas un type de champ connu de preview/data.py.
    contract["context"]["contacts"]["fields"]["nom"] = "uuid"
    (root / CONTRACT_FILE).write_text(json.dumps(contract))
    html = nominal(app)[1]
    assert "Données fictives : partielles" in html and "Rendu : partiel" in html
    assert "Prévisualisation partielle." in html
    assert "<code>preview.unsupported_prop</code>" in html
    assert "<code>preview.unsupported_field_type</code>" in html
    assert 'data-forge-design-preview="page"' in html  # HTML exploitable affiché


def test_hostile_values_inert(app: WSGIServer, root: Path) -> None:
    data = design_data()
    hostile = '"><script>alert(1)</script><img src=x onerror=alert(1)>'
    data["root"]["children"][0]["props"] = {"class": hostile}
    data["view"] = hostile
    write(root, data)
    html = nominal(app)[1]
    assert "<script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html or "&#34;&gt;&lt;script" in html


def test_no_inline_style(app: WSGIServer) -> None:
    assert "style=" not in nominal(app)[1]
    assert "style=" not in get(app, design=DESIGN)[1]


def test_responsive_helpers_not_used(
    app: WSGIServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("helper responsive avec style inline")

    for target in (responsive, preview_package):
        monkeypatch.setattr(target, "render_responsive_preview", forbidden)
        monkeypatch.setattr(target, "wrap_preview_html", forbidden)
    assert nominal(app, "mobile")[0] == 200
    names = set(vars(editor_preview))
    assert not names & {"render_responsive_preview", "wrap_preview_html"}


def test_preview_is_read_only(
    app: WSGIServer, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("écriture interdite en GET")

    for name in ("write_design", "set_design_props", "append_design_block"):
        monkeypatch.setattr(web_editor, name, forbidden)
    before = snapshot(root)
    template = root / "mvc/views/contacts/list.html"
    template_before = template.read_bytes(), template.stat().st_mtime_ns
    for mode in ("desktop", "tablet", "mobile"):
        assert nominal(app, mode)[0] == 200
    assert snapshot(root) == before
    assert (template.read_bytes(), template.stat().st_mtime_ns) == template_before
    assert not (root / ".forge-design").exists()


def test_preview_css_served(app: WSGIServer) -> None:
    status, css, headers = request(app, "/editor-preview.css", method="GET")
    assert status == 200 and headers["Content-Type"] == "text/css; charset=utf-8"
    assert ".preview-canvas" in css


# Intégration dans l'éditeur.


def iframe(html: str) -> str:
    match = re.search(r"<iframe [^>]*></iframe>", html)
    assert match is not None
    return match.group(0)


def test_editor_iframe_sandboxed(app: WSGIServer) -> None:
    tag = iframe(get(app, design=DESIGN)[1])
    assert tag == (
        '<iframe class="preview-frame preview-frame--desktop" '
        'src="/editor/preview?design=contacts%2Flist.design.json&amp;mode=desktop" '
        'title="Prévisualisation du Design" sandbox></iframe>'
    )
    for permission in ("allow-scripts", "allow-forms", "allow-same-origin", "allow-"):
        assert permission not in tag


def test_editor_preview_mode(app: WSGIServer) -> None:
    status, html, _ = get(app, design=DESIGN, node="0", preview="mobile")
    assert status == 200
    tag = iframe(html)
    assert "preview-frame--mobile" in tag and "mode=mobile" in tag
    assert 'aria-current="true">Mobile</a>' in html
    # Le mode est conservé par la sélection de bloc et par les formulaires.
    assert "node=0.0&amp;preview=mobile" in html
    assert html.count('name="preview" value="mobile"') >= 5
    assert 'name="preview" value="desktop"' not in html


def test_editor_preview_mode_invalid_400(app: WSGIServer) -> None:
    assert get(app, design=DESIGN, preview="wide")[0] == 400


def test_historic_urls_default_desktop(app: WSGIServer) -> None:
    html = get(app, design=DESIGN)[1]
    assert "preview-frame--desktop" in html
    assert 'aria-current="true">Desktop</a>' in html
    # URL historique conservée : pas de preview=desktop ajouté aux liens.
    assert "preview=desktop" not in html


def test_mutation_keeps_mode_and_preview_rereads(app: WSGIServer) -> None:
    status, _, headers = action(
        app, action="append", parent="0", block_type="alert", preview="tablet"
    )
    assert status == 303 and location(headers)["preview"] == ["tablet"]
    assert '<div data-forge-design-type="alert">' in nominal(app, "tablet")[1]
    status, _, headers = action(
        app, action="tailwind_add", path="0", class_token="max-w-5xl", preview="mobile"
    )
    assert location(headers)["preview"] == ["mobile"]
    assert 'class="p-4 max-w-5xl"' in nominal(app, "mobile")[1]


def test_action_without_preview_keeps_historic_redirect(app: WSGIServer) -> None:
    headers = action(app, action="append", parent="0", block_type="alert")[2]
    assert "preview" not in location(headers)


def test_noop_with_preview_never_writes(
    app: WSGIServer, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def spy(*args: Any, **kwargs: Any) -> None:
        calls.append(args)

    monkeypatch.setattr(web_editor, "write_design", spy)
    before = snapshot(root)
    status, _, headers = action(
        app, action="tailwind_add", path="0", class_token="p-4", preview="mobile"
    )
    assert status == 303 and location(headers)["notice"] == ["noop"]
    assert location(headers)["preview"] == ["mobile"]
    assert calls == [] and snapshot(root) == before


def test_action_invalid_preview_400(app: WSGIServer, root: Path) -> None:
    before = snapshot(root)
    fields = {"action": "append", "parent": "0", "block_type": "alert", "preview": "x"}
    assert action(app, **fields)[0] == 400
    assert snapshot(root) == before


def test_css_widths_match_viewports() -> None:
    from importlib.resources import files

    css = files("forge_design.web").joinpath("static/shell.css").read_text()
    for mode, viewport in PREVIEW_VIEWPORTS.items():
        assert f".preview-frame--{mode} {{ width: {viewport.width_px}px; }}" in css
    assert ".preview-frame { display: block; margin: 0 auto; max-width: 100%;" in css
