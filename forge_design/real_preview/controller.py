"""Runner local de la preview réelle (FD-REALPREVIEW-002).

Le projet n'est jamais importé ici : il s'exécute dans un processus enfant,
lancé sans shell avec l'interpréteur du projet et le bootstrap autonome
child_bootstrap.py, qui lie lui-même 127.0.0.1:<port>. La sonde /health ne
sert qu'à la readiness. Aucun état n'est écrit sur disque.

Les fonctions de module préfixées par _ (lancement, port, sonde, signaux,
horloge) sont les seuls points de substitution des tests.
"""

import json
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import Message
from http.client import HTTPException
from os import PathLike
from pathlib import Path
from stat import S_ISREG
from typing import IO, Protocol

from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.real_preview.models import (
    RealPreviewConfig,
    RealPreviewError,
    RealPreviewState,
    RealPreviewStatus,
)

HOST = "127.0.0.1"
_POSIX = os.name == "posix"
_ENVIRONMENT_WHITELIST = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR")
_HEALTH_BODY_LIMIT = 1024
_WAIT_STEP = 0.05
_READER_JOIN_TIMEOUT = 2.0
_EXIT_REASONS = {
    2: "arguments du bootstrap invalides",
    3: "Forge incompatible",
    4: "port occupé",
    5: "import du projet impossible",
    6: "bind impossible",
}


class _Process(Protocol):
    """Sous-ensemble de subprocess.Popen utilisé ici (jamais exposé)."""

    @property
    def pid(self) -> int: ...

    @property
    def returncode(self) -> int | None: ...

    @property
    def stdout(self) -> IO[str] | None: ...

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


def _spawn(command: list[str], cwd: Path, env: dict[str, str]) -> _Process:
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        shell=False,
        start_new_session=True,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _allocate_port() -> int:
    """Port éphémère loopback ; le socket est fermé avant le lancement."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        port: int = probe.getsockname()[1]
    if not 1024 <= port <= 65535:
        raise OSError(f"Port alloué hors intervalle : {port}.")
    return port


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Une redirection de /health n'est jamais suivie (elle devient une erreur)."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> None:
        return None


def _probe_health(port: int, timeout: float) -> bool:
    """GET /health direct (aucun proxy, aucune redirection), corps exact."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(f"http://{HOST}:{port}/health", timeout=timeout) as response:
            if response.status != 200:
                return False
            if response.headers.get_content_type() != "application/json":
                return False
            body = response.read(_HEALTH_BODY_LIMIT + 1)
    except (urllib.error.URLError, HTTPException, OSError, ValueError):
        return False
    if len(body) > _HEALTH_BODY_LIMIT:
        return False
    try:
        return json.loads(body) == {"status": "ok"}
    except ValueError:
        return False


def _signal_group(pid: int, signum: int) -> None:
    """Signal au groupe créé par start_new_session ; groupe disparu ignoré."""
    try:
        os.killpg(pid, signum)
    except ProcessLookupError:
        pass


def _leader_exited(pid: int) -> bool | None:
    """Leader terminé, sans le récolter : son PID réserve encore le groupe.

    None si os.waitid manque (macOS) : l'appelant récolte alors directement.
    """
    waitid = getattr(os, "waitid", None)
    if waitid is None:
        return None
    try:
        result = waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return True
    return result is not None


_clock: Callable[[], float] = time.monotonic
_sleep: Callable[[float], None] = time.sleep


def _project_interpreter(root: Path) -> Path | None:
    """<racine>/.venv/bin/python : dossiers sans lien, cible fichier exécutable.

    Le chemin non résolu est retourné : l'interpréteur reconnaît son venv par
    l'emplacement invoqué, pas par la cible du lien.
    """
    try:
        with open_directory(str(root / ".venv" / "bin")):
            pass
        python = root / ".venv" / "bin" / "python"
        target = python.resolve(strict=True)
        if not S_ISREG(target.stat().st_mode) or not os.access(target, os.X_OK):
            return None
    except (OSError, RuntimeError):
        return None
    return python


def _bootstrap_path() -> Path | None:
    path = Path(__file__).resolve().with_name("child_bootstrap.py")
    return path if path.is_file() else None


