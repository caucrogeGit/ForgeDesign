"""Vérification officielle Forge (FD-RUNTIME-003) : ``project:check`` importe
réellement les routes du projet. Commande exacte, liste fermée, codes retour,
sorties masquées, délai, et preuve expérimentale de la frontière d'exécution :
routes, contrôleurs et imports transitifs exécutés ; config.py et modules non
importés jamais exécutés ; groupe de processus arrêté."""

import json
import os
import signal
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import alive, forge_project, make_linked_venv
from test_project_health import snapshot
from test_runtime_audit import real_project

from forge_design.forge.checked_root import CheckedForgeRoot, check_forge_root
from forge_design.forge.project_python import CHILD_ENVIRONMENT_WHITELIST
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
Runner = Callable[[CheckedForgeRoot], ForgeDiagnosticRun]


def check(root: Path, **options: Any) -> ForgeDiagnosticRun:
    return run_forge_project_check(check_forge_root(root), **options)


# ── Faux interpréteur ─────────────────────────────────────────────────────────


def test_command_cwd_and_environment_are_fixed(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "argv")
    environ = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "PYTHONPATH": "/injecté",
        "PYTHONHOME": "/injecté",
        "VIRTUAL_ENV": "/injecté",
        "APP_ENV": "prod",
        "SERVICE_TOKEN": "secret",
    }
    seen = json.loads(check(root, environ=environ).stdout)
    assert CHECK_ARGUMENTS == ("-s", "-B", "-P", "-u", "-m", "forge", "project:check")
    assert seen["argv"] == list(CHECK_ARGUMENTS)
    assert seen["cwd"] == str(root)
    assert set(seen["env"]) - {"PWD"} <= set(CHILD_ENVIRONMENT_WHITELIST)
    assert "APP_ENV" not in seen["env"]


@pytest.mark.parametrize(
    ("mode", "status", "code"),
    [("ok", "succeeded", 0), ("fail", "checks-failed", 1), ("code3", "exit-code", 3)],
)
def test_exit_codes(tmp_path: Path, mode: str, status: str, code: int) -> None:
    result = check(forge_project(tmp_path / "projet", mode))
    assert (result.status, result.exit_code, result.timed_out) == (status, code, False)


def test_outputs_secrets_and_bounds(tmp_path: Path) -> None:
    secret = check(forge_project(tmp_path / "secret", "secret"))
    for value in ("hunter", "k3y-777", "abc999", "t0ken-99"):
        assert value not in secret.stdout + secret.stderr
    big = check(forge_project(tmp_path / "big", "big"))
    assert len(big.stdout) == len(big.stderr) == 256 * 1024
    assert big.stdout_truncated == big.stderr_truncated == 768 * 1024


def test_timeout_and_missing_interpreter_messages(tmp_path: Path) -> None:
    slow = check(forge_project(tmp_path / "lent", "sleep"), timeout=0.5)
    assert slow.status == "timed-out"
    assert slow.message == "Vérification interrompue : délai dépassé."
    missing = check(forge_project(tmp_path / "absent", None))
    assert missing.status == "launch-failed"
    assert missing.message == (
        "Interpréteur du projet introuvable ou inutilisable (.venv/bin/python) : "
        "vérification non lancée."
    )


def test_concurrent_three_commands_share_no_state(tmp_path: Path) -> None:
    roots = [forge_project(tmp_path / f"p{i}", "argv") for i in range(3)]
    runners: dict[Runner, tuple[str, ...]] = {
        run_forge_diagnostic: DIAGNOSTIC_ARGUMENTS,
        run_forge_project_audit: AUDIT_ARGUMENTS,
        run_forge_project_check: CHECK_ARGUMENTS,
    }
    jobs = [(root, runner) for root in roots for runner in runners]

    def one(job: tuple[Path, Runner]) -> ForgeDiagnosticRun:
        return job[1](check_forge_root(job[0]))

    with ThreadPoolExecutor(max_workers=9) as pool:
        results = list(pool.map(one, jobs))
    for (root, runner), result in zip(jobs, results, strict=True):
        seen = json.loads(result.stdout)
        assert seen["argv"] == list(runners[runner]) and seen["cwd"] == str(root)


