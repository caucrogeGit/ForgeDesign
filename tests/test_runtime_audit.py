"""Audit officiel Forge (FD-RUNTIME-002) : commande exacte, liste fermée des
commandes, codes retour, sorties nettoyées et masquées, délai, interpréteur,
aucune écriture, et vrai ``forge project:audit`` sans exécution du projet."""

import ast
import json
import os
import shutil
import site
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from runtime_diagnostics_support import alive, forge_project, make_linked_venv
from test_project_health import snapshot

import forge_design
from forge_design.forge import runtime_diagnostics
from forge_design.forge.checked_root import CheckedForgeRoot, check_forge_root
from forge_design.forge.project_python import CHILD_ENVIRONMENT_WHITELIST
from forge_design.forge.runtime_diagnostics import (
    AUDIT_ARGUMENTS,
    DIAGNOSTIC_ARGUMENTS,
    ForgeDiagnosticRun,
    run_forge_diagnostic,
    run_forge_project_audit,
    run_forge_project_check,
)

M = "[masqué]"
Runner = Callable[[CheckedForgeRoot], ForgeDiagnosticRun]


def audit(root: Path, **options: Any) -> Any:
    return run_forge_project_audit(check_forge_root(root), **options)


def test_command_cwd_and_environment_are_fixed(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "argv")
    environ = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "PYTHONPATH": "/injecté",
        "VIRTUAL_ENV": "/injecté",
        "APP_ENV": "prod",
        "DB_PASSWORD": "secret",
    }
    result = audit(root, environ=environ)
    seen = json.loads(result.stdout)
    assert AUDIT_ARGUMENTS == ("-s", "-B", "-P", "-m", "forge", "project:audit")
    assert seen["argv"] == list(AUDIT_ARGUMENTS)
    assert seen["cwd"] == str(root)
    # Aucun APP_ENV : l'audit ne le lit pas, Forge Design ne le force pas.
    assert set(seen["env"]) - {"PWD"} <= set(CHILD_ENVIRONMENT_WHITELIST)
    assert "APP_ENV" not in seen["env"]


def test_launcher_receives_exactly_the_audit_argv(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    calls: list[list[str]] = []

    def launcher(argv: Any, cwd: Path, env: Any) -> Any:
        calls.append(list(argv))
        return runtime_diagnostics._spawn(argv, cwd, env)  # pyright: ignore[reportPrivateUsage]

    audit(root, launcher=launcher)
    run_forge_diagnostic(check_forge_root(root), launcher=launcher)
    interpreter = str(root / ".venv/bin/python")
    assert calls == [
        [interpreter, *AUDIT_ARGUMENTS],
        [interpreter, *DIAGNOSTIC_ARGUMENTS],
    ]


def test_closed_command_list_is_structural(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "ok")
    commands = runtime_diagnostics._COMMANDS  # pyright: ignore[reportPrivateUsage]
    # Contrat FD-RUNTIME-003 : ensemble exact des trois commandes autorisées.
    assert set(commands) == {"doctor", "project:audit", "project:check"}
    with pytest.raises(TypeError):
        commands["run"] = commands["doctor"]  # type: ignore[index]
    launched: list[object] = []

    def launcher(*args: object) -> Any:
        launched.append(args)
        raise AssertionError("jamais lancé")

    private = runtime_diagnostics._run_forge_command  # pyright: ignore[reportPrivateUsage]
    for name in ("run", "db:apply", "doctor --fix", "project:check --fix", ""):
        with pytest.raises(ValueError, match="non autorisée"):
            private(
                check_forge_root(root),
                name,  # type: ignore[arg-type]
                launcher=launcher,
                environ={},
                timeout=1.0,
                limit=10,
            )
    assert launched == []
    # Seules trois fonctions publiques lancent une commande, chacune la sienne.
    public = sorted(
        name
        for name in vars(runtime_diagnostics)
        if name.startswith("run_") and callable(getattr(runtime_diagnostics, name))
    )
    assert public == [
        "run_forge_diagnostic",
        "run_forge_project_audit",
        "run_forge_project_check",
    ]
    source = Path(runtime_diagnostics.__file__).read_text(encoding="utf-8")
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_run_forge_command"
    ]
    names = [call.args[1] for call in calls]
    assert [n.value for n in names if isinstance(n, ast.Constant)] == [
        "doctor",
        "project:audit",
        "project:check",
    ]
    # Le runner privé n'est importé nulle part ailleurs.
    package = Path(forge_design.__file__).parent
    for path in package.rglob("*.py"):
        if path.name != "runtime_diagnostics.py":
            text = path.read_text(encoding="utf-8")
            assert "_run_forge_command" not in text and "_COMMANDS" not in text, path


