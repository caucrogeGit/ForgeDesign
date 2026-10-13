"""Diagnostic officiel Forge exécuté à la demande (FD-RUNTIME-001).

Forge Design ne réimplémente pas ``forge doctor`` : il le lance, sur action
explicite de l'utilisateur, dans un sous-processus séparé du serveur, avec
l'interpréteur du projet :

    <racine>/.venv/bin/python -s -B -P -m forge doctor      (cwd = racine)

- ``-s`` : sans le site-packages de l'utilisateur ;
- ``-B`` : aucun bytecode écrit (lancé tel quel, le diagnostic crée
  ``__pycache__/config.*.pyc`` dans le projet) ;
- ``-P`` : la racine n'est pas insérée en tête de ``sys.path`` par ``-m`` ; sans
  lui, un ``forge.py`` du projet s'exécuterait à la place du CLI officiel. Le
  diagnostic ajoute lui-même la racine au chargement de ``config.py`` : les
  imports locaux du projet restent ceux d'un ``forge doctor`` lancé en terminal.

Le diagnostic exécute ``config.py`` du projet et peut se connecter à la base
configurée : ce n'est pas un bac à sable, c'est une frontière de processus.
Aucun shell, aucun argument venu de HTTP, environnement en liste blanche, durée
bornée (le groupe de processus entier est tué), sorties bornées pendant la
lecture, séquences ANSI retirées, affectations sensibles masquées (le diagnostic
rapporte les messages d'exception des pilotes de base de données). Le texte n'est
jamais interprété : le résultat est le code retour, la durée et les deux flux.
"""

import os
import re
import selectors
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal, Protocol

from forge_design.forge.checked_root import CheckedForgeRoot
from forge_design.forge.debug_redaction import redact_debug_text
from forge_design.forge.project_python import child_environment, project_interpreter
from forge_design.limits import (
    FORGE_DIAGNOSTIC_TIMEOUT_SECONDS,
    MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES,
)

DIAGNOSTIC_ARGUMENTS = ("-s", "-B", "-P", "-m", "forge", "doctor")
INTERPRETER_LABEL = ".venv/bin/python"

DiagnosticStatus = Literal[
    "succeeded", "checks-failed", "exit-code", "launch-failed", "timed-out"
]

_READ_CHUNK = 64 * 1024
# CSI (ESC [ … final), OSC (ESC ] … BEL ou ESC \, borné), puis échappements à deux
# caractères ; appliqué à un texte déjà borné.
_ANSI = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]{0,4096}(?:\x07|\x1b\\)?|\x1b[@-Z\\-_]"
)
# Autres contrôles C0 et DEL, sauf tabulation et fins de ligne.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_REPLACEMENT = chr(0xFFFD)


class DiagnosticProcess(Protocol):
    """Sous-ensemble de subprocess.Popen utilisé par le runner."""

    pid: int
    stdout: IO[bytes] | None
    stderr: IO[bytes] | None

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


Launcher = Callable[[Sequence[str], Path, Mapping[str, str]], DiagnosticProcess]


def _spawn(argv: Sequence[str], cwd: Path, env: Mapping[str, str]) -> DiagnosticProcess:
    """Nouvelle session (groupe tuable en entier), sans shell ni entrée standard."""
    return subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=dict(env),
        shell=False,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@dataclass(frozen=True)
class ForgeDiagnosticRun:
    """Résultat d'une exécution ; appartient à la réponse courante, jamais persisté."""

    status: DiagnosticStatus
    exit_code: int | None
    stdout: str
    stderr: str
    duration: float
    timed_out: bool = False
    stdout_truncated: int = 0
    stderr_truncated: int = 0
    interpreter: str = INTERPRETER_LABEL
    message: str | None = None


def clean_output(data: bytes) -> str:
    """UTF-8 tolérant, séquences ANSI retirées, contrôles remplacés."""
    text = data.decode("utf-8", errors="replace")
    return _CONTROL.sub(_REPLACEMENT, _ANSI.sub("", text))


def _displayed(data: bytes) -> str:
    """Texte affichable : nettoyé, puis masquage de Debug Center (non exhaustif)."""
    return redact_debug_text(clean_output(data))