# ── Vrai « forge project:check » : frontière d'exécution ────────────────────

SENTINELS = ("ROUTES_IMPORTED", "CONTROLLER_IMPORTED", "TRANSITIVE_IMPORTED")
SECRETS = ("VerySecret123", "abc123", "MotDePasse9")


@pytest.fixture(scope="module")
def linked_venv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_linked_venv(tmp_path_factory.mktemp("venv") / ".venv")


def sentinel_project(root: Path, venv: Path, routes_tail: str = "") -> Path:
    """Projet conforme dont chaque niveau d'import écrit sa sentinelle."""
    real_project(root, venv)
    touch = "import pathlib\npathlib.Path({!r}).touch()\n"
    (root / "config.py").write_text(touch.format(str(root / "CONFIG_EXECUTED")))
    (root / "mvc/routes/__init__.py").write_text(
        touch.format(str(root / "ROUTES_IMPORTED"))
        + "from mvc.controllers.users import UsersController\n"
        + "router = object()\n"
        + routes_tail
    )
    (root / "mvc/controllers/users.py").write_text(
        touch.format(str(root / "CONTROLLER_IMPORTED"))
        + "import sys\nimport app_side_effect\n"
        + "print('DB_PASSWORD=VerySecret123 SERVICE_TOKEN=abc123')\n"
        + "print('connexion mysql://roger:MotDePasse9@db.local/app', file=sys.stderr)\n"
        + "class UsersController:\n    pass\n"
    )
    (root / "mvc/controllers/unused.py").write_text(
        touch.format(str(root / "UNUSED_IMPORTED"))
    )
    # Module du projet hors mvc/, importé par le contrôleur (import transitif).
    (root / "app_side_effect.py").write_text(
        touch.format(str(root / "TRANSITIVE_IMPORTED"))
    )
    return root


def _outside_venv(root: Path) -> dict[str, Any]:
    return {k: v for k, v in snapshot(root).items() if "/.venv/" not in k + "/"}


def test_real_check_executes_routes_controllers_and_transitive_imports(
    tmp_path: Path, linked_venv: Path
) -> None:
    root = sentinel_project(tmp_path / "projet", linked_venv)
    before = _outside_venv(root)
    result = check(root)
    assert result.status == "succeeded" and result.exit_code == 0, result
    # -P : le CLI officiel, jamais le forge.py du projet ; la sortie du code
    # importé précède le rapport.
    assert "Forge project:check — 1.0.0rc9" in result.stdout
    assert "forge.py du projet exécuté" not in result.stdout + result.stderr
    assert "[OK]    Routes — mvc/routes/__init__.py valide" in result.stdout
    assert "Tout est conforme." in result.stdout
    # Frontière démontrée : exécutés…
    for name in SENTINELS:
        assert (root / name).exists(), name
    # … jamais exécutés : config.py (non chargé par la commande) et un
    # contrôleur que les routes n'importent pas.
    assert not (root / "CONFIG_EXECUTED").exists()
    assert not (root / "UNUSED_IMPORTED").exists()
    # Seules différences : les sentinelles écrites par le code applicatif ;
    # Forge Design n'écrit rien, -B empêche tout __pycache__.
    after = _outside_venv(root)
    assert sorted(set(after) - set(before)) == sorted(str(root / n) for n in SENTINELS)
    assert {k: v for k, v in after.items() if k in before} == before
    assert not list(root.rglob("__pycache__"))
    # Secrets imprimés par le code importé : masqués.
    shown = result.stdout + result.stderr
    for value in SECRETS:
        assert value not in shown
    assert f"DB_PASSWORD={M} SERVICE_TOKEN={M}" in result.stdout
    assert f"mysql://roger:{M}@db.local/app" in result.stderr


