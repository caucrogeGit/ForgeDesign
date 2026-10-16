"""Coordination Linux locale des écrivains de designs (FD-EDITOR-008).

Les fichiers restent en place : seule la fermeture des descripteurs libère
l'occupation. Les écrivains externes doivent respecter le même protocole.
"""

import errno
import hashlib
import os
import sys
import threading
import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from forge_design.forge.filesystem import open_directory
from forge_design.forge.source import source_parts

TIMEOUT_SECONDS = 5.0
_POLL_SECONDS = 0.01
_QUALIFIED = frozenset({"ext4", "tmpfs"})


class LockUnavailable(RuntimeError):
    """Aucune action ne doit commencer sans coordination vérifiable."""


# Protection de la liste de descripteurs pendant fork, pas des designs.
# Le verrou des designs est toujours un flock noyau.
_FDS: set[int] = set()
_FDS_GUARD = threading.Lock()


def _fork_child() -> None:
    try:
        for fd in _FDS:
            try:
                os.close(fd)  # ne jamais LOCK_UN : le parent conserve son occupation
            except OSError:
                pass  # fermer aussi les autres copies, même si un fd est déjà fermé
        _FDS.clear()
        _HELD.set(None)
    finally:
        _FDS_GUARD.release()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_FDS_GUARD.acquire,
        after_in_parent=_FDS_GUARD.release,
        after_in_child=_fork_child,
    )


def filesystem_type(fd: int) -> str:
    """Le montage du descripteur réel, y compris les sous-montages/bind mounts."""
    info = Path(f"/proc/self/fdinfo/{fd}").read_text()
    ids = [line.split()[1] for line in info.splitlines() if line.startswith("mnt_id:")]
    if len(ids) != 1:
        raise LockUnavailable("Montage du design invérifiable.")
    matches: list[str] = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, separator, after = line.partition(" - ")
        if separator and before.split()[0] == ids[0]:
            matches.append(after.split()[0])
    if len(matches) != 1 or matches[0] not in _QUALIFIED:
        raise LockUnavailable("Stockage du design non qualifié (ext4 ou tmpfs requis).")
    return matches[0]


def _safe_metadata(fd: int, *, directory: bool, private: bool) -> None:
    metadata = os.fstat(fd)
    kind_ok = S_ISDIR(metadata.st_mode) if directory else S_ISREG(metadata.st_mode)
    forbidden = 0o077 if private else 0o022
    if (
        not kind_ok
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & forbidden
        or (not directory and metadata.st_nlink != 1)
    ):
        raise LockUnavailable("Permissions ou identité du verrou refusées.")
    filesystem_type(fd)


def _metadata_directory(stack: ExitStack, parent: int, name: str, private: bool) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent)
    except FileExistsError:
        pass
    fd = stack.enter_context(open_directory(name, parent))
    _safe_metadata(fd, directory=True, private=private)
    return fd


def _target_mounts(root_fd: int, path: str) -> None:
    """Vérifier aussi les sous-montages de la cible à chaque acquisition/reprise."""
    parts = source_parts("mvc/views/" + path)
    filesystem_type(root_fd)
    with ExitStack() as stack:
        target_dir = root_fd
        for part in parts[:-1]:
            target_dir = stack.enter_context(open_directory(part, target_dir))
        filesystem_type(target_dir)
        # Un fichier monté séparément peut différer du répertoire parent.
        try:
            target = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=target_dir,
            )
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.ELOOP):
                raise
            # Absence ou symlink : refus historique sous verrou par le reader
            # ou le writer ; jamais suivre la cible liée.
        else:
            try:
                if not S_ISREG(os.fstat(target).st_mode):
                    raise LockUnavailable(
                        "La cible du design n’est pas un fichier régulier."
                    )
                filesystem_type(target)
            finally:
                os.close(target)