@pytest.mark.parametrize(
    ("mode", "status", "code"),
    [("ok", "succeeded", 0), ("fail", "checks-failed", 1), ("code3", "exit-code", 3)],
)
def test_exit_codes(tmp_path: Path, mode: str, status: str, code: int) -> None:
    result = audit(forge_project(tmp_path / "projet", mode))
    assert (result.status, result.exit_code, result.timed_out) == (status, code, False)
    if mode == "fail":
        assert "[FAIL]  Structure MVC" in result.stdout
        assert result.stderr.strip() == "trace simulée"


def test_hostile_and_secret_outputs(tmp_path: Path) -> None:
    hostile = audit(forge_project(tmp_path / "hostile", "hostile"))
    assert "\x1b" not in hostile.stdout and "\x00" not in hostile.stdout
    secret = audit(forge_project(tmp_path / "secret", "secret"))
    shown = secret.stdout + secret.stderr
    for value in ("hunter", "k3y-777", "abc999", "t0ken-99"):
        assert value not in shown
    assert f"mysql://roger:{M}@db.local/app" in secret.stdout


def test_timeout_kills_the_group_with_audit_message(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "child")
    started = time.monotonic()
    result = audit(root, timeout=1.0)
    assert time.monotonic() - started < 5
    assert result.status == "timed-out" and result.exit_code is None
    assert result.message == "Audit interrompu : délai dépassé."
    grandchild = int((root / "fake-child-pid").read_text())
    deadline = time.monotonic() + 2
    while alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not alive(grandchild)


def test_outputs_are_bounded(tmp_path: Path) -> None:
    result = audit(forge_project(tmp_path / "projet", "big"))
    assert len(result.stdout) == len(result.stderr) == 256 * 1024
    assert result.stdout_truncated == result.stderr_truncated == 768 * 1024


def test_missing_interpreter_is_a_controlled_failure(tmp_path: Path) -> None:
    result = audit(forge_project(tmp_path / "projet", None))
    assert result.status == "launch-failed"
    assert result.message == (
        "Interpréteur du projet introuvable ou inutilisable (.venv/bin/python) : "
        "audit non lancé."
    )


def test_project_is_not_modified(tmp_path: Path) -> None:
    root = forge_project(tmp_path / "projet", "hostile")
    before = snapshot(root)
    audit(root)
    assert snapshot(root) == before


def test_concurrent_runs_share_no_state(tmp_path: Path) -> None:
    roots = [forge_project(tmp_path / f"p{i}", "argv") for i in range(4)]
    runners: tuple[Runner, ...] = (run_forge_diagnostic, run_forge_project_audit)
    jobs = [(root, runner) for root in roots for runner in runners]

    def one(job: tuple[Path, Runner]) -> ForgeDiagnosticRun:
        return job[1](check_forge_root(job[0]))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, jobs))
    for (root, runner), result in zip(jobs, results, strict=True):
        seen = json.loads(result.stdout)
        expected = (
            AUDIT_ARGUMENTS
            if runner is run_forge_project_audit
            else DIAGNOSTIC_ARGUMENTS
        )
        assert seen["argv"] == list(expected) and seen["cwd"] == str(root)


# ── Vrai « forge project:audit » ─────────────────────────────────────────────