def test_child_started_by_imported_code_never_survives(
    tmp_path: Path, linked_venv: Path
) -> None:
    tail = (
        "import subprocess, pathlib\n"
        "child = subprocess.Popen(['sleep', '60'])\n"
        f"pathlib.Path({str(tmp_path / 'child.pid')!r}).write_text(str(child.pid))\n"
    )
    root = sentinel_project(tmp_path / "projet", linked_venv, tail)
    result = check(root, timeout=5.0)
    # L'enfant garde les tubes : la commande se termine, puis le délai joue.
    assert "Forge project:check" in result.stdout
    child = int((tmp_path / "child.pid").read_text())
    deadline = time.monotonic() + 2
    while alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(child)


def test_blocking_import_with_child_times_out_and_group_is_killed(
    tmp_path: Path, linked_venv: Path
) -> None:
    tail = (
        "import subprocess, pathlib, time\n"
        "child = subprocess.Popen(['sleep', '60'])\n"
        f"pathlib.Path({str(tmp_path / 'child.pid')!r}).write_text(str(child.pid))\n"
        "time.sleep(30)\n"
    )
    root = sentinel_project(tmp_path / "projet", linked_venv, tail)
    started = time.monotonic()
    result = check(root, timeout=2.0)
    assert time.monotonic() - started < 6
    assert result.status == "timed-out" and result.exit_code is None
    assert result.message == "Vérification interrompue : délai dépassé."
    child = int((tmp_path / "child.pid").read_text())
    deadline = time.monotonic() + 2
    while alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(child)


def test_non_daemon_thread_keeps_process_alive_until_timeout(
    tmp_path: Path, linked_venv: Path
) -> None:
    tail = (
        "import threading, time\n"
        "threading.Thread(target=time.sleep, args=(30,)).start()\n"
    )
    root = sentinel_project(tmp_path / "projet", linked_venv, tail)
    result = check(root, timeout=3.0)
    # Le thread du projet empêche la sortie : délai. Avec -u (FD-RUNTIME-004),
    # le rapport déjà écrit est dans le tube et reste conservé (perdu avant).
    assert result.status == "timed-out" and result.exit_code is None
    assert "Forge project:check — 1.0.0rc9" in result.stdout
    assert "Tout est conforme." in result.stdout
    assert f"DB_PASSWORD={M} SERVICE_TOKEN={M}" in result.stdout
    assert f"mysql://roger:{M}@db.local/app" in result.stderr


def test_system_exit_from_imported_code_ends_without_report(
    tmp_path: Path, linked_venv: Path
) -> None:
    tail = "print('API_TOKEN=abc123 avant sortie')\nraise SystemExit(3)\n"
    root = sentinel_project(tmp_path / "projet", linked_venv, tail)
    result = check(root)
    assert (result.status, result.exit_code) == ("exit-code", 3)
    assert "Forge project:check" not in result.stdout
    assert f"API_TOKEN={M} avant sortie" in result.stdout
    assert "abc123" not in result.stdout


def test_detached_session_escapes_the_group(tmp_path: Path, linked_venv: Path) -> None:
    """Limite documentée : un processus qui crée sa propre session sort du groupe
    lancé par Forge Design ; seul ce groupe est arrêté (d'où la formulation de
    l'avertissement)."""
    tail = (
        "import subprocess, pathlib\n"
        "child = subprocess.Popen(['sleep', '60'], start_new_session=True,\n"
        "    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        f"pathlib.Path({str(tmp_path / 'detached.pid')!r}).write_text(str(child.pid))\n"
    )
    root = sentinel_project(tmp_path / "projet", linked_venv, tail)
    check(root)
    detached = int((tmp_path / "detached.pid").read_text())
    try:
        assert alive(detached)
    finally:
        os.kill(detached, signal.SIGKILL)
