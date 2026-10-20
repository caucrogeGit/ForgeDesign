"""Vérification Forge dans Debug Center (FD-RUNTIME-003) : jamais au GET, un POST
par commande, aucune des trois commandes n'en déclenche une autre, mêmes gardes,
avertissement explicite sur l'exécution de code applicatif, aucune persistance."""

import re
from html import unescape
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import forge_project
from test_project_health import snapshot
from test_web_modules import serving
from test_web_recent_projects import call
from test_web_runtime_audit import part
from test_web_runtime_diagnostics import opened, post

import forge_design.web.debug as debug_page
from forge_design.app import create_tool_registry
from forge_design.forge.runtime_diagnostics import ForgeDiagnosticRun

CHECK = "/debug/forge-project-check"
AUDIT = "/debug/forge-audit"
DOCTOR = "/debug/forge-diagnostic"
RUNNERS = {
    "doctor": "run_forge_diagnostic",
    "audit": "run_forge_project_audit",
    "check": "run_forge_project_check",
}


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Espion : chaque exécution réelle, dans l'ordre, par commande."""
    calls: list[str] = []
    for label, name in RUNNERS.items():
        original = getattr(debug_page, name)

        def counted(checked: Any, label: str = label, original: Any = original) -> Any:
            calls.append(label)
            return original(checked)

        monkeypatch.setattr(debug_page, name, counted)
    return calls


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", html)))


def test_get_never_runs_and_warning_states_the_execution_boundary(
    tmp_path: Path, runs: list[str]
) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        _, empty, _ = call(app, "/debug")
        opened(app, root)
        for url in ("/debug", "/inspector", "/routes", "/entities", "/templates"):
            assert call(app, url)[0] in {200, 400}
        assert call(app, "/project/refresh", method="POST")[0] == 200
        status, html, headers = call(app, "/debug")
        status_get = call(app, CHECK)[0]
    assert runs == [] and status == 200 and headers["Cache-Control"] == "no-store"
    assert status_get == 405
    assert "ouvrez un projet pour lancer la vérification." in plain(
        part(empty, "check")
    )
    section = part(html, "check")
    assert 'data-diagnostic-status="not-run"' in section
    assert f'<form method="post" action="{CHECK}">' in section
    assert "Exécuter la vérification Forge" in section
    text = plain(section)
    # Garde de l'avertissement : la frontière d'exécution reste explicite.
    for phrase in (
        "forge project:check",
        "importe réellement les routes du projet",
        "ce code s’exécute, ainsi que les contrôleurs et modules qu’il importe",
        "peut lire ou écrire des fichiers, contacter des services ou lancer des "
        "processus avec les droits de votre compte",
        "arrête le groupe de processus qu’il a lancé",
        "ce sous-processus n’est pas un bac à sable",
    ):
        assert phrase in text, phrase
    assert "tous les processus" not in text and "analyse les routes" not in text
    # Ordre : diagnostic, audit, vérification, journal.
    positions = [
        html.index(marker)
        for marker in (
            "forge-diagnostic-title",
            "forge-audit-title",
            "forge-check-title",
            'id="journal-title"',
        )
    ]
    assert positions == sorted(positions)


def test_each_post_runs_only_its_command(tmp_path: Path, runs: list[str]) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    before = snapshot(root)
    with serving(tmp_path, None) as app:
        opened(app, root)
        status, checked, headers = post(app, url=CHECK)
        assert runs == ["check"]
        _, audited, _ = post(app, url=AUDIT)
        assert runs == ["check", "audit"]
        _, doctored, _ = post(app, url=DOCTOR)
        assert runs == ["check", "audit", "doctor"]
        _, after, _ = call(app, "/debug")
    assert status == 200 and headers["Cache-Control"] == "no-store"
    expected = {"check": checked, "audit": audited, "diagnostic": doctored}
    for ran, html in expected.items():
        for key in ("diagnostic", "audit", "check"):
            state = "succeeded" if key == ran else "not-run"
            assert f'data-diagnostic-status="{state}"' in part(html, key), (ran, key)
    assert (
        "Terminé avec le code 0\u00a0: aucun contrôle en échec (des avertissements "
        "restent possibles)" in part(checked, "check")
    )
    for key in ("diagnostic", "audit", "check"):
        assert 'data-diagnostic-status="not-run"' in part(after, key)
    assert runs == ["check", "audit", "doctor"]
    assert snapshot(root) == before


@pytest.mark.parametrize(
    ("mode", "label"),
    [
        (
            "fail",
            "Terminé avec le code 1\u00a0: au moins un contrôle en échec, ou erreur",
        ),
        (
            "code3",
            "Terminé avec un autre code retour\u00a0: le code importé du projet a pu "
            "terminer le processus",
        ),
    ],
)
def test_exit_code_labels(tmp_path: Path, mode: str, label: str) -> None:
    root = forge_project(tmp_path / "projet", mode)
    with serving(tmp_path, None) as app:
        opened(app, root)
        _, html, _ = post(app, url=CHECK)
    assert label in part(html, "check")


def test_guards_and_projects(tmp_path: Path, runs: list[str]) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    with serving(tmp_path, None) as app:
        status, html, _ = post(app, url=CHECK)
        assert status == 409
        assert "Aucun projet sélectionné\u00a0: vérification non lancée." in part(
            html, "check"
        )
        opened(app, root)
        assert post(app, url=CHECK, origin="http://evil.test")[0] == 403
        assert post(app, url=CHECK, origin=None)[0] == 403
        assert post(app, url=CHECK, content_type="text/plain")[0] == 415
        for body, url in (
            ("command=project:audit", CHECK),
            ("args=--fix", CHECK),
            ("cwd=/tmp", CHECK),
            ("", CHECK + "?env=APP_ENV%3Dprod"),
        ):
            status, html, _ = post(app, body, url=url)
            assert status == 400 and "aucun paramètre" in part(html, "check")
        (root / "app.py").unlink()
        status, html, _ = post(app, url=CHECK)
        assert status == 409
        assert "Vérification non lancée\u00a0: " in part(html, "check")
    assert runs == []


def test_secret_timeout_and_missing_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.forge import runtime_diagnostics

    original = runtime_diagnostics.run_forge_project_check

    def short(checked: Any) -> ForgeDiagnosticRun:
        return original(checked, timeout=0.5)

    monkeypatch.setattr(debug_page, "run_forge_project_check", short)
    root = forge_project(tmp_path / "projet", "secret")
    absent = forge_project(tmp_path / "absent", None)
    with serving(tmp_path, None) as app:
        opened(app, root)
        _, secret, _ = post(app, url=CHECK)
        (root / "fake-doctor-mode").write_text("sleep")
        _, slow, _ = post(app, url=CHECK)
        opened(app, absent)
        _, missing, _ = post(app, url=CHECK)
    for value in ("hunter", "k3y-777", "abc999", "t0ken-99"):
        assert value not in secret
    assert "Vérification interrompue\u00a0: délai dépassé." in part(slow, "check")
    assert 'data-diagnostic-status="launch-failed"' in part(missing, "check")
    assert "vérification non lancée." in part(missing, "check")


def test_tool_registry_unchanged() -> None:
    assert [tool.id for tool in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