@pytest.fixture(scope="module")
def linked_venv(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Venv sans pip relié au forge-mvc installé ici, copié dans chaque projet."""
    yield make_linked_venv(tmp_path_factory.mktemp("venv") / ".venv")


def real_project(root: Path, venv: Path | None, *, failing: bool = False) -> Path:
    """Projet Forge conforme ; ``failing`` rend relations.json invalide (FAIL)."""
    for path in ("mvc/routes", "mvc/controllers", "mvc/views", "mvc/entities/article"):
        (root / path).mkdir(parents=True)
    (root / "app.py").write_text("raise SystemExit('app.py exécuté')\n")
    (root / "bootstrap.py").write_text("raise SystemExit('bootstrap.py exécuté')\n")
    # Sentinelle : doctor exécuterait config.py ; l'audit ne doit jamais le faire.
    (root / "config.py").write_text(
        "import pathlib\npathlib.Path(__file__).with_name('CONFIG_EXECUTED').touch()\n"
    )
    (root / "forge.py").write_text("raise SystemExit('forge.py du projet exécuté')\n")
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9\n")
    (root / "mvc/routes/__init__.py").write_text("router = None\n")
    (root / "mvc/controllers/home.py").write_text("raise SystemExit('contrôleur')\n")
    (root / "mvc/views/base.html").write_text("<html></html>\n")
    (root / "env").mkdir()
    (root / "env/example").write_text(
        "APP_NAME=x\nAPP_ROUTES_MODULE=mvc.routes\nDB_NAME=app\nDB_HOST=localhost\n"
    )
    (root / "env/dev").write_text("DB_PASSWORD=VerySecret123\nAPI_TOKEN=abc123\n")
    entities = root / "mvc/entities"
    (entities / "relations.json").write_text("{" if failing else '{"relations": []}')
    article = entities / "article"
    for name in ("article.json", "article.sql", "article_base.py"):
        (article / name).write_text("{}" if name.endswith(".json") else "")
    if venv is not None:
        shutil.copytree(venv, root / ".venv", symlinks=True)
    return root.resolve()


def _outside_venv(root: Path) -> dict[str, Any]:
    return {k: v for k, v in snapshot(root).items() if "/.venv/" not in k + "/"}


def test_real_project_audit_executes_no_project_code(
    tmp_path: Path, linked_venv: Path
) -> None:
    root = real_project(tmp_path / "projet", linked_venv)
    before = _outside_venv(root)
    result = audit(root)
    assert result.status == "succeeded" and result.exit_code == 0, result
    # -P : le CLI officiel, jamais le forge.py du projet.
    assert result.stdout.lstrip().startswith("Forge project:audit — 1.0.0rc9")
    assert "Audit terminé — aucun problème détecté." in result.stdout
    assert "exécuté" not in result.stdout + result.stderr
    # config.py jamais exécuté (différence avec doctor), aucun fichier écrit,
    # aucun __pycache__ (-B).
    assert not (root / "CONFIG_EXECUTED").exists()
    assert _outside_venv(root) == before
    assert not list(root.rglob("__pycache__"))
    # Les valeurs de env/dev ne sont pas affichées.
    for value in ("VerySecret123", "abc123"):
        assert value not in result.stdout + result.stderr


def test_real_project_audit_failure_and_masked_names(
    tmp_path: Path, linked_venv: Path
) -> None:
    root = real_project(tmp_path / "projet", linked_venv, failing=True)
    # Nom légal d'entité, énuméré et imprimé tel quel par l'audit réel.
    (root / "mvc/entities/DB_PASSWORD=VerySecret123").mkdir()
    (root / "mvc/entities/DB_PASSWORD=VerySecret123/x.txt").write_text("")
    result = audit(root)
    assert result.status == "checks-failed" and result.exit_code == 1, result
    assert "[FAIL]  relations.json invalide" in result.stdout
    assert "VerySecret123" not in result.stdout + result.stderr
    assert f"DB_PASSWORD={M}" in result.stdout
    assert not (root / "CONFIG_EXECUTED").exists()


@pytest.mark.parametrize(
    "runner", [run_forge_project_audit, run_forge_diagnostic, run_forge_project_check]
)
def test_user_site_pth_is_never_executed(tmp_path: Path, runner: Any) -> None:
    """-s : dans un venv « --system-site-packages », un .pth du site utilisateur
    serait exécuté au démarrage ; il ne l'est jamais."""
    root = real_project(tmp_path / "projet", None)
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", "--system-site-packages"]
        + [str(root / ".venv")],
        check=True,
        timeout=60,
    )
    target = next((root / ".venv").glob("lib/python*/site-packages"))
    (target / "forge_mvc.pth").write_text("\n".join(site.getsitepackages()) + "\n")
    home = tmp_path / "home"
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    user_site = home / ".local/lib" / version / "site-packages"
    user_site.mkdir(parents=True)
    marker = tmp_path / "USER_SITE_EXECUTED"
    (user_site / "evil.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).touch()\n"
    )
    result = runner(
        check_forge_root(root), environ={"PATH": os.environ["PATH"], "HOME": str(home)}
    )
    assert result.status in {"succeeded", "checks-failed"}, result
    assert not marker.exists()
