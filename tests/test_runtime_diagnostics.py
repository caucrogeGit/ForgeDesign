"""Runner du diagnostic Forge (FD-RUNTIME-001) : commande exacte, dossier,
environnement, codes retour, sorties bornées et nettoyées, délai, processus enfants,
aucune écriture dans le projet."""

import ast
import json
import os
import shutil
import site
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import HOSTILE, alive, fake_interpreter, forge_project
from test_project_health import snapshot

from forge_design.forge import runtime_diagnostics
from forge_design.forge.checked_root import check_forge_root
from forge_design.forge.project_python import CHILD_ENVIRONMENT_WHITELIST
from forge_design.forge.runtime_diagnostics import (
    DIAGNOSTIC_ARGUMENTS,
    clean_output,
    run_forge_diagnostic,
)
from forge_design.limits import (
    FORGE_DIAGNOSTIC_TIMEOUT_SECONDS,
    MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES,
)


def run(root: Path, **options: Any) -> Any:
    return run_forge_diagnostic(check_forge_root(root), **options)


def test_command_cwd_and_environment_are_fixed(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "argv")
    environ = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "LANG": "C.UTF-8",
        "PYTHONPATH": "/injecté",
        "PYTHONHOME": "/injecté",
        "DB_ADMIN_PASSWORD": "secret",
        "API_TOKEN": "secret",
    }
    result = run(root, environ=environ)
    assert result.status == "succeeded" and result.exit_code == 0
    seen = json.loads(result.stdout)
    # Interpréteur du projet, arguments exacts : -s -B -P -m forge doctor.
    assert DIAGNOSTIC_ARGUMENTS == ("-s", "-B", "-P", "-u", "-m", "forge", "doctor")
    assert seen["argv"] == list(DIAGNOSTIC_ARGUMENTS)
    assert seen["cwd"] == str(root)
    # PWD est posé par /bin/sh, lanceur du faux interpréteur, pas par Forge Design.
    assert set(seen["env"]) - {"PWD"} <= set(CHILD_ENVIRONMENT_WHITELIST)
    assert {"PATH", "HOME", "LANG"} <= set(seen["env"])
    assert result.interpreter == ".venv/bin/python"