def _child_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Liste blanche construite positivement ; APP_ENV fixé."""
    environment = {
        name: source[name] for name in _ENVIRONMENT_WHITELIST if name in source
    }
    environment["APP_ENV"] = "dev"
    return environment


def _exit_reason(code: int) -> str:
    if code in _EXIT_REASONS:
        return _EXIT_REASONS[code]
    if code < 0:
        return f"arrêt inattendu (signal {-code})"
    return f"arrêt inattendu (code {code})"


class _LogBuffer:
    """Dernières lignes, chacune tronquée ; lecture et écriture sous verrou."""

    def __init__(self, max_lines: int, max_chars: int) -> None:
        self.max_chars = max_chars
        self._lines: deque[str] = deque(maxlen=max_lines)
        self._lock = threading.Lock()

    def append(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)

    def snapshot(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._lines)


def _pump(stream: IO[str], buffer: _LogBuffer) -> None:
    """Consommer le tube jusqu'à EOF ; le reste d'une ligne trop longue est jeté."""
    limit = buffer.max_chars
    try:
        while chunk := stream.readline(limit):
            if chunk.endswith("\n"):
                buffer.append(chunk[:-1])
                continue
            buffer.append(chunk)
            if len(chunk) == limit:
                while (rest := stream.readline(limit)) and not rest.endswith("\n"):
                    pass
    except (OSError, ValueError):
        pass


@dataclass
class _Child:
    process: _Process
    reader: threading.Thread
    port: int

    def reap(self) -> int | None:
        """Code de sortie une fois le leader terminé ; survivants du groupe tués."""
        if self.process.returncode is not None:
            return self.process.returncode
        exited = _leader_exited(self.process.pid)
        if exited is None:
            return self.process.poll()
        if not exited:
            return None
        _signal_group(self.process.pid, signal.SIGKILL)
        return self.process.wait()

    def wait_exit(self, timeout: float) -> int | None:
        deadline = _clock() + timeout
        while (code := self.reap()) is None:
            if _clock() >= deadline:
                return None
            _sleep(_WAIT_STEP)
        return code

    def release(self) -> None:
        """Après la fin du leader : attendre le lecteur puis fermer le tube."""
        self.reader.join(_READER_JOIN_TIMEOUT)
        if not self.reader.is_alive() and self.process.stdout is not None:
            self.process.stdout.close()


class RealPreviewController:
    """Au plus une preview réelle ; synchrone, sans singleton ni état disque."""

    def __init__(self, config: RealPreviewConfig | None = None) -> None:
        self._config = config if config is not None else RealPreviewConfig()
        self._lock = threading.Lock()
        self._operation = threading.Lock()
        self._cancel = threading.Event()
        self._state: RealPreviewState = "stopped"
        self._root: Path | None = None
        self._child: _Child | None = None
        self._pid: int | None = None
        self._port: int | None = None
        self._exit_code: int | None = None
        self._error: str | None = None
        self._logs = self._new_logs()

    def _new_logs(self) -> _LogBuffer:
        return _LogBuffer(self._config.max_log_lines, self._config.max_log_chars)

    def _snapshot_locked(self) -> RealPreviewStatus:
        return RealPreviewStatus(
            state=self._state,
            project_root=self._root,
            pid=self._pid,
            port=self._port,
            exit_code=self._exit_code,
            error=self._error,
            logs=self._logs.snapshot(),
        )

    def _refresh_locked(self) -> None:
        """starting/running dont le leader est terminé → failed."""
        if self._state not in ("starting", "running") or self._child is None:
            return
        code = self._child.reap()
        if code is not None:
            self._state = "failed"
            self._exit_code = code
            self._error = _exit_reason(code)

    def status(self) -> RealPreviewStatus:
        with self._lock:
            self._refresh_locked()
            return self._snapshot_locked()

    def _fail(self, error: str) -> RealPreviewStatus:
        with self._lock:
            self._state = "failed"
            self._error = error
            return self._snapshot_locked()

    def _launch_plan(
        self, project_root: str | PathLike[str]
    ) -> tuple[Path, list[str], int] | str:
        """Commande dérivée du seul projet ; message d'erreur sinon, sans lancement."""
        if not _POSIX:
            return "Preview réelle indisponible sur cette plateforme."
        try:
            root = resolve_project_root(project_root)
        except ValueError as error:
            return f"Racine projet invalide : {error}"
        with self._lock:
            self._root = root
        if not detect_forge_project(root).valid:
            return "Projet Forge non reconnu."
        interpreter = _project_interpreter(root)
        if interpreter is None:
            return "Interpréteur du projet introuvable (.venv/bin/python)."
        bootstrap = _bootstrap_path()
        if bootstrap is None:
            return "Bootstrap de preview introuvable dans l'installation Forge Design."
        try:
            port = _allocate_port()
        except OSError:
            return "Aucun port loopback disponible."
        command = [str(interpreter), "-I", "-u", str(bootstrap), "--port", str(port)]
        return root, command, port

    def start(self, project_root: str | PathLike[str]) -> RealPreviewStatus:
        """Lancer puis attendre running ou failed, au plus startup_timeout."""
        if not self._operation.acquire(blocking=False):
            raise RealPreviewError("Une opération de preview réelle est en cours.")
        try:
            with self._lock:
                self._refresh_locked()
                if self._state not in ("stopped", "failed"):
                    raise RealPreviewError(
                        f"Preview réelle déjà active (état {self._state})."
                    )
                previous = self._child
            if previous is not None and not self._dispose(previous):
                return self._fail("Le processus précédent est toujours actif.")
            with self._lock:
                self._state = "starting"
                self._root = None
                self._child = None
                self._pid = self._port = self._exit_code = None
                self._error = None
                self._logs = self._new_logs()
            plan = self._launch_plan(project_root)
            if isinstance(plan, str):
                return self._fail(plan)
            root, command, port = plan
            try:
                process = _spawn(command, root, _child_environment(os.environ))
            except OSError as error:
                return self._fail(f"Lancement impossible : {error.strerror or error}")
            stream = process.stdout
            assert stream is not None
            reader = threading.Thread(
                target=_pump,
                args=(stream, self._logs),
                name="forge-design-real-preview-logs",
                daemon=True,
            )
            reader.start()
            child = _Child(process, reader, port)
            with self._lock:
                self._child = child
                self._pid = process.pid
                self._port = port
            return self._await_ready(child)
        finally:
            self._operation.release()

    def _await_ready(self, child: _Child) -> RealPreviewStatus:
        deadline = _clock() + self._config.startup_timeout
        while True:
            if self._cancel.is_set():
                return self.status()
            with self._lock:
                self._refresh_locked()
                state = self._state
            if state != "starting":
                if state == "failed":
                    child.release()
                return self.status()
            if _probe_health(child.port, self._config.probe_timeout):
                with self._lock:
                    if self._state == "starting":
                        self._state = "running"
                    return self._snapshot_locked()
            if _clock() >= deadline:
                code = self._terminate(child)
                limit = self._config.startup_timeout
                error = f"Délai de démarrage dépassé ({limit:g} s)."
                if code is None:
                    error += " Processus impossible à arrêter."
                with self._lock:
                    self._state = "failed"
                    self._exit_code = code
                    self._error = error
                    return self._snapshot_locked()
            _sleep(self._config.probe_interval)

    def _terminate(self, child: _Child) -> int | None:
        """SIGTERM au groupe, attente bornée, SIGKILL au groupe, attente bornée."""
        pid = child.process.pid
        if (code := child.reap()) is None:
            _signal_group(pid, signal.SIGTERM)
            code = child.wait_exit(self._config.terminate_timeout)
        if code is None:
            _signal_group(pid, signal.SIGKILL)
            code = child.wait_exit(self._config.kill_timeout)
        if code is not None:
            child.release()
        return code

    def _dispose(self, child: _Child) -> bool:
        """Nettoyer un enfant déjà en échec ; False s'il reste vivant."""
        code = self._terminate(child)
        with self._lock:
            if self._child is child and code is not None:
                self._child = None
        return code is not None

    def stop(self) -> RealPreviewStatus:
        """Arrêt contrôlé ; sans effet depuis stopped. Interrompt un start en cours."""
        self._cancel.set()
        try:
            with self._operation:
                with self._lock:
                    self._refresh_locked()
                    child = self._child
                    if self._state == "stopped" or (
                        self._state == "failed" and child is None
                    ):
                        self._state = "stopped"
                        self._pid = self._port = None
                        return self._snapshot_locked()
                    self._state = "stopping"
                assert child is not None
                code = self._terminate(child)
                with self._lock:
                    if code is None:
                        self._state = "failed"
                        self._error = "Processus de preview impossible à arrêter."
                    else:
                        self._state = "stopped"
                        self._child = None
                        self._pid = self._port = None
                        self._exit_code = code
                        self._error = None
                    return self._snapshot_locked()
        finally:
            self._cancel.clear()