@dataclass(frozen=True)
class _Lease:
    root: Path
    path: str
    pid: int
    thread: int
    descriptor: int
    directory: int
    name: str

    def verify(self) -> None:
        if self.pid != os.getpid() or self.thread != threading.get_ident():
            raise LockUnavailable("Verrou non transmissible à un autre exécutant.")
        opened = os.fstat(self.descriptor)
        named = os.stat(self.name, dir_fd=self.directory, follow_symlinks=False)
        if not os.path.samestat(opened, named):
            raise LockUnavailable("Fichier de verrou remplacé.")
        _safe_metadata(self.descriptor, directory=False, private=True)
        # Vérifier que le chemin du verrou mène toujours au répertoire ouvert.
        with open_directory(str(self.root)) as root_fd:
            _target_mounts(root_fd, self.path)
            with open_directory(".forge-design", root_fd) as meta:
                with open_directory("locks", meta) as locks:
                    _safe_metadata(meta, directory=True, private=False)
                    _safe_metadata(locks, directory=True, private=True)
                    if not os.path.samestat(os.fstat(locks), os.fstat(self.directory)):
                        raise LockUnavailable("Répertoire de verrou remplacé.")


_HELD: ContextVar[_Lease | None] = ContextVar("design_mutation_lease", default=None)


def _acquire(fd: int) -> None:
    # Import tardif : le refus d'un OS non couvert reste explicite.
    try:
        import fcntl
    except ImportError as error:
        raise LockUnavailable("Verrouillage Linux indisponible.") from error

    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        if time.monotonic() >= deadline:
            raise LockUnavailable("Design occupé : délai de cinq secondes dépassé.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if time.monotonic() >= deadline:
                raise LockUnavailable("Design occupé : délai de cinq secondes dépassé.")
            return
        except OSError as error:
            if error.errno not in (errno.EAGAIN, errno.EACCES, errno.EINTR):
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LockUnavailable(
                    "Design occupé : délai de verrouillage de cinq secondes dépassé."
                ) from error
            time.sleep(min(_POLL_SECONDS, remaining))


@contextmanager
def design_lock(root: Path, path: str) -> Generator[None, None, None]:
    """Coordination par cible ; réutilisation explicite dans la requête propriétaire.

    Le contexte interne permet à write_design de participer au verrou déjà pris
    par le Web, sans deuxième flock sur un descripteur concurrent du même thread.
    Chaque occupation indépendante ouvre son propre descripteur.
    """
    if sys.platform != "linux":
        raise LockUnavailable(
            "Verrouillage de designs disponible uniquement sur Linux."
        )
    held = _HELD.get()
    if held is not None:
        if held.root != root or held.path != path:
            raise LockUnavailable(
                "Une mutation imbriquée ne peut viser un autre design."
            )
        try:
            held.verify()
        except OSError as error:
            raise LockUnavailable("Verrou courant invérifiable.") from error
        yield
        return
    entered = False
    try:
        with ExitStack() as stack:
            root_fd = stack.enter_context(open_directory(str(root)))
            filesystem_type(root_fd)
            _target_mounts(root_fd, path)
            meta = _metadata_directory(stack, root_fd, ".forge-design", False)
            directory = _metadata_directory(stack, meta, "locks", True)
            name = (
                "design-" + hashlib.sha256(path.encode("utf-8")).hexdigest() + ".lock"
            )
            with _FDS_GUARD:
                fd = os.open(
                    name,
                    os.O_RDWR
                    | os.O_CREAT
                    | os.O_NOFOLLOW
                    | os.O_NONBLOCK
                    | os.O_CLOEXEC,
                    0o600,
                    dir_fd=directory,
                )
                _FDS.add(fd)
            owner = os.getpid()
            try:
                _safe_metadata(fd, directory=False, private=True)
                _acquire(fd)
                lease = _Lease(
                    root, path, owner, threading.get_ident(), fd, directory, name
                )
                lease.verify()
                token = _HELD.set(lease)
                try:
                    entered = True
                    yield
                finally:
                    _HELD.reset(token)
            finally:
                if os.getpid() == owner:
                    with _FDS_GUARD:
                        _FDS.discard(fd)
                        os.close(fd)
    except (OSError, ValueError, IndexError) as error:
        if entered:
            raise
        raise LockUnavailable(
            "Verrouillage du design inaccessible ou invérifiable."
        ) from error