def _status(code: int) -> DiagnosticStatus:
    # Convention de forge doctor : 0 sans FAIL, 1 avec au moins un FAIL ou une
    # erreur de la commande ; tout autre code est rapporté tel quel.
    if code == 0:
        return "succeeded"
    return "checks-failed" if code == 1 else "exit-code"


def _kill_group(process: DiagnosticProcess) -> None:
    """SIGKILL au groupe créé par start_new_session ; groupe disparu ignoré."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class _BoundedStreams:
    """Lit stdout et stderr jusqu'à EOF ou échéance ; garde ``limit`` octets par
    flux et jette le reste sans cesser de drainer (aucun blocage sur tube plein)."""

    def __init__(self, process: DiagnosticProcess, limit: int) -> None:
        self.limit = limit
        self.kept: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
        self.dropped: dict[str, int] = {"stdout": 0, "stderr": 0}
        self.selector = selectors.DefaultSelector()
        for name in ("stdout", "stderr"):
            stream = getattr(process, name)
            if stream is not None:
                self.selector.register(stream, selectors.EVENT_READ, name)

    def drain(self, deadline: float) -> bool:
        """True si les deux flux sont clos avant l'échéance."""
        while self.selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            for key, _ in self.selector.select(timeout=remaining):
                name: str = key.data
                chunk = os.read(key.fd, _READ_CHUNK)
                if not chunk:
                    self.selector.unregister(key.fileobj)
                    continue
                room = self.limit - len(self.kept[name])
                self.kept[name] += chunk[: max(room, 0)]
                self.dropped[name] += max(len(chunk) - max(room, 0), 0)
        return True

    def close(self) -> None:
        for key in list(self.selector.get_map().values()):
            self.selector.unregister(key.fileobj)
        self.selector.close()


def run_forge_diagnostic(
    checked: CheckedForgeRoot,
    *,
    launcher: Launcher | None = None,
    environ: Mapping[str, str] | None = None,
    timeout: float = FORGE_DIAGNOSTIC_TIMEOUT_SECONDS,
    limit: int = MAX_FORGE_DIAGNOSTIC_OUTPUT_BYTES,
) -> ForgeDiagnosticRun:
    """Lancer ``forge doctor`` avec l'interpréteur du projet, une fois.

    ``checked`` : racine Forge vérifiée par l'appelant (contexte courant).
    ``launcher`` et ``environ`` ne sont injectables que depuis Python (tests).
    """
    root = checked.root
    interpreter = project_interpreter(root)
    if interpreter is None:
        return ForgeDiagnosticRun(
            "launch-failed",
            None,
            "",
            "",
            0.0,
            message=(
                "Interpréteur du projet introuvable ou inutilisable "
                f"({INTERPRETER_LABEL}) : diagnostic non lancé."
            ),
        )
    argv = (str(interpreter), *DIAGNOSTIC_ARGUMENTS)
    env = child_environment(os.environ if environ is None else environ)
    started = time.monotonic()
    try:
        process = (launcher or _spawn)(argv, root, env)
    except OSError as error:
        return ForgeDiagnosticRun(
            "launch-failed",
            None,
            "",
            "",
            time.monotonic() - started,
            message=f"Lancement impossible : {error.strerror or error}.",
        )
    streams = _BoundedStreams(process, limit)
    deadline = started + timeout
    try:
        finished = streams.drain(deadline)
        code: int | None = None
        if finished:
            try:
                code = process.wait(timeout=max(deadline - time.monotonic(), 0))
            except subprocess.TimeoutExpired:
                code = None
    finally:
        # Toujours : aucun processus du groupe ne survit, même après une sortie
        # normale du processus principal.
        _kill_group(process)
        if process.poll() is None:
            process.wait()
        streams.close()
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
    duration = time.monotonic() - started
    stdout = _displayed(bytes(streams.kept["stdout"]))
    stderr = _displayed(bytes(streams.kept["stderr"]))
    if code is None:
        return ForgeDiagnosticRun(
            "timed-out",
            None,
            stdout,
            stderr,
            duration,
            True,
            streams.dropped["stdout"],
            streams.dropped["stderr"],
            message="Diagnostic interrompu : délai dépassé.",
        )
    return ForgeDiagnosticRun(
        _status(code),
        code,
        stdout,
        stderr,
        duration,
        False,
        streams.dropped["stdout"],
        streams.dropped["stderr"],
    )
