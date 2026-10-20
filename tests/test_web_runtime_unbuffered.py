"""Sortie produite avant un délai dépassé, rendue dans Debug Center
(FD-RUNTIME-004) : pour chacune des trois commandes, la page affiche le message
de délai et la sortie déjà émise, masquée et échappée, dans sa seule section."""

from html import unescape
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import forge_project
from test_web_modules import serving
from test_web_runtime_audit import part
from test_web_runtime_diagnostics import opened, post

import forge_design.web.debug as debug_page
from forge_design.forge import runtime_diagnostics
from forge_design.forge.runtime_diagnostics import ForgeDiagnosticRun

CASES = [
    (
        "diagnostic",
        "/debug/forge-diagnostic",
        "run_forge_diagnostic",
        "Diagnostic interrompu\u00a0: délai dépassé.",
    ),
    (
        "audit",
        "/debug/forge-audit",
        "run_forge_project_audit",
        "Audit interrompu\u00a0: délai dépassé.",
    ),
    (
        "check",
        "/debug/forge-project-check",
        "run_forge_project_check",
        "Vérification interrompue\u00a0: délai dépassé.",
    ),
]


@pytest.mark.parametrize(("key", "url", "runner", "message"), CASES)
def test_partial_output_is_rendered_after_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    url: str,
    runner: str,
    message: str,
) -> None:
    original = getattr(runtime_diagnostics, runner)

    def short(checked: Any) -> ForgeDiagnosticRun:
        return original(checked, timeout=1.5)

    monkeypatch.setattr(debug_page, runner, short)
    root = forge_project(tmp_path / "projet", "partial")
    with serving(tmp_path, None) as app:
        opened(app, root)
        status, html, _ = post(app, url=url)
    section = part(html, key)
    assert status == 200 and 'data-diagnostic-status="timed-out"' in section
    text = unescape(section)
    assert message in text
    assert "AVANT TIMEOUT\nDB_PASSWORD=[masqué] avant blocage\nSANS-LF" in text
    assert "ERREUR AVANT TIMEOUT\nERR-SANS-LF" in text
    assert "VerySecret123" not in html
    # Les deux autres sections restent non exécutées.
    for other, *_ in CASES:
        if other != key:
            assert 'data-diagnostic-status="not-run"' in part(html, other)
