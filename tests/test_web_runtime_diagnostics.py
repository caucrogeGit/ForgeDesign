"""Diagnostic Forge dans Debug Center (FD-RUNTIME-001) : jamais au GET, POST
explicite unique, refus sans projet ou hors projet Forge, garde d'origine, aucun
paramètre accepté, rendu échappé, sans cache ni persistance."""

import re
import shutil
from html import unescape
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import HOSTILE, forge_project
from test_project_health import snapshot
from test_web_modules import serving
from test_web_recent_projects import call

import forge_design.web.debug as debug_page
from forge_design.app import create_tool_registry
from forge_design.forge.runtime_diagnostics import ForgeDiagnosticRun
from forge_design.web.server import ForgeDesignServer

ACTION = "/debug/forge-diagnostic"


def post(
    app: ForgeDesignServer,
    body: str = "",
    *,
    origin: str | None = "local",
    content_type: str = "application/x-www-form-urlencoded",
    url: str = ACTION,
) -> tuple[int, str, dict[str, str]]:
    headers = {"Content-Type": content_type, "Sec-Fetch-Site": "same-origin"}
    if origin is not None:
        headers["Origin"] = (
            f"http://127.0.0.1:{app.server_port}" if origin == "local" else origin
        )
    connection = HTTPConnection("127.0.0.1", app.server_port, timeout=30)
    try:
        connection.request("POST", url, body.encode(), headers)
        response = connection.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        connection.close()


def section(html: str) -> str:
    match = re.search(r'<section class="forge-diagnostic".*?</section>', html, re.S)
    assert match is not None
    return match.group(0)


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Espion : chaque exécution réelle du runner, avec sa racine."""
    calls: list[Path] = []
    original = debug_page.run_forge_diagnostic

    def counted(checked: Any) -> ForgeDiagnosticRun:
        calls.append(checked.root)
        return original(checked)

    monkeypatch.setattr(debug_page, "run_forge_diagnostic", counted)
    return calls


def opened(app: ForgeDesignServer, root: Path) -> None:
    assert call(app, "/inspector", method="POST", value=str(root))[0] == 200


def test_get_never_runs_the_diagnostic(tmp_path: Path, runs: list[Path]) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        opened(app, root)
        for url in ("/debug", "/inspector", "/routes", "/", "/debug?q=x"):
            assert call(app, url)[0] in {200, 400}
        assert call(app, "/project/refresh", method="POST")[0] == 200
        status, html, headers = call(app, "/debug")
        status_get, _, _ = call(app, ACTION)
    assert runs == []
    assert status == 200 and headers["Cache-Control"] == "no-store"
    part = section(html)
    assert 'data-diagnostic-status="not-run"' in part
    assert '<form method="post" action="/debug/forge-diagnostic">' in part
    assert "Exécuter le diagnostic Forge" in part
    assert "exécute la configuration du projet" in unescape(part)
    assert status_get in {404, 405}


def test_explicit_post_runs_once_and_renders(tmp_path: Path, runs: list[Path]) -> None:
    root = forge_project(tmp_path / "projet", "fail")
    before = snapshot(root)
    with serving(tmp_path, None) as app:
        opened(app, root)
        status, html, headers = post(app)
    assert runs == [root]
    assert status == 200 and headers["Cache-Control"] == "no-store"
    part = section(html)
    assert 'data-diagnostic-status="checks-failed"' in part
    assert "Terminé avec le code 1" in part
    assert "<dt>Code retour</dt><dd>1</dd>" in part
    assert "[FAIL]  Structure MVC" in part and "trace simulée" in part
    # Le journal reste une section distincte.
    assert '<h2 id="journal-title">Journal des erreurs runtime</h2>' in html
    assert snapshot(root) == before


def test_hostile_output_is_escaped(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "hostile")
    with serving(tmp_path, None) as app:
        opened(app, root)
        _, html, _ = post(app)
    part = section(html)
    assert "<script>alert(1)</script>" not in part and "<img src=x" not in part
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in part
    stdout = re.search(r"data-diagnostic-stdout>(.*?)</pre>", part, re.S)
    assert stdout is not None and unescape(stdout.group(1)).startswith(HOSTILE)
    assert "\x1b" not in part


def test_timeout_and_truncation_are_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.forge import runtime_diagnostics

    root = forge_project(tmp_path / "projet", "sleep")
    original = runtime_diagnostics.run_forge_diagnostic

    def short(checked: Any) -> ForgeDiagnosticRun:
        return original(checked, timeout=0.5)

    monkeypatch.setattr(debug_page, "run_forge_diagnostic", short)
    with serving(tmp_path, None) as app:
        opened(app, root)
        _, html, _ = post(app)
        (root / "fake-doctor-mode").write_text("big")
        _, big, _ = post(app)
    assert 'data-diagnostic-status="timed-out"' in section(html)
    assert "Diagnostic interrompu\u00a0: délai dépassé." in section(html)
    assert 'data-diagnostic-truncated="stdout"' in section(big)
    assert "786432 octets ignorés au-delà de 256 Kio" in section(big)


def test_no_project_and_invalid_projects_never_run(
    tmp_path: Path, runs: list[Path]
) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        status, html, _ = post(app)
        assert status == 409
        assert "Aucun projet sélectionné\u00a0: diagnostic non lancé." in html
        opened(app, root)
        (root / "app.py").unlink()
        status, html, _ = post(app)
        assert status == 409 and "Diagnostic non lancé\u00a0: " in html
        shutil.rmtree(root)
        status, html, _ = post(app)
        assert status == 409 and "Diagnostic non lancé\u00a0: " in html
        assert "Traceback" not in html
    assert runs == []


def test_http_guards(tmp_path: Path, runs: list[Path]) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        opened(app, root)
        assert post(app, origin="http://evil.test")[0] == 403
        assert post(app, origin=None)[0] == 403
        assert post(app, content_type="text/plain")[0] == 415
        # Aucun champ ni paramètre : ni commande, ni chemin, ni environnement.
        for body, url in (
            ("command=rm", ACTION),
            ("path=/etc", ACTION),
            ("env=PYTHONPATH%3D%2Ftmp", ACTION),
            ("", ACTION + "?cwd=/tmp"),
        ):
            status, html, _ = post(app, body, url=url)
            assert status == 400 and "aucun paramètre" in html
    assert runs == []


def test_missing_project_interpreter_is_reported(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", None)
    with serving(tmp_path, None) as app:
        opened(app, root)
        status, html, _ = post(app)
    part = section(html)
    assert status == 200 and 'data-diagnostic-status="launch-failed"' in part
    assert "Interpréteur du projet introuvable ou inutilisable" in part


def test_result_is_not_persisted(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "fail")
    with serving(tmp_path, None) as app:
        opened(app, root)
        post(app)
        _, html, _ = call(app, "/debug")
    # Aucun « dernier diagnostic » : la page revient à l'état non exécuté.
    assert 'data-diagnostic-status="not-run"' in section(html)
    assert not (root / ".forge-design").exists()


def test_tool_registry_unchanged() -> None:
    assert [tool.id for tool in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