def test_launcher_receives_exactly_the_project_interpreter(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    calls: list[tuple[list[str], Path, dict[str, str]]] = []

    def launcher(argv: Any, cwd: Path, env: Any) -> Any:
        calls.append((list(argv), cwd, dict(env)))
        return runtime_diagnostics._spawn(argv, cwd, env)  # pyright: ignore[reportPrivateUsage]

    run(root, launcher=launcher, environ={"PATH": "/usr/bin:/bin", "SECRET": "x"})
    ((argv, cwd, env),) = calls
    assert argv == [str(root / ".venv/bin/python"), *DIAGNOSTIC_ARGUMENTS]
    assert cwd == root and env == {"PATH": "/usr/bin:/bin"}


def test_spawn_never_uses_a_shell() -> None:
    source = Path(runtime_diagnostics.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "shell":
            assert isinstance(node.value, ast.Constant) and node.value.value is False
    for forbidden in ("os.system", "os.popen", "eval(", "exec(", "shell=True"):
        assert forbidden not in source, forbidden
    assert "start_new_session=True" in source and "stdin=subprocess.DEVNULL" in source


@pytest.mark.parametrize(
    ("mode", "status", "code"),
    [("ok", "succeeded", 0), ("fail", "checks-failed", 1), ("code3", "exit-code", 3)],
)
def test_exit_codes(tmp_path: Path, mode: str, status: str, code: int) -> None:
    result = run(forge_project(tmp_path / "projet", mode))
    assert (result.status, result.exit_code, result.timed_out) == (status, code, False)
    if mode == "fail":
        assert "[FAIL]  Structure MVC" in result.stdout
        assert result.stderr.strip() == "trace simulée"
    assert result.duration > 0


def test_hostile_output_is_plain_text_without_ansi(tmp_path: Path) -> None:
    result = run(forge_project(tmp_path / "projet", "hostile"))
    first = result.stdout.splitlines()[0]
    assert first == HOSTILE + " rouge fin�nul"
    assert "\x1b" not in result.stdout and "\x00" not in result.stdout
    assert result.stderr.strip() == HOSTILE


def test_sensitive_assignments_are_masked(tmp_path: Path) -> None:
    result = run(forge_project(tmp_path / "projet", "secret"))
    shown = result.stdout + result.stderr
    for secret in ("hunter", "k3y-777", "abc999", "t0ken-99"):
        assert secret not in shown
    assert result.stdout.splitlines() == [
        "password=[masqué] api_key: [masqué] visible",
        "DB_PASSWORD=[masqué] vers mysql://roger:[masqué]@db.local/app "
        "API_TOKEN=[masqué]",
    ]
    assert result.stderr.splitlines() == [
        "Authorization: [masqué]",
        "HTTP_AUTHORIZATION=[masqué]",
    ]


def test_clean_output() -> None:
    assert clean_output(b"\x1b[1;31mA\x1b[0m\x1b[2K") == "A"
    assert clean_output(b"\x1b]8;;http://x\x1b\\lien\x1b]8;;\x1b\\") == "lien"
    assert clean_output(b"a\tb\r\nc\x07d") == "a\tb\r\nc�d"
    assert clean_output(b"\xff\xfe") == "��"


def test_outputs_are_bounded_while_reading(tmp_path: Path) -> None:
    result = run(forge_project(tmp_path / "projet", "big"))
    assert result.status == "succeeded"
    assert len(result.stdout) == MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES == 256 * 1024
    assert len(result.stderr) == MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES
    assert result.stdout_truncated == result.stderr_truncated == 768 * 1024
    small = run(forge_project(tmp_path / "petit", "big"), limit=10)
    assert small.stdout == "o" * 10 and small.stdout_truncated == 1024 * 1024 - 10


def test_timeout_kills_the_whole_group(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "child")
    started = time.monotonic()
    result = run(root, timeout=1.0)
    assert time.monotonic() - started < 5
    assert result.status == "timed-out" and result.timed_out
    assert result.exit_code is None
    assert result.message == "Diagnostic interrompu : délai dépassé."
    grandchild = int((root / "fake-child-pid").read_text())
    deadline = time.monotonic() + 2
    while alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(grandchild)


def test_no_child_survives_a_normal_exit(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "orphan")
    result = run(root, timeout=3.0)
    # Le petit-enfant garde les tubes ouverts : le délai s'applique, puis le
    # groupe entier est tué.
    grandchild = int((root / "fake-child-pid").read_text())
    deadline = time.monotonic() + 2
    while alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(grandchild)
    assert result.status in {"timed-out", "succeeded"}


def test_default_bounds() -> None:
    assert FORGE_DIAGNOSTIC_TIMEOUT_SECONDS == 10.0


def test_missing_or_unusable_interpreter_is_a_controlled_failure(
    tmp_path: Path,
) -> None:
    root = forge_project(tmp_path / "projet", None)
    result = run(root)
    assert result.status == "launch-failed" and result.exit_code is None
    assert result.message == (
        "Interpréteur du projet introuvable ou inutilisable (.venv/bin/python) : "
        "diagnostic non lancé."
    )
    # Lien de .venv/bin : refusé, jamais suivi ; aucun repli sur un autre Python.
    elsewhere = tmp_path / "ailleurs"
    fake_interpreter(elsewhere, "ok")
    (root / ".venv").symlink_to(elsewhere / ".venv")
    assert run(root).status == "launch-failed"
    (root / ".venv").unlink()
    fake_interpreter(root, "ok")
    (root / ".venv/bin/python").chmod(0o644)
    assert run(root).status == "launch-failed"


def test_launch_error_is_reported(tmp_path: Path) -> None:
    def broken(*args: Any) -> Any:
        raise PermissionError(13, "Permission non accordée")

    result = run(forge_project(tmp_path / "projet", "ok"), launcher=broken)
    assert result.status == "launch-failed"
    assert result.message == "Lancement impossible : Permission non accordée."


def test_runner_needs_a_checked_forge_root(tmp_path: Path) -> None:
    from forge_design.forge.project_root import ProjectRootNotFoundError
    from forge_design.forge.project_version import NotForgeProjectError

    with pytest.raises(ProjectRootNotFoundError):
        check_forge_root(tmp_path / "absent")
    (tmp_path / "pas-forge").mkdir()
    with pytest.raises(NotForgeProjectError):
        check_forge_root(tmp_path / "pas-forge")


def test_project_is_not_modified(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "hostile")
    before = snapshot(root)
    run(root)
    assert snapshot(root) == before


def test_real_forge_doctor_in_a_project_venv(tmp_path: Path) -> None:
    """Vrai ``forge doctor`` : venv du projet relié au forge-mvc installé ici."""
    root = forge_project(tmp_path / "projet", None)
    (root / "forge.py").write_text("raise SystemExit('forge.py du projet exécuté')")
    venv = root / ".venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)],
        check=True,
        timeout=60,
    )
    target = next(venv.glob("lib/python*/site-packages"))
    (target / "forge_mvc.pth").write_text("\n".join(site.getsitepackages()) + "\n")
    if shutil.which("python3") is None:
        pytest.skip("python3 indisponible")
    before = snapshot(root)
    result = run(root)
    assert result.status in {"succeeded", "checks-failed"}, result
    # -P : le CLI officiel, jamais le forge.py du projet.
    assert result.stdout.lstrip().startswith("Forge doctor — ")
    assert "forge.py du projet" not in result.stdout + result.stderr
    # -B : aucun bytecode (ni config.py ni autre) écrit dans le projet.
    after = {k: v for k, v in snapshot(root).items() if "/.venv/" not in k + "/"}
    assert after == {k: v for k, v in before.items() if "/.venv/" not in k + "/"}
