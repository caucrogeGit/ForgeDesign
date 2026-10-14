"""Sorties runtime non tamponnées (FD-RUNTIME-004) : avec ``-u``, ce que le Python
principal a déjà écrit est dans le tube et reste conservé si la commande est
interrompue au délai ; sans ``-u``, la même sortie est perdue. Le faux
interpréteur applique réellement les options Python placées avant ``-m``."""

import os
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import alive, forge_project, make_linked_venv
from test_runtime_audit import real_project

from forge_design.forge import runtime_diagnostics
from forge_design.forge.checked_root import CheckedForgeRoot, check_forge_root
from forge_design.forge.runtime_diagnostics import (
    AUDIT_ARGUMENTS,
    CHECK_ARGUMENTS,
    DIAGNOSTIC_ARGUMENTS,
    ForgeDiagnosticRun,
    run_forge_diagnostic,
    run_forge_project_audit,
    run_forge_project_check,
)

M = "[masqué]"
Runner = Callable[..., ForgeDiagnosticRun]
RUNNERS: dict[str, Runner] = {
    "doctor": run_forge_diagnostic,
    "project:audit": run_forge_project_audit,
    "project:check": run_forge_project_check,
}
TIMED_OUT = {
    "doctor": "Diagnostic interrompu : délai dépassé.",
    "project:audit": "Audit interrompu : délai dépassé.",
    "project:check": "Vérification interrompue : délai dépassé.",
}


def without_u(argv: Sequence[str], cwd: Path, env: Mapping[str, str]) -> Any:
    """Même lancement, même argv, sauf ``-u`` : la preuve contraire."""
    stripped = [arg for arg in argv if arg != "-u"]
    assert len(stripped) == len(argv) - 1
    return runtime_diagnostics._spawn(stripped, cwd, env)  # pyright: ignore[reportPrivateUsage]


def run(name: str, root: Path, **options: Any) -> ForgeDiagnosticRun:
    return RUNNERS[name](check_forge_root(root), **options)


def test_exact_argv_puts_u_before_m() -> None:
    for arguments, command in (
        (DIAGNOSTIC_ARGUMENTS, "doctor"),
        (AUDIT_ARGUMENTS, "project:audit"),
        (CHECK_ARGUMENTS, "project:check"),
    ):
        # Après -m, « -u » serait un argument de Forge, pas de Python.
        assert arguments == ("-s", "-B", "-P", "-u", "-m", "forge", command)
        assert arguments.index("-u") < arguments.index("-m")


@pytest.mark.parametrize("name", list(RUNNERS))
def test_unbuffered_output_is_preserved_before_timeout(
    tmp_path: Path, name: str
) -> None:
    root = forge_project(tmp_path / "projet", "partial")
    result = run(name, root, timeout=1.5)
    assert (result.status, result.exit_code, result.timed_out) == (
        "timed-out",
        None,
        True,
    )
    assert result.message == TIMED_OUT[name]
    # Lignes, secret masqué, fragment sans saut de ligne, dans l'ordre reçu.
    assert result.stdout == f"AVANT TIMEOUT\nDB_PASSWORD={M} avant blocage\nSANS-LF"
    assert result.stderr == "ERREUR AVANT TIMEOUT\nERR-SANS-LF"
    assert "VerySecret123" not in result.stdout


@pytest.mark.parametrize("name", list(RUNNERS))
def test_same_output_is_lost_without_u(tmp_path: Path, name: str) -> None:
    root = forge_project(tmp_path / "projet", "partial")
    result = run(name, root, timeout=1.5, launcher=without_u)
    assert result.status == "timed-out"
    # stdout tamponné jamais vidé : rien ; stderr vidé par ligne : le fragment
    # sans saut de ligne est perdu.
    assert result.stdout == ""
    assert result.stderr == "ERREUR AVANT TIMEOUT\n"


def test_large_output_before_timeout_is_bounded(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "partial-big")
    started = time.monotonic()
    result = run("project:check", root, timeout=2.0)
    assert time.monotonic() - started < 6
    assert result.status == "timed-out"
    assert result.stdout == "o" * (256 * 1024)
    assert result.stdout_truncated == 1024 * 1024 - 256 * 1024
    assert result.stderr == "e" * 1000 and result.stderr_truncated == 0


def test_group_child_output_is_kept_and_child_killed(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "partial-child")
    result = run("doctor", root, timeout=1.5)
    assert result.status == "timed-out"
    # Ordre inter-processus non garanti : présence seulement.
    assert "PARENT AVANT TIMEOUT" in result.stdout
    assert "ENFANT AVANT TIMEOUT" in result.stdout
    child = int((root / "fake-child-pid").read_text())
    deadline = time.monotonic() + 2
    while alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(child)


def test_pythonunbuffered_is_neither_needed_nor_transmitted(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "partial")
    calls: list[dict[str, str]] = []

    def launcher(argv: Sequence[str], cwd: Path, env: Mapping[str, str]) -> Any:
        calls.append(dict(env))
        return runtime_diagnostics._spawn(argv, cwd, env)  # pyright: ignore[reportPrivateUsage]

    environ = {"PATH": os.environ["PATH"], "PYTHONUNBUFFERED": "1"}
    result = run("project:audit", root, timeout=1.5, launcher=launcher, environ=environ)
    assert "PYTHONUNBUFFERED" not in calls[0]
    assert "SANS-LF" in result.stdout


# ── Vrai Forge : résultat fonctionnel identique avec et sans -u ─────────────


@pytest.fixture(scope="module")
def linked_venv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_linked_venv(tmp_path_factory.mktemp("venv") / ".venv")


@pytest.mark.parametrize("name", list(RUNNERS))
def test_real_forge_output_is_identical_with_and_without_u(
    tmp_path: Path, linked_venv: Path, name: str
) -> None:
    root = real_project(tmp_path / "projet", linked_venv, failing=True)
    checked: CheckedForgeRoot = check_forge_root(root)
    with_u = RUNNERS[name](checked)
    plain = RUNNERS[name](checked, launcher=without_u)
    assert with_u.status == plain.status and with_u.exit_code == plain.exit_code
    assert with_u.exit_code in {0, 1}
    assert with_u.stdout == plain.stdout and with_u.stderr == plain.stderr
    assert with_u.stdout_truncated == plain.stdout_truncated == 0
