"""Runner de preview réelle (FD-REALPREVIEW-002).

Deux couches : un harnais de faux processus (horloge, signaux, sonde) pour les
transitions exactes, puis de vrais processus enfants sur des projets Forge
synthétiques (squelette rc9), avec vérification qu'aucun ne survit.
"""

import ast
import http.client
import io
import os
import runpy
import signal
import socket
import subprocess
import sys
import threading
import time
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import IO, Any

import pytest
from real_preview_support import (
    listening_sockets,
    make_project,
    own_socket_inodes,
    processes_mentioning,
    wait_until_dead,
)

import forge_design.real_preview as real_preview
import forge_design.real_preview.controller as runner
from forge_design.real_preview import (
    RealPreviewConfig,
    RealPreviewController,
    RealPreviewError,
    RealPreviewStatus,
)

REPOSITORY = Path(__file__).resolve().parent.parent
BOOTSTRAP = Path(runner.__file__).resolve().with_name("child_bootstrap.py")


# ── Harnais de faux processus ────────────────────────────────────────────────


class FakeProcess:
    def __init__(self, pid: int, output: str) -> None:
        self.pid = pid
        self.stdout: IO[str] | None = io.StringIO(output)
        self.returncode: int | None = None
        self.exit_code: int | None = None

    def poll(self) -> int | None:
        if self.exit_code is not None:
            self.returncode = self.exit_code
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        if self.exit_code is None:
            raise subprocess.TimeoutExpired("fake", timeout or 0)
        self.returncode = self.exit_code
        return self.exit_code


