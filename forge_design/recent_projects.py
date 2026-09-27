"""Historique utilisateur de racines canoniques, indépendant du projet courant."""

import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG
from typing import cast
from uuid import uuid4

MAX_RECENT_PROJECTS = 10
MAX_RECENT_FILE_BYTES = 64 * 1024
MAX_RECENT_PATH_LENGTH = 4096


class RecentProjectsError(ValueError):
    """Historique inaccessible ou incompatible ; ne pas l'écraser."""


@dataclass(frozen=True)
class RecentProject:
    path: str


def resolve_user_config_dir() -> Path:
    """Base XDG absolue ; les valeurs relatives ne dépendent pas du cwd."""
    value = os.environ.get("XDG_CONFIG_HOME", "")
    base = (
        Path(value) if value and Path(value).is_absolute() else Path.home() / ".config"
    )
    return base / "forge-design"


def recent_projects_file() -> Path:
    return resolve_user_config_dir() / "recent-projects.json"


def _valid_path(value: object) -> bool:
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError:
            return False
    return (
        isinstance(value, str)
        and 0 < len(value) <= MAX_RECENT_PATH_LENGTH
        and "\x00" not in value
        and Path(value).is_absolute()
        and os.path.normpath(value) == value
    )


class RecentProjects:
    """Pas d'inspection des chemins enregistrés, pas de singleton ni projet actif.

    Les ajouts reçoivent la racine canonique d'une inspection valide. Chaque
    opération recharge le fichier pour vérifier son format avant modification.
    Les écritures sont atomiques, sans verrou interprocessus (dernier écrivain).
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else recent_projects_file()
        self.warning: str | None = None
        if not _valid_path(str(self.path)):
            raise RecentProjectsError("Emplacement des projets récents invalide.")
        self.list()

    @contextmanager
    def _directory(self, *, create: bool = False) -> Generator[int, None, None]:
        if not all(
            hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
        ):
            raise RecentProjectsError("Stockage sécurisé des récents indisponible.")
        descriptors: list[int] = []
        try:
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            descriptors.append(os.open(self.path.anchor, flags))
            for part in self.path.parent.parts[1:]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=descriptors[-1])
                    except FileExistsError:
                        pass
                descriptors.append(os.open(part, flags, dir_fd=descriptors[-1]))
            yield descriptors[-1]
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def _read(self) -> tuple[RecentProject, ...]:
        try:
            with self._directory() as directory:
                metadata = os.stat(
                    self.path.name, dir_fd=directory, follow_symlinks=False
                )
                if not S_ISREG(metadata.st_mode):
                    raise RecentProjectsError(
                        "Le fichier des récents doit être ordinaire, sans lien."
                    )
                descriptor = os.open(
                    self.path.name,
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=directory,
                )
                with os.fdopen(descriptor, "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if not S_ISREG(opened.st_mode) or not os.path.samestat(
                        metadata, opened
                    ):
                        raise RecentProjectsError(
                            "Fichier des récents remplacé pendant la lecture."
                        )
                    if opened.st_size > MAX_RECENT_FILE_BYTES:
                        raise RecentProjectsError(
                            "Fichier des récents supérieur à 64 Kio."
                        )
                    content = stream.read(MAX_RECENT_FILE_BYTES + 1)
            if len(content) > MAX_RECENT_FILE_BYTES:
                raise RecentProjectsError("Fichier des récents supérieur à 64 Kio.")
            data: object = json.loads(content.decode("utf-8"))
            if not isinstance(data, dict):
                raise RecentProjectsError("Format des projets récents invalide.")
            data = cast(dict[str, object], data)
            if type(data.get("version")) is not int:
                raise RecentProjectsError("Format des projets récents invalide.")
            if data["version"] != 1:
                raise RecentProjectsError(
                    "Version des projets récents non prise en charge."
                )
            projects: object = data.get("projects")
            if set(data) != {"version", "projects"} or not isinstance(projects, list):
                raise RecentProjectsError("Liste des projets récents invalide.")
            projects = cast(list[object], projects)
            if len(projects) > MAX_RECENT_PROJECTS or not all(
                _valid_path(item) for item in projects
            ):
                raise RecentProjectsError("Liste des projets récents invalide.")
            paths = tuple(RecentProject(str(item)) for item in projects)
            if len(set(paths)) != len(paths):
                raise RecentProjectsError("Liste des projets récents dupliquée.")
            return paths
        except FileNotFoundError:
            return ()
        except RecentProjectsError:
            raise
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            raise RecentProjectsError(
                "Impossible de lire les projets récents."
            ) from error

    def list(self) -> tuple[RecentProject, ...]:
        try:
            result = self._read()
        except RecentProjectsError as error:
            self.warning = str(error)
            return ()
        self.warning = None
        return result

    def _write(self, projects: tuple[RecentProject, ...]) -> None:
        content = (
            json.dumps(
                {"version": 1, "projects": [p.path for p in projects]},
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            + b"\n"
        )
        if len(content) > MAX_RECENT_FILE_BYTES:
            raise RecentProjectsError("Fichier des récents supérieur à 64 Kio.")
        temporary = ".recent-" + uuid4().hex + ".tmp"
        with self._directory(create=True) as directory:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(
                    temporary,
                    self.path.name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                )
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass

    def _change(self, root: Path, *, remove: bool) -> None:
        try:
            if not _valid_path(str(root)):
                raise RecentProjectsError("Racine récente invalide.")
            previous = self._read()  # Ne jamais réparer/écraser un format inconnu.
            if any(
                self.path.is_relative_to(p)
                for p in (root, *(Path(p.path) for p in previous))
            ):
                raise RecentProjectsError(
                    "Le stockage des récents doit rester hors des projets."
                )
            remaining = tuple(p for p in previous if p.path != str(root))
            updated = (
                remaining
                if remove
                else (RecentProject(str(root)), *remaining)[:MAX_RECENT_PROJECTS]
            )
            if remove and updated == previous:
                self.warning = None
                return
            self._write(updated)
            self.warning = None
        except (OSError, RecentProjectsError) as error:
            self.warning = "Enregistrement des projets récents impossible : " + str(
                error
            )
            raise RecentProjectsError(self.warning) from error

    def add(self, root: Path) -> None:
        self._change(root, remove=False)

    def remove(self, root: Path) -> None:
        self._change(root, remove=True)
