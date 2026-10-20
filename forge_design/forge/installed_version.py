"""Version forge-mvc installée dans le .venv du projet, confirmée par commit.

Complète la version déclarée (project_version) quand requirements.txt épingle
Forge par un commit Git : seul l'environnement installé dit alors quelle
version de distribution ce commit porte. Lecture seule et bornée, sans import,
commande ni réseau. Chaque dossier est ouvert relativement au précédent
(dir_fd, O_NOFOLLOW) depuis la racine : aucun lien symbolique n'est suivi.
Seuls METADATA et direct_url.json de l'unique forge_mvc-*.dist-info sont lus.
"""

import json
import os
import re
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG
from typing import Literal, cast

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

VENV = ".venv"
_PYTHON = re.compile(r"python3\.\d{1,3}")
_DIST_INFO = re.compile(r"forge_mvc-[^-/]+\.dist-info")
_INSTALLED_COMMIT = re.compile(r"[0-9a-f]{40}")
_MAX_ENTRIES = 50_000
_MAX_METADATA = 256 * 1024
_MAX_DIRECT_URL = 64 * 1024


@dataclass(frozen=True)
class InstalledForge:
    """match : version installée au commit déclaré ; sinon un détail lisible."""

    status: Literal["match", "mismatch", "absent", "unreadable"]
    version: str | None
    detail: str


class _Refused(ValueError):
    """Métadonnée refusée : le message est le détail rendu."""


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _entries(directory: int, pattern: re.Pattern[str]) -> list[str]:
    """Sous-dossiers réels (pas des liens) dont le nom correspond, bornés."""
    names: list[str] = []
    with os.scandir(directory) as scan:
        for count, entry in enumerate(scan):
            if count >= _MAX_ENTRIES:
                raise _Refused("Dossier de .venv trop volumineux.")
            if pattern.fullmatch(entry.name) and entry.is_dir(follow_symlinks=False):
                names.append(entry.name)
    return sorted(names)


def _read(directory: int, name: str, limit: int) -> str:
    """Fichier ordinaire sans lien, identité contrôlée, au plus limit octets."""
    metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if not S_ISREG(metadata.st_mode):
        raise _Refused("Métadonnée de .venv non ordinaire ou liée.")
    if metadata.st_size > limit:
        raise _Refused("Métadonnée de .venv trop volumineuse.")
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
    )
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
            raise _Refused("Métadonnée de .venv remplacée pendant la lecture.")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise _Refused("Métadonnée de .venv trop volumineuse.")
    return data.decode("utf-8")


def _headers(text: str) -> tuple[str | None, str | None]:
    """Name et Version du bloc d'en-têtes de METADATA (avant la description)."""
    name = version = None
    for line in text.splitlines():
        if not line.strip():
            break
        key, _, value = line.partition(":")
        if key == "Name" and name is None:
            name = value.strip()
        elif key == "Version" and version is None:
            version = value.strip()
    return name, version


def _installed_commit(text: str) -> str | None:
    data: object = json.loads(text)
    if not isinstance(data, dict):
        return None
    vcs = cast(dict[str, object], data).get("vcs_info")
    if not isinstance(vcs, dict):
        return None
    commit = cast(dict[str, object], vcs).get("commit_id")
    if isinstance(commit, str) and _INSTALLED_COMMIT.fullmatch(commit):
        return commit
    return None


def read_installed_forge(root: Path, commit: str) -> InstalledForge:
    """Lire la version forge-mvc de root/.venv et la confronter au commit.

    root doit être canonique (resolve_project_root) ; commit est le commit
    déclaré, hexadécimal minuscule de 7 à 40 caractères. Le commit installé
    (direct_url.json) doit commencer par lui. Rien n'est écrit ni exécuté.
    """
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        return InstalledForge(
            "unreadable", None, "Lecture sécurisée de .venv indisponible."
        )
    with ExitStack() as stack:

        def enter(name: str, parent: int | None) -> int:
            descriptor = os.open(name, _directory_flags(), dir_fd=parent)
            stack.callback(os.close, descriptor)
            return descriptor

        try:
            parts = root.absolute().parts
            directory = enter(parts[0], None)
            for part in parts[1:]:
                directory = enter(part, directory)
            try:
                venv = enter(VENV, directory)
            except FileNotFoundError:
                return InstalledForge("absent", None, "Environnement .venv absent.")
            except OSError as error:
                raise _Refused(".venv lié, non dossier ou inaccessible.") from error
            try:
                lib = enter("lib", venv)
            except FileNotFoundError:
                return InstalledForge(
                    "absent", None, "Environnement .venv sans dossier lib."
                )
            found: list[tuple[int, str]] = []
            for python in _entries(lib, _PYTHON):
                try:
                    site = enter("site-packages", enter(python, lib))
                except FileNotFoundError:
                    continue
                found.extend((site, name) for name in _entries(site, _DIST_INFO))
            if not found:
                return InstalledForge(
                    "absent", None, "forge-mvc n'est pas installé dans .venv."
                )
            if len(found) > 1:
                raise _Refused("Plusieurs installations de forge-mvc dans .venv.")
            site, name = found[0]
            dist_info = enter(name, site)
            package, raw_version = _headers(_read(dist_info, "METADATA", _MAX_METADATA))
            if package is None or canonicalize_name(package) != "forge-mvc":
                raise _Refused("Métadonnées forge-mvc de .venv incohérentes.")
            version = Version(raw_version or "")
            try:
                text = _read(dist_info, "direct_url.json", _MAX_DIRECT_URL)
            except FileNotFoundError:
                return InstalledForge(
                    "mismatch", None, "forge-mvc de .venv installé sans commit Git."
                )
            installed = _installed_commit(text)
        except _Refused as refused:
            return InstalledForge("unreadable", None, str(refused))
        except (OSError, UnicodeError, ValueError, InvalidVersion):
            return InstalledForge(
                "unreadable", None, "Métadonnées forge-mvc de .venv illisibles."
            )
    if installed is None or not installed.startswith(commit):
        return InstalledForge(
            "mismatch",
            None,
            "Le commit de forge-mvc installé dans .venv diffère du commit déclaré.",
        )
    return InstalledForge("match", str(version), "")
