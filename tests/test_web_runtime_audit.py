"""Audit Forge dans Debug Center (FD-RUNTIME-002) : jamais au GET, POST explicite
unique, aucun mélange avec le diagnostic, mêmes gardes, rendu échappé et masqué,
sans cache ni persistance."""

import re
from html import unescape
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import forge_project
from test_project_health import snapshot
from test_web_modules import serving
from test_web_recent_projects import call
from test_web_runtime_diagnostics import opened, post

import forge_design.web.debug as debug_page
from forge_design.app import create_tool_registry
from forge_design.forge.runtime_diagnostics import ForgeDiagnosticRun

AUDIT = "/debug/forge-audit"
DOCTOR = "/debug/forge-diagnostic"


def part(html: str, key: str) -> str:
    match = re.search(rf'<section class="forge-{key}".*?</section>', html, re.S)
    assert match is not None, key
    return match.group(0)


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Espion : chaque exécution réelle, dans l'ordre, par commande."""
    calls: list[str] = []
    doctor, audit = debug_page.run_forge_diagnostic, debug_page.run_forge_project_audit

    def counted_doctor(checked: Any) -> ForgeDiagnosticRun:
        calls.append("doctor")
        return doctor(checked)

    def counted_audit(checked: Any) -> ForgeDiagnosticRun:
        calls.append("audit")
        return audit(checked)

    monkeypatch.setattr(debug_page, "run_forge_diagnostic", counted_doctor)
    monkeypatch.setattr(debug_page, "run_forge_project_audit", counted_audit)
    return calls


def test_get_never_runs_and_shows_both_commands(
    tmp_path: Path, runs: list[str]
) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        opened(app, root)
        for url in ("/debug", "/inspector", "/debug?q=x", "/routes"):
            assert call(app, url)[0] in {200, 400}
        status, html, headers = call(app, "/debug")
        status_get = call(app, AUDIT)[0]
    assert runs == [] and status == 200 and headers["Cache-Control"] == "no-store"
    assert status_get == 405
    audit = part(html, "audit")
    assert 'data-diagnostic-status="not-run"' in part(html, "diagnostic")
    assert 'data-diagnostic-status="not-run"' in audit
    assert f'<form method="post" action="{AUDIT}">' in audit
    assert "Exécuter l’audit Forge" in audit and "Exécuter le diagnostic Forge" in html
    warning = unescape(audit)
    assert "il n’exécute ni config.py, ni l’application, ni les tests" in re.sub(
        r"</?code>", "", warning
    )
    assert "exécute la configuration du projet" not in warning
    # Ordre : diagnostic, audit, puis journal.
    assert html.index("forge-diagnostic-title") < html.index("forge-audit-title")
    assert html.index("forge-audit-title") < html.index('id="journal-title"')


def test_each_post_runs_only_its_command(tmp_path: Path, runs: list[str]) -> None:
    root = forge_project(tmp_path / "projet", "fail")
    before = snapshot(root)
    with serving(tmp_path, None) as app:
        opened(app, root)
        status, audited, headers = post(app, url=AUDIT)
        assert runs == ["audit"]
        _, doctored, _ = post(app, url=DOCTOR)
        assert runs == ["audit", "doctor"]
        _, after, _ = call(app, "/debug")
    assert status == 200 and headers["Cache-Control"] == "no-store"
    assert 'data-diagnostic-status="checks-failed"' in part(audited, "audit")
    assert 'data-diagnostic-status="not-run"' in part(audited, "diagnostic")
    assert (
        "Terminé avec le code 1 : au moins un constat FAIL, ou erreur de la commande"
        in part(audited, "audit")
    )
    assert 'data-diagnostic-status="checks-failed"' in part(doctored, "diagnostic")
    assert 'data-diagnostic-status="not-run"' in part(doctored, "audit")
    assert "au moins un contrôle en échec" in part(doctored, "diagnostic")
    # Aucun résultat persisté : le GET suivant revient à « non exécuté ».
    assert part(after, "audit").count('data-diagnostic-status="not-run"') == 1
    assert part(after, "diagnostic").count('data-diagnostic-status="not-run"') == 1
    assert runs == ["audit", "doctor"]
    assert snapshot(root) == before


def test_code_zero_label_mentions_possible_warnings(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        opened(app, root)
        _, html, _ = post(app, url=AUDIT)
    assert (
        "Terminé avec le code 0 : aucun constat FAIL (des avertissements restent "
        "possibles)" in part(html, "audit")
    )


def test_guards_and_projects(tmp_path: Path, runs: list[str]) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        status, html, _ = post(app, url=AUDIT)
        assert status == 409
        assert "Aucun projet sélectionné : audit non lancé." in part(html, "audit")
        assert "data-diagnostic-error" not in part(html, "diagnostic")
        opened(app, root)
        assert post(app, url=AUDIT, origin="http://evil.test")[0] == 403
        assert post(app, url=AUDIT, origin=None)[0] == 403
        assert post(app, url=AUDIT, content_type="text/plain")[0] == 415
        for body, url in (
            ("command=doctor", AUDIT),
            ("args=--fix", AUDIT),
            ("timeout=99", AUDIT),
            ("", AUDIT + "?cwd=/tmp"),
        ):
            status, html, _ = post(app, body, url=url)
            assert status == 400 and "aucun paramètre" in part(html, "audit")
        (root / "app.py").unlink()
        status, html, _ = post(app, url=AUDIT)
        assert status == 409 and "Audit non lancé : " in part(html, "audit")
    assert runs == []


def test_hostile_secret_timeout_and_truncation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.forge import runtime_diagnostics

    root = forge_project(tmp_path / "projet", "hostile")
    original = runtime_diagnostics.run_forge_project_audit

    def short(checked: Any) -> ForgeDiagnosticRun:
        return original(checked, timeout=0.5)

    monkeypatch.setattr(debug_page, "run_forge_project_audit", short)
    with serving(tmp_path, None) as app:
        opened(app, root)
        _, hostile, _ = post(app, url=AUDIT)
        (root / "fake-doctor-mode").write_text("secret")
        _, secret, _ = post(app, url=AUDIT)
        (root / "fake-doctor-mode").write_text("sleep")
        _, slow, _ = post(app, url=AUDIT)
        (root / "fake-doctor-mode").write_text("big")
        _, big, _ = post(app, url=AUDIT)
    assert "<script>alert(1)</script>" not in part(hostile, "audit")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in part(hostile, "audit")
    for value in ("hunter", "k3y-777", "abc999", "t0ken-99"):
        assert value not in secret
    assert "Audit interrompu : délai dépassé." in part(slow, "audit")
    assert 'data-diagnostic-status="timed-out"' in part(slow, "audit")
    assert "786432 octets ignorés au-delà de 256 Kio" in part(big, "audit")


def test_missing_interpreter(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", None)
    with serving(tmp_path, None) as app:
        opened(app, root)
        status, html, _ = post(app, url=AUDIT)
    assert status == 200 and 'data-diagnostic-status="launch-failed"' in part(
        html, "audit"
    )
    assert "audit non lancé" in part(html, "audit")


def test_tool_registry_unchanged() -> None:
    assert [tool.id for tool in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
