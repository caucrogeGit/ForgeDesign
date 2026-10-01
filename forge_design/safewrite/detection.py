"""Révision disque d'un template et détection de modification externe, sans écriture."""

import hashlib
import os
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG
from typing import Literal

from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import (
    SourceReadError,
    read_source_bytes,
    source_parts,
    template_source,
)
from forge_design.limits import MAX_SOURCE_BYTES

TemplateChangeStatus = Literal["unchanged", "modified", "created", "deleted"]

_VIEWS_PREFIX = "mvc/views/"
_TEMPLATE_SUFFIX = ".html"


@dataclass(frozen=True)
class TemplateRevision:
    """Même forme que DesignRevision : contenu (SHA-256) et identité disque."""

    size: int
    modified_ns: int
    digest: str
    device: int
    inode: int
    changed_ns: int


@dataclass(frozen=True)
class TemplateSnapshot:
    path: str
    exists: bool
    revision: TemplateRevision | None

    def __post_init__(self) -> None:
        # exists porte seul l'absence : aucune révision manquante sur fichier présent.
        if self.exists != (self.revision is not None):
            raise ValueError("Snapshot incohérent : exists et revision divergent.")


@dataclass(frozen=True)
class TemplateChangeResult:
    path: str
    status: TemplateChangeStatus
    expected: TemplateSnapshot
    current: TemplateSnapshot


class TemplateSnapshotError(RuntimeError):
    """Template présent mais impossible à capturer de façon sûre."""


def _template_path(template_path: object) -> str:
    """Seuls mvc/views/**/*.html, selon la politique source existante."""
    if (
        not isinstance(template_path, str)
        or not template_path.startswith(_VIEWS_PREFIX)
        or not template_path.endswith(_TEMPLATE_SUFFIX)
        or not template_path.rsplit("/", 1)[-1].removesuffix(_TEMPLATE_SUFFIX)
        or template_source(template_path.removeprefix(_VIEWS_PREFIX)) is None
    ):
        raise SourceReadError("Chemin de template refusé.")
    return template_path


def _root(root: Path) -> Path:
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    return canonical


def _secure_read_available() -> bool:
    return (
        all(hasattr(os, name) for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY"))
        and all(function in os.supports_dir_fd for function in (os.open, os.stat))
        and os.stat in os.supports_follow_symlinks
    )


def _read_revision(root: int, parts: tuple[str, ...]) -> TemplateRevision | None:
    """None seulement si un segment ou le fichier manque avant ouverture."""
    name = parts[-1]
    with ExitStack() as stack:
        directory = root
        try:
            for part in parts[:-1]:
                directory = stack.enter_context(open_directory(part, directory))
            metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not S_ISREG(metadata.st_mode):
            raise TemplateSnapshotError("Template non régulier ou lié.")
        try:
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        except FileNotFoundError:
            return None
        try:
            opened = os.fstat(descriptor)
            if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
                raise TemplateSnapshotError("Template remplacé pendant l'ouverture.")
            if opened.st_size > MAX_SOURCE_BYTES:
                raise TemplateSnapshotError("Template supérieur à 1 Mio.")
            data = read_source_bytes(descriptor, opened)
            # Le descripteur survit à un renommage : relire aussi le nom.
            current = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if (
                not os.path.samestat(opened, current)
                or current.st_ctime_ns != opened.st_ctime_ns
            ):
                raise TemplateSnapshotError("Template remplacé pendant la lecture.")
        finally:
            os.close(descriptor)
    return TemplateRevision(
        len(data),
        opened.st_mtime_ns,
        hashlib.sha256(data).hexdigest(),
        opened.st_dev,
        opened.st_ino,
        opened.st_ctime_ns,
    )


def snapshot_template(project_root: Path, template_path: str) -> TemplateSnapshot:
    """Lire l'état disque des octets du template ; aucun décodage ni écriture.

    Absence (fichier ou dossier parent) : exists=False. Toute autre impossibilité,
    lien, fichier spécial, permission, taille ou course, lève TemplateSnapshotError.
    """
    path = _template_path(template_path)
    parts = source_parts(path)
    canonical = _root(project_root)
    if not _secure_read_available():
        raise TemplateSnapshotError("Lecture POSIX sécurisée indisponible.")
    try:
        with open_directory(str(canonical)) as root:
            revision = _read_revision(root, parts)
    except TemplateSnapshotError:
        raise
    except (OSError, SourceReadError) as error:
        raise TemplateSnapshotError(
            "Template présent mais impossible à capturer de façon sûre."
        ) from error
    return TemplateSnapshot(path, revision is not None, revision)


def compare_template_snapshots(
    expected: TemplateSnapshot, current: TemplateSnapshot
) -> TemplateChangeStatus:
    """Comparaison pure : révision complète, identité disque comprise."""
    if expected.path != current.path:
        raise ValueError("Les snapshots portent sur des chemins différents.")
    if not expected.exists:
        return "created" if current.exists else "unchanged"
    if not current.exists:
        return "deleted"
    return "unchanged" if expected.revision == current.revision else "modified"


def detect_template_change(
    project_root: Path, expected: TemplateSnapshot
) -> TemplateChangeResult:
    """Relire le template de expected.path et le comparer au snapshot attendu."""
    current = snapshot_template(project_root, expected.path)
    status = compare_template_snapshots(expected, current)
    return TemplateChangeResult(expected.path, status, expected, current)