class Harness:
    """Remplace lancement, port, sonde, signaux et horloge du module runner."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.now = 0.0
        self.port = 40001
        self.output = ""
        self.exit_on_spawn: int | None = None
        self.ready_after: int | None = 0
        self.exit_on_signal: dict[int, int | None] = {
            signal.SIGTERM: -15,
            signal.SIGKILL: -9,
        }
        self.signals: list[tuple[int, bool]] = []
        self.spawned: list[tuple[list[str], Path, dict[str, str]]] = []
        self.processes: list[FakeProcess] = []
        self.probes = 0
        self.allocations = 0
        self.during_probe: Callable[[], None] | None = None
        self.during_signal: Callable[[], None] | None = None
        monkeypatch.setattr(runner, "_spawn", self.spawn)
        monkeypatch.setattr(runner, "_allocate_port", self.allocate)
        monkeypatch.setattr(runner, "_probe_health", self.probe)
        monkeypatch.setattr(runner, "_signal_group", self.signal)
        monkeypatch.setattr(runner, "_leader_exited", self.leader_exited)
        monkeypatch.setattr(runner, "_clock", lambda: self.now)
        monkeypatch.setattr(runner, "_sleep", self.sleep)

    @property
    def process(self) -> FakeProcess:
        return self.processes[-1]

    def spawn(self, command: list[str], cwd: Path, env: dict[str, str]) -> FakeProcess:
        self.spawned.append((command, cwd, env))
        process = FakeProcess(4_000_000 + len(self.processes), self.output)
        process.exit_code = self.exit_on_spawn
        self.processes.append(process)
        return process

    def allocate(self) -> int:
        self.allocations += 1
        return self.port

    def probe(self, port: int, timeout: float) -> bool:
        assert port == self.port
        self.probes += 1
        if self.during_probe is not None:
            self.during_probe()
        return self.ready_after is not None and self.probes > self.ready_after

    def signal(self, pid: int, signum: int) -> None:
        process = next(p for p in self.processes if p.pid == pid)
        self.signals.append((signum, process.exit_code is None))
        if self.during_signal is not None:
            self.during_signal()
        code = self.exit_on_signal.get(signum)
        if code is not None and process.exit_code is None:
            process.exit_code = code

    def leader_exited(self, pid: int) -> bool:
        return next(p for p in self.processes if p.pid == pid).exit_code is not None

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(monkeypatch)


def fake_project(root: Path) -> Path:
    """Signatures Forge et .venv/bin/python, sans exécution."""
    (root / "mvc" / "routes").mkdir(parents=True)
    for name in ("app.py", "bootstrap.py", "config.py"):
        (root / name).write_text("")
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".venv" / "bin" / "python").symlink_to(os.path.realpath(sys.executable))
    return root.resolve()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return fake_project(tmp_path / "projet")


def test_initial_status() -> None:
    assert RealPreviewController().status() == RealPreviewStatus(
        "stopped", None, None, None, None, None, ()
    )


def test_start_command_and_running(harness: Harness, project: Path) -> None:
    harness.ready_after = 2
    status = RealPreviewController().start(project)
    assert status == RealPreviewStatus(
        "running", project, harness.process.pid, 40001, None, None, status.logs
    )
    command, cwd, _ = harness.spawned[0]
    assert command == [
        str(project / ".venv" / "bin" / "python"),
        "-I",
        "-u",
        str(BOOTSTRAP),
        "--port",
        "40001",
    ]
    assert cwd == project
    assert harness.probes == 3
    assert harness.signals == []


def test_spawn_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def popen(command: list[str], **options: Any) -> str:
        calls.append((command, options))
        return "processus"

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    spawn = runner._spawn  # pyright: ignore[reportPrivateUsage]
    spawn(["python", "-I"], tmp_path, {"APP_ENV": "dev"})
    command, options = calls[0]
    assert command == ["python", "-I"]
    assert options["shell"] is False
    assert options["start_new_session"] is True
    assert options["cwd"] == tmp_path
    assert options["env"] == {"APP_ENV": "dev"}
    assert options["stdin"] is subprocess.DEVNULL
    assert options["stdout"] is subprocess.PIPE
    assert options["stderr"] is subprocess.STDOUT
    assert options["text"] is True


def test_environment_is_a_positive_whitelist(
    harness: Harness, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in list(os.environ):
        monkeypatch.delenv(name)
    present = {"PATH": "/bin", "HOME": "/home/x", "LANG": "fr_FR.UTF-8", "TZ": "UTC"}
    hostile = {
        "APP_HOST": "0.0.0.0",
        "APP_PORT": "8000",
        "APP_SSL_ENABLED": "true",
        "APP_ENV": "prod",
        "VIRTUAL_ENV": "/venv",
        "PYTHONPATH": "/evil",
        "PYTHONHOME": "/evil",
        "PYTHONSTARTUP": "/evil.py",
        "XDG_CONFIG_HOME": "/xdg",
        "GITHUB_TOKEN": "ghp_secret",
        "AWS_SECRET_ACCESS_KEY": "secret",
        "CI": "true",
        "SSH_AUTH_SOCK": "/agent",
        "DB_PASSWORD": "secret",
    }
    for name, value in {**present, **hostile}.items():
        monkeypatch.setenv(name, value)
    RealPreviewController().start(project)
    assert harness.spawned[0][2] == {**present, "APP_ENV": "dev"}


def test_root_is_canonical(harness: Harness, project: Path, tmp_path: Path) -> None:
    link = tmp_path / "lien"
    link.symlink_to(project)
    status = RealPreviewController().start(link)
    assert status.project_root == project
    assert harness.spawned[0][1] == project


def _not_forge(root: Path) -> None:
    (root / "config.py").unlink()


def _no_venv(root: Path) -> None:
    (root / ".venv" / "bin" / "python").unlink()
    (root / ".venv" / "bin").rmdir()
    (root / ".venv").rmdir()


def _venv_link(root: Path) -> None:
    (root / ".venv").rename(root / "vrai-venv")
    (root / ".venv").symlink_to(root / "vrai-venv")


def _bin_link(root: Path) -> None:
    (root / ".venv" / "bin").rename(root / ".venv" / "vrai-bin")
    (root / ".venv" / "bin").symlink_to(root / ".venv" / "vrai-bin")


def _python_missing(root: Path) -> None:
    (root / ".venv" / "bin" / "python").unlink()


def _python_dangling(root: Path) -> None:
    (root / ".venv" / "bin" / "python").unlink()
    (root / ".venv" / "bin" / "python").symlink_to(root / "absent")


def _python_not_executable(root: Path) -> None:
    (root / ".venv" / "bin" / "python").unlink()
    (root / "python").write_text("")
    (root / ".venv" / "bin" / "python").symlink_to(root / "python")


def _python_directory(root: Path) -> None:
    (root / ".venv" / "bin" / "python").unlink()
    (root / ".venv" / "bin" / "python").mkdir()


@pytest.mark.parametrize(
    ("damage", "message"),
    [
        (_not_forge, "Projet Forge non reconnu."),
        (_no_venv, "Interpréteur du projet introuvable"),
        (_venv_link, "Interpréteur du projet introuvable"),
        (_bin_link, "Interpréteur du projet introuvable"),
        (_python_missing, "Interpréteur du projet introuvable"),
        (_python_dangling, "Interpréteur du projet introuvable"),
        (_python_not_executable, "Interpréteur du projet introuvable"),
        (_python_directory, "Interpréteur du projet introuvable"),
    ],
)
def test_preconditions_fail_without_spawn(
    harness: Harness, project: Path, damage: Callable[[Path], None], message: str
) -> None:
    damage(project)
    status = RealPreviewController().start(project)
    assert status.state == "failed"
    assert status.error is not None and status.error.startswith(message)
    assert status.project_root == project
    assert (status.pid, status.port) == (None, None)
    assert harness.spawned == [] and harness.allocations == 0


def test_invalid_root(harness: Harness, tmp_path: Path) -> None:
    status = RealPreviewController().start(tmp_path / "absent")
    assert status.state == "failed"
    assert status.project_root is None
    assert status.error is not None and status.error.startswith(
        "Racine projet invalide"
    )
    assert harness.spawned == []


def test_other_platform(
    harness: Harness, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "_POSIX", False)
    status = RealPreviewController().start(project)
    assert status.error == "Preview réelle indisponible sur cette plateforme."
    assert harness.spawned == []


def test_missing_bootstrap(
    harness: Harness, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "_bootstrap_path", lambda: None)
    status = RealPreviewController().start(project)
    assert status.state == "failed" and harness.spawned == []


def test_port_allocation_failure(
    harness: Harness, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_port() -> int:
        raise OSError("épuisé")

    monkeypatch.setattr(runner, "_allocate_port", no_port)
    status = RealPreviewController().start(project)
    assert status.error == "Aucun port loopback disponible."
    assert harness.spawned == []


def test_spawn_failure(
    harness: Harness, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(command: list[str], cwd: Path, env: dict[str, str]) -> FakeProcess:
        raise PermissionError(13, "Permission non accordée")

    monkeypatch.setattr(runner, "_spawn", refuse)
    status = RealPreviewController().start(project)
    assert status.state == "failed"
    assert status.error == "Lancement impossible : Permission non accordée"


@pytest.mark.parametrize(
    ("code", "error"),
    [
        (2, "arguments du bootstrap invalides"),
        (3, "Forge incompatible"),
        (4, "port occupé"),
        (5, "import du projet impossible"),
        (6, "bind impossible"),
        (0, "arrêt inattendu (code 0)"),
        (1, "arrêt inattendu (code 1)"),
        (-9, "arrêt inattendu (signal 9)"),
    ],
)
def test_exit_before_ready(
    harness: Harness, project: Path, code: int, error: str
) -> None:
    harness.exit_on_spawn = code
    status = RealPreviewController().start(project)
    assert (status.state, status.exit_code, status.error) == ("failed", code, error)
    assert harness.probes == 0
    assert harness.allocations == 1 and len(harness.spawned) == 1


def test_spontaneous_exit_after_running(harness: Harness, project: Path) -> None:
    controller = RealPreviewController()
    assert controller.start(project).state == "running"
    harness.process.exit_code = -9
    status = controller.status()
    assert (status.state, status.exit_code) == ("failed", -9)
    assert status.error == "arrêt inattendu (signal 9)"
    assert controller.status() == status


def test_death_detected_by_status_during_starting(
    harness: Harness, project: Path
) -> None:
    controller = RealPreviewController()
    seen: list[RealPreviewStatus] = []

    def die() -> None:
        harness.process.exit_code = 7
        seen.append(controller.status())

    harness.ready_after = None
    harness.during_probe = die
    status = controller.start(project)
    assert seen[0].state == "failed"
    assert (status.state, status.exit_code) == ("failed", 7)
    assert harness.probes == 1


def test_duplicate_start_refused(harness: Harness, project: Path) -> None:
    controller = RealPreviewController()
    controller.start(project)
    with pytest.raises(RealPreviewError, match="état running"):
        controller.start(project)
    assert len(harness.spawned) == 1


def test_start_refused_while_starting(harness: Harness, project: Path) -> None:
    controller = RealPreviewController()
    errors: list[Exception] = []
    states: list[str] = []

    def again() -> None:
        states.append(controller.status().state)
        try:
            controller.start(project)
        except RealPreviewError as error:
            errors.append(error)

    harness.ready_after = 1
    harness.during_probe = again
    assert controller.start(project).state == "running"
    assert states[0] == "starting"
    assert len(errors) == 2 and len(harness.spawned) == 1


def test_start_refused_while_stopping(harness: Harness, project: Path) -> None:
    controller = RealPreviewController()
    controller.start(project)
    errors: list[Exception] = []
    states: list[str] = []

    def again() -> None:
        states.append(controller.status().state)
        try:
            controller.start(project)
        except RealPreviewError as error:
            errors.append(error)

    harness.during_signal = again
    assert controller.stop().state == "stopped"
    assert states[0] == "stopping" and len(errors) >= 1


def test_startup_timeout_stops_group(harness: Harness, project: Path) -> None:
    harness.ready_after = None
    config = RealPreviewConfig(startup_timeout=1.0, probe_interval=0.2)
    status = RealPreviewController(config).start(project)
    assert status.state == "failed"
    assert status.error == "Délai de démarrage dépassé (1 s)."
    assert status.exit_code == -15
    assert harness.signals[0] == (signal.SIGTERM, True)
    assert 1.0 <= harness.now < 1.5


def test_stop_sends_sigterm_to_group(harness: Harness, project: Path) -> None:
    controller = RealPreviewController()
    controller.start(project)
    status = controller.stop()
    assert status == RealPreviewStatus(
        "stopped", project, None, None, -15, None, status.logs
    )
    # SIGTERM au leader vivant ; SIGKILL ensuite aux seuls survivants du groupe.
    assert harness.signals == [(signal.SIGTERM, True), (signal.SIGKILL, False)]


def test_stop_escalates_to_sigkill(harness: Harness, project: Path) -> None:
    harness.exit_on_signal[signal.SIGTERM] = None
    controller = RealPreviewController()
    controller.start(project)
    status = controller.stop()
    assert (status.state, status.exit_code) == ("stopped", -9)
    assert harness.signals[:2] == [(signal.SIGTERM, True), (signal.SIGKILL, True)]
    assert harness.now >= 5.0


def test_unkillable_process_reports_failed(harness: Harness, project: Path) -> None:
    harness.exit_on_signal = {signal.SIGTERM: None, signal.SIGKILL: None}
    controller = RealPreviewController()
    controller.start(project)
    status = controller.stop()
    assert status.state == "failed"
    assert status.error == "Processus de preview impossible à arrêter."
    assert status.pid == harness.process.pid
    assert harness.now >= 7.0
    retry = controller.start(project)
    assert retry.error == "Le processus précédent est toujours actif."
    assert len(harness.spawned) == 1


def test_signal_race_with_dead_group(
    harness: Harness, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = RealPreviewController()
    controller.start(project)
    monkeypatch.undo()
    process = harness.process

    def gone(pid: int, signum: int) -> None:
        process.exit_code = -15
        raise ProcessLookupError

    def exited(pid: int) -> bool:
        return process.exit_code is not None

    monkeypatch.setattr(runner, "_leader_exited", exited)
    monkeypatch.setattr(os, "killpg", gone)
    status = controller.stop()
    assert (status.state, status.error) == ("stopped", None)


def test_stop_from_stopped_is_noop(harness: Harness) -> None:
    controller = RealPreviewController()
    assert controller.stop() == controller.status()
    assert controller.status().state == "stopped"
    assert harness.signals == []


def test_stop_from_failed_without_process(harness: Harness, project: Path) -> None:
    _not_forge(project)
    controller = RealPreviewController()
    assert controller.start(project).state == "failed"
    status = controller.stop()
    assert (status.state, status.pid, status.port) == ("stopped", None, None)


def test_stop_after_spontaneous_exit(harness: Harness, project: Path) -> None:
    controller = RealPreviewController()
    controller.start(project)
    harness.process.exit_code = 1
    assert controller.status().state == "failed"
    status = controller.stop()
    assert (status.state, status.pid, status.port) == ("stopped", None, None)
    assert all(
        signum == signal.SIGKILL and not alive for signum, alive in harness.signals
    )


def test_restart_after_failure_disposes_previous(
    harness: Harness, project: Path
) -> None:
    harness.output = "ancien\n"
    harness.exit_on_spawn = 5
    controller = RealPreviewController()
    assert controller.start(project).state == "failed"
    first = harness.process
    harness.output = "nouveau\n"
    harness.exit_on_spawn = None
    status = controller.start(project)
    assert status.state == "running" and status.pid == harness.process.pid
    assert first.stdout is not None and first.stdout.closed
    final = controller.stop()
    assert final.logs == ("nouveau",)


def test_logs_bounds_exact(harness: Harness, project: Path) -> None:
    harness.output = "abcdefgh\n12345\n123456\nxy"
    controller = RealPreviewController(
        RealPreviewConfig(max_log_lines=3, max_log_chars=5)
    )
    controller.start(project)
    assert controller.stop().logs == ("12345", "12345", "xy")


def test_logs_default_bounds(harness: Harness, project: Path) -> None:
    lines = [f"ligne-{index}" for index in range(250)]
    harness.output = "\n".join(lines) + "\n" + "x" * 5000 + "\n" + "y" * 2000 + "\nfin"
    controller = RealPreviewController()
    controller.start(project)
    logs = controller.stop().logs
    assert len(logs) == 200
    assert logs[-3:] == ("x" * 2000, "y" * 2000, "fin")
    assert logs[0] == "ligne-53"
    assert max(len(line) for line in logs) == 2000


def test_logs_kept_after_stop_and_reset_on_start(
    harness: Harness, project: Path
) -> None:
    harness.output = "premier\n"
    controller = RealPreviewController()
    controller.start(project)
    stopped = controller.stop()
    assert stopped.logs == ("premier",)
    assert controller.status().logs == ("premier",)
    harness.output = ""
    controller.start(project)
    assert controller.stop().logs == ()
    assert stopped.logs == ("premier",)


def test_status_is_an_immutable_snapshot(harness: Harness, project: Path) -> None:
    harness.output = "a\nb\n"
    controller = RealPreviewController()
    running = controller.start(project)
    snapshot = running.logs
    final = controller.stop()
    assert running.logs is snapshot and isinstance(snapshot, tuple)
    assert final.logs == ("a", "b")
    with pytest.raises(FrozenInstanceError):
        running.state = "stopped"  # type: ignore[misc]


# ── Configuration, API, packaging ────────────────────────────────────────────


@pytest.mark.parametrize(
    "options",
    [
        {"startup_timeout": 0},
        {"startup_timeout": -1.0},
        {"probe_timeout": float("nan")},
        {"probe_interval": float("inf")},
        {"terminate_timeout": True},
        {"kill_timeout": "2"},
        {"kill_timeout": 3601},
        {"max_log_lines": 0},
        {"max_log_lines": 1.5},
        {"max_log_lines": True},
        {"max_log_chars": 0},
        {"max_log_chars": 100_001},
    ],
)
def test_config_validation(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        RealPreviewConfig(**options)


def test_config_defaults() -> None:
    assert RealPreviewConfig() == RealPreviewConfig(15.0, 1.0, 0.2, 5.0, 2.0, 200, 2000)


def test_public_exports() -> None:
    assert real_preview.__all__ == [
        "RealPreviewConfig",
        "RealPreviewController",
        "RealPreviewError",
        "RealPreviewProxyConfig",
        "RealPreviewProxyServer",
        "RealPreviewState",
        "RealPreviewStatus",
        "create_real_preview_proxy",
    ]
    assert not hasattr(real_preview, "child_bootstrap") or "child_bootstrap" not in (
        real_preview.__all__
    )


def test_bootstrap_is_packaged() -> None:
    pyproject = tomllib.loads((REPOSITORY / "pyproject.toml").read_text())
    assert "forge_design.real_preview" in pyproject["tool"]["setuptools"]["packages"]
    assert runner._bootstrap_path() == BOOTSTRAP  # pyright: ignore[reportPrivateUsage]


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module.split(".")[0])
    return names


def test_bootstrap_uses_only_the_standard_library() -> None:
    assert _imports(BOOTSTRAP) <= sys.stdlib_module_names


def test_runner_never_imports_or_executes_project_code() -> None:
    source = Path(runner.__file__).read_text()
    assert _imports(Path(runner.__file__)) <= sys.stdlib_module_names | {"forge_design"}
    for forbidden in (
        "runpy",
        "exec(",
        "import_module",
        "sys.path",
        "chdir",
        "shell=True",
    ):
        assert forbidden not in source


def test_allocated_port_is_released() -> None:
    port = runner._allocate_port()  # pyright: ignore[reportPrivateUsage]
    assert 1024 <= port <= 65535
    with socket.socket() as again:
        again.bind(("127.0.0.1", port))


# ── Processus réels ──────────────────────────────────────────────────────────


@pytest.fixture
def live(tmp_path: Path) -> Iterator[Callable[..., RealPreviewController]]:
    """Contrôleurs réels arrêtés en fin de test ; aucun processus ne doit survivre."""
    controllers: list[RealPreviewController] = []

    def create(config: RealPreviewConfig | None = None) -> RealPreviewController:
        controller = RealPreviewController(config)
        controllers.append(controller)
        return controller

    yield create
    for controller in controllers:
        controller.stop()
    leftovers = processes_mentioning(str(tmp_path))
    assert wait_until_dead(leftovers) == []


def _get(port: int, host: str, path: str = "/health") -> tuple[int, str, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.putrequest("GET", path, skip_host=True)
        connection.putheader("Host", host)
        connection.endheaders()
        response = connection.getresponse()
        return (
            response.status,
            response.getheader("Content-Type") or "",
            response.read(),
        )
    finally:
        connection.close()


def test_real_lifecycle(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    root = make_project(tmp_path / "projet").resolve()
    controller = live()
    status = controller.start(root)
    assert status.state == "running", status
    assert status.project_root == root and status.pid is not None
    assert status.port is not None and status.error is None
    assert _get(status.port, f"127.0.0.1:{status.port}") == (
        200,
        "application/json",
        b'{"status": "ok"}',
    )
    stopped = controller.stop()
    assert (stopped.state, stopped.pid, stopped.port) == ("stopped", None, None)
    # Le lecteur est terminé après stop() : les logs sont complets.
    assert f"Preview réelle : écoute sur http://127.0.0.1:{status.port}" in stopped.logs
    assert processes_mentioning(str(root)) == []


def test_real_host_guard(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    status = live().start(make_project(tmp_path / "projet"))
    assert status.port is not None
    for host in ("localhost:%d", "evil.example:%d", "127.0.0.1:%d0", "[::1]:%d"):
        code, content_type, body = _get(status.port, host % status.port)
        assert (code, content_type, body) == (
            400,
            "text/plain; charset=utf-8",
            b"Bad Request\n",
        )


def test_hostile_env_dev_cannot_move_endpoint(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    other = runner._allocate_port()  # pyright: ignore[reportPrivateUsage]
    root = make_project(
        tmp_path / "projet",
        app_prefix=(
            "import config as _config\n"
            "print('ENV-DEV', _config.APP_HOST, _config.APP_PORT,"
            " _config.APP_SSL_ENABLED, flush=True)\n"
        ),
        env_dev=f"APP_HOST=0.0.0.0\nAPP_PORT={other}\nAPP_SSL_ENABLED=true\n",
    )
    controller = live()
    status = controller.start(root)
    assert status.state == "running", status
    # ...mais l'endpoint écoute en HTTP sur 127.0.0.1:<port du parent> seulement.
    assert status.port is not None and status.port != other
    listening = [entry for entries in listening_sockets().values() for entry in entries]
    assert [address for address, port in listening if port == status.port] == [
        "0100007F"
    ]
    assert [address for address, port in listening if port == other] == []
    assert _get(status.port, f"127.0.0.1:{status.port}")[0] == 200
    # Les valeurs hostiles étaient pourtant actives dans l'enfant.
    assert f"ENV-DEV 0.0.0.0 {other} True" in controller.stop().logs


def test_bind_refused_during_project_import(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    root = make_project(
        tmp_path / "projet",
        app_prefix=(
            "import socket as _socket\n"
            "_s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)\n"
            "try:\n"
            "    _s.bind(('0.0.0.0', 0))\n"
            "except PermissionError:\n"
            "    print('BIND-REFUSED', _s.getsockname(), flush=True)\n"
            "    raise\n"
        ),
    )
    status = live().start(root)
    assert (status.state, status.exit_code) == ("failed", 5)
    assert status.error == "import du projet impossible"
    # Port 0 non attribué : l'appel système bind n'a jamais eu lieu.
    assert "BIND-REFUSED ('0.0.0.0', 0)" in status.logs
    assert any("bind refusé sur ('0.0.0.0', 0)" in line for line in status.logs)


def test_port_collision_without_retry(
    live: Callable[..., RealPreviewController],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = make_project(tmp_path / "projet")
    spawn = runner._spawn  # pyright: ignore[reportPrivateUsage]
    calls = {"allocate": 0, "spawn": 0}
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        busy = holder.getsockname()[1]

        def allocate() -> int:
            calls["allocate"] += 1
            return busy

        def counted(command: list[str], cwd: Path, env: dict[str, str]) -> Any:
            calls["spawn"] += 1
            return spawn(command, cwd, env)

        monkeypatch.setattr(runner, "_allocate_port", allocate)
        monkeypatch.setattr(runner, "_spawn", counted)
        status = live().start(root)
    assert (status.state, status.exit_code, status.error) == (
        "failed",
        4,
        "port occupé",
    )
    assert calls == {"allocate": 1, "spawn": 1}


def test_project_import_crash(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    root = make_project(tmp_path / "projet", app_prefix="raise RuntimeError('boom')")
    status = live().start(root)
    assert (status.state, status.exit_code) == ("failed", 5)
    assert "RuntimeError: boom" in status.logs


def test_real_startup_timeout(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    root = make_project(
        tmp_path / "projet", app_prefix="import time as _t\n_t.sleep(60)"
    )
    started = time.monotonic()
    status = live(RealPreviewConfig(startup_timeout=1.0)).start(root)
    assert status.state == "failed"
    assert status.error == "Délai de démarrage dépassé (1 s)."
    assert status.exit_code == -signal.SIGTERM
    assert time.monotonic() - started < 10
    assert wait_until_dead(processes_mentioning(str(root))) == []


def test_real_spontaneous_exit(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    controller = live()
    status = controller.start(make_project(tmp_path / "projet"))
    assert status.pid is not None
    os.kill(status.pid, signal.SIGKILL)
    deadline = time.monotonic() + 5
    while (current := controller.status()).state == "running":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert (current.state, current.exit_code) == ("failed", -9)
    assert current.error == "arrêt inattendu (signal 9)"


def test_real_stop_reaches_process_group(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    root = make_project(
        tmp_path / "projet",
        app_prefix=(
            "import pathlib as _p, subprocess as _sp, sys as _sys\n"
            "_g = _sp.Popen([_sys.executable, '-c', 'import time; time.sleep(120)'])\n"
            "_p.Path('petit-enfant.pid').write_text(str(_g.pid))\n"
        ),
    )
    controller = live()
    assert controller.start(root).state == "running"
    grandchild = int((root / "petit-enfant.pid").read_text())
    assert wait_until_dead([grandchild], timeout=0) == [grandchild]
    assert controller.stop().state == "stopped"
    assert wait_until_dead([grandchild]) == []


def test_real_sigkill_fallback(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    root = make_project(
        tmp_path / "projet",
        app_prefix="import signal as _s\n_s.signal(_s.SIGTERM, _s.SIG_IGN)",
    )
    controller = live(RealPreviewConfig(terminate_timeout=0.5))
    assert controller.start(root).state == "running"
    status = controller.stop()
    assert (status.state, status.exit_code) == ("stopped", -signal.SIGKILL)


def test_real_logs_are_bounded(
    live: Callable[..., RealPreviewController], tmp_path: Path
) -> None:
    root = make_project(
        tmp_path / "projet",
        app_prefix=(
            "for _i in range(250):\n"
            "    print(f'ligne-{_i}')\n"
            "print('y' * 5000, flush=True)\n"
        ),
    )
    controller = live()
    assert controller.start(root).state == "running"
    logs = controller.stop().logs
    assert len(logs) == 200
    assert "y" * 2000 in logs
    assert max(len(line) for line in logs) <= 2000


def test_parent_process_is_untouched(
    live: Callable[..., RealPreviewController],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = make_project(tmp_path / "projet").resolve()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("exécution de code projet dans Forge Design")

    monkeypatch.setattr(runpy, "run_path", forbidden)
    monkeypatch.setattr(runpy, "run_module", forbidden)
    path, environ, cwd = list(sys.path), dict(os.environ), os.getcwd()
    modules = set(sys.modules)
    threads = set(threading.enumerate())
    controller = live()
    status = controller.start(root)
    assert status.state == "running"
    # Le parent n'héberge aucun socket d'écoute : le serveur est dans l'enfant.
    assert own_socket_inodes() & set(listening_sockets()) == set()
    controller.stop()
    assert (sys.path, dict(os.environ), os.getcwd()) == (path, environ, cwd)
    added = set(sys.modules) - modules
    assert not added & {"app", "config", "bootstrap", "mvc", "core.app.wsgi"}
    for name in added:
        location = getattr(sys.modules[name], "__file__", None) or ""
        assert not location.startswith(str(root))
    assert set(threading.enumerate()) <= threads


# ── Sonde /health ────────────────────────────────────────────────────────────


class _HealthStub(BaseHTTPRequestHandler):
    """Réponse fixée par le serveur de test ; Host reçu mémorisé."""

    def do_GET(self) -> None:
        server: Any = self.server
        server.hosts.append(self.headers.get("Host"))
        status, content_type, body, location = server.reply
        if self.path == "/ok":
            # Cible d'une redirection : une santé valide, qui ne doit pas être suivie.
            status, content_type, body, location = (
                200,
                "application/json",
                b'{"status": "ok"}',
                None,
            )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def health_stub() -> Iterator[Any]:
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _HealthStub)
    server.hosts = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def _probe(port: int) -> bool:
    return runner._probe_health(port, 1.0)  # pyright: ignore[reportPrivateUsage]


def test_probe_accepts_exact_health(health_stub: Any) -> None:
    port = health_stub.server_address[1]
    health_stub.reply = (200, "application/json", b'{"status": "ok"}', None)
    assert _probe(port)
    assert health_stub.hosts == [f"127.0.0.1:{port}"]


@pytest.mark.parametrize(
    "reply",
    [
        (200, "application/json", b'{"status": "ko"}', None),
        (200, "application/json", b'{"status": "ok", "extra": 1}', None),
        (200, "text/html", b'{"status": "ok"}', None),
        (200, "application/json", b"ok", None),
        (200, "application/json", b'{"status": "ok"}' + b" " * 2000, None),
        (500, "application/json", b'{"status": "ok"}', None),
        (302, "application/json", b"", "/ok"),
    ],
)
def test_probe_refuses(health_stub: Any, reply: tuple[Any, ...]) -> None:
    health_stub.reply = reply
    assert not _probe(health_stub.server_address[1])
    assert len(health_stub.hosts) == 1


def test_probe_ignores_proxy_environment(
    health_stub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    health_stub.reply = (200, "application/json", b'{"status": "ok"}', None)
    assert _probe(health_stub.server_address[1])


def test_probe_connection_refused() -> None:
    port = runner._allocate_port()  # pyright: ignore[reportPrivateUsage]
    assert not _probe(port)
