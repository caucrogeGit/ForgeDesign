"""Hôte des ressources spécialisées : lecture confinée et écriture contrôlée.

Le codec ne traite que des octets et une ressource en mémoire : il ne lit ni
n'écrit le système de fichiers et ignore la racine du projet. L'hôte possède le
chemin (espace de sources, suffixe, politique lexicale, aucun lien), la borne de
taille, la version, la révision attendue, la publication atomique et le journal.

Lecture → résultat avec issues. Écriture impossible ou conflit → exceptions
contrôlées, rattachées aux catégories du contrat. Une exception inattendue d'un
codec reste une erreur de programmation et n'est pas convertie.
"""

import errno
import hashlib
import os
import secrets
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from stat import S_ISDIR, S_ISREG
from typing import Generic, Protocol, TypeVar

from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import unsafe_relative_path
from forge_design.generate.history import (
    GenerationHistoryEvent,
    append_generation_history,
)
from forge_design.limits import MAX_SOURCE_PATH_LENGTH
from forge_design.specialized.models import (
    ErrorCategory,
    SpecializedIssue,
    SpecializedResourceType,
    SpecializedToolDefinition,
    SpecializedValidationResult,
)

Resource = TypeVar("Resource")
_CHUNK = 64 * 1024
_TEMPORARY_PREFIX = ".forge-design-write-"


@dataclass(frozen=True)
class SpecializedResourceRevision:
    """Révision observable : contenu, métadonnées et identité du fichier."""

    size: int
    modified_ns: int
    digest: str
    device: int
    inode: int
    changed_ns: int


@dataclass(frozen=True)
class SpecializedResourceRef:
    """Identité d'une ressource : outil, type, chemin relatif, version observée."""

    tool_id: str
    resource_type_id: str
    path: str
    format_version: str


class SpecializedFormatError(ValueError):
    """Erreur de format attendue d'un codec : issues structurées, pas de ressource."""

    def __init__(self, issues: tuple[SpecializedIssue, ...]) -> None:
        if not issues:
            raise ValueError("Une erreur de format porte au moins une issue.")
        self.issues = issues
        super().__init__("Ressource non décodable.")


class SpecializedResourceCodec(Protocol, Generic[Resource]):
    """Format et domaine d'un type de ressource, sans filesystem ni racine."""

    def detect_version(self, data: bytes) -> str | None:
        """Version de format, sans décodage métier complet ; None si illisible."""
        ...

    def decode(self, data: bytes) -> Resource:
        """Ressource en mémoire ; SpecializedFormatError si le format est invalide."""
        ...

    def encode(self, resource: Resource) -> bytes:
        """Octets de la version écrite par le type."""
        ...

    def validate(self, resource: Resource) -> SpecializedValidationResult:
        """Issues par niveau de validation déclaré par le type."""
        ...


@dataclass(frozen=True)
class SpecializedReadResult(Generic[Resource]):
    """Lecture : ressource et révision si lisibles ; error = catégorie bloquante."""

    path: str
    ref: SpecializedResourceRef | None
    revision: SpecializedResourceRevision | None
    resource: Resource | None
    issues: tuple[SpecializedIssue, ...]
    truncated: bool
    error: ErrorCategory | None


@dataclass(frozen=True)
class SpecializedWriteResult:
    ref: SpecializedResourceRef
    created: bool
    revision: SpecializedResourceRevision
    history: GenerationHistoryEvent


class SpecializedResourceError(RuntimeError):
    """Échec de l'hôte ; après publication éventuelle, relire la ressource.

    category vaut None pour une défaillance d'infrastructure (entrée/sortie),
    qui n'est pas une catégorie de ressource du contrat.
    """

    category: ErrorCategory | None = None


class SpecializedResourceRefusedError(SpecializedResourceError):
    category = "resource-refused"


class SpecializedCapabilityError(SpecializedResourceError):
    category = "capability-unavailable"


class UnsupportedSpecializedVersionError(SpecializedResourceError):
    category = "unsupported-version"


class SpecializedResourceConflictError(SpecializedResourceError):
    category = "conflict"


class InvalidSpecializedResourceError(SpecializedResourceError):
    category = "invalid-resource"

    def __init__(self, issues: tuple[SpecializedIssue, ...], truncated: bool) -> None:
        self.issues = issues
        self.truncated = truncated
        super().__init__("Ressource refusée par sa validation bloquante.")


class SpecializedResourceHistoryError(SpecializedResourceError):
    """Ressource publiée et vérifiée, journal non écrit (ni retry ni rollback)."""

    def __init__(
        self,
        ref: SpecializedResourceRef,
        created: bool,
        revision: SpecializedResourceRevision,
    ) -> None:
        self.ref = ref
        self.created = created
        self.revision = revision
        super().__init__("Ressource écrite et vérifiée, journal non écrit.")


class _Refused(Exception):
    """Refus interne de chemin ou de fichier (resource-refused)."""


def _type_of(
    tool: SpecializedToolDefinition, resource_type: SpecializedResourceType
) -> SpecializedResourceType:
    """Le type doit appartenir à l'outil (qualification outil + type)."""
    if resource_type not in tool.resource_types:
        raise ValueError("Le type de ressource n'est pas celui de l'outil.")
    return resource_type


def resource_parts(
    resource_type: SpecializedResourceType, path: str
) -> tuple[str, ...]:
    """Segments du chemin relatif, sous l'espace de sources et avec le suffixe."""
    if (
        len(path) > MAX_SOURCE_PATH_LENGTH
        or unsafe_relative_path(path)
        or not path.startswith(resource_type.source_prefix + "/")
        or not path.endswith(resource_type.suffix)
        or not path.rsplit("/", 1)[-1].removesuffix(resource_type.suffix)
    ):
        raise _Refused("Chemin hors de l'espace de sources ou mal formé.")
    return tuple(path.split("/"))


def _root(root: Path) -> Path:
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    return canonical


def _revision(data: bytes, metadata: os.stat_result) -> SpecializedResourceRevision:
    return SpecializedResourceRevision(
        len(data),
        metadata.st_mtime_ns,
        hashlib.sha256(data).hexdigest(),
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_ctime_ns,
    )


def _open_parent(stack: ExitStack, canonical: Path, parts: tuple[str, ...]) -> int:
    """Dossier parent, chaque segment ouvert sans suivre de lien."""
    directory = stack.enter_context(open_directory(str(canonical)))
    for part in parts[:-1]:
        directory = stack.enter_context(open_directory(part, directory))
        if not S_ISDIR(os.fstat(directory).st_mode):
            raise _Refused("Parent non répertoire.")
    return directory


def _read_bounded(
    directory: int, name: str, max_size: int
) -> tuple[bytes, os.stat_result]:
    """Fichier ordinaire sans lien, taille bornée avant lecture, stable pendant."""
    metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if not S_ISREG(metadata.st_mode):
        raise _Refused("La ressource doit être un fichier ordinaire sans lien.")
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
    )
    try:
        opened = os.fstat(descriptor)
        if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
            raise _Refused("Ressource remplacée pendant l'ouverture.")
        if opened.st_size > max_size:
            raise _Refused("Ressource supérieure à la taille maximale du type.")
        chunks: list[bytes] = []
        size = 0
        while size <= max_size and (chunk := os.read(descriptor, _CHUNK)):
            chunks.append(chunk)
            size += len(chunk)
        current = os.fstat(descriptor)
        after = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if (
            size != opened.st_size
            or current.st_size != opened.st_size
            or current.st_mtime_ns != opened.st_mtime_ns
            or current.st_ctime_ns != opened.st_ctime_ns
            or not os.path.samestat(opened, after)
        ):
            raise _Refused("Ressource modifiée pendant la lecture.")
        return b"".join(chunks), opened
    finally:
        os.close(descriptor)


def _platform_issue(category: ErrorCategory, message: str) -> SpecializedIssue:
    return SpecializedIssue(category, "error", message)


def _check_levels(
    resource_type: SpecializedResourceType, result: SpecializedValidationResult
) -> None:
    """Un niveau non déclaré par le type est un défaut du codec, pas un diagnostic."""
    for issue in result.issues:
        if issue.level not in resource_type.validation_levels:
            raise ValueError(f"Niveau de validation non déclaré : {issue.level}")


def read_specialized_resource(
    root: Path,
    tool: SpecializedToolDefinition,
    resource_type: SpecializedResourceType,
    path: str,
    codec: SpecializedResourceCodec[Resource],
) -> SpecializedReadResult[Resource]:
    """Lire, détecter la version avant tout décodage, décoder puis valider.

    Racine invalide ou projet non reconnu : exceptions du Bridge, comme read_design.
    """
    _type_of(tool, resource_type)

    def failed(
        category: ErrorCategory,
        message: str,
        revision: SpecializedResourceRevision | None = None,
        issues: tuple[SpecializedIssue, ...] = (),
        truncated: bool = False,
    ) -> SpecializedReadResult[Resource]:
        return SpecializedReadResult(
            path,
            None,
            revision,
            None,
            issues or (_platform_issue(category, message),),
            truncated,
            category,
        )

    if not resource_type.has_capability("open"):
        return failed("capability-unavailable", "Ce type ne déclare pas open.")
    try:
        parts = resource_parts(resource_type, path)
    except _Refused as error:
        return failed("resource-refused", str(error))
    canonical = _root(root)
    try:
        with ExitStack() as stack:
            directory = _open_parent(stack, canonical, parts)
            data, metadata = _read_bounded(directory, parts[-1], resource_type.max_size)
    except FileNotFoundError:
        return failed("resource-not-found", "Ressource introuvable.")
    except (_Refused, OSError) as error:
        message = (
            str(error)
            if isinstance(error, _Refused)
            else "Ressource inaccessible ou liée."
        )
        return failed("resource-refused", message)
    revision = _revision(data, metadata)
    version = codec.detect_version(data)
    if version is None:
        return failed("invalid-resource", "Version de format illisible.", revision)
    if version not in resource_type.read_versions:
        return failed(
            "unsupported-version",
            f"Version de format non prise en charge : {version}",
            revision,
        )
    ref = SpecializedResourceRef(tool.id, resource_type.id, path, version)
    try:
        resource = codec.decode(data)
    except SpecializedFormatError as error:
        bounded = SpecializedValidationResult.bounded(error.issues)
        _check_levels(resource_type, bounded)
        return SpecializedReadResult(
            path,
            ref,
            revision,
            None,
            bounded.issues,
            bounded.truncated,
            "invalid-resource",
        )
    result = codec.validate(resource)
    _check_levels(resource_type, result)
    blocking = result.blocking(resource_type) or result.truncated
    return SpecializedReadResult(
        path,
        ref,
        revision,
        resource,
        result.issues,
        result.truncated,
        "invalid-resource" if blocking else None,
    )


def _current(directory: int, name: str, max_size: int) -> SpecializedResourceRevision:
    data, opened = _read_bounded(directory, name, max_size)
    return _revision(data, opened)


def _check_target(
    directory: int,
    name: str,
    expected: SpecializedResourceRevision | None,
    max_size: int,
) -> os.stat_result | None:
    """Création : cible absente. Mise à jour : révision identique, sinon conflit."""
    if expected is None:
        try:
            os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None
        raise SpecializedResourceConflictError("La ressource existe déjà.")
    try:
        revision = _current(directory, name, max_size)
        metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except (_Refused, OSError) as error:
        raise SpecializedResourceConflictError(
            "Ressource absente, remplacée, liée ou illisible."
        ) from error
    if revision != expected:
        raise SpecializedResourceConflictError(
            "La ressource a changé depuis sa lecture."
        )
    return metadata


def _secure_write_available() -> bool:
    return (
        all(
            hasattr(os, name)
            for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY", "fchmod", "fsync")
        )
        and all(
            function in os.supports_dir_fd
            for function in (os.open, os.stat, os.unlink, os.link, os.rename)
        )
        and os.stat in os.supports_follow_symlinks
        and os.link in os.supports_follow_symlinks
    )


def write_specialized_resource(
    root: Path,
    tool: SpecializedToolDefinition,
    resource_type: SpecializedResourceType,
    path: str,
    resource: Resource,
    codec: SpecializedResourceCodec[Resource],
    *,
    expected_revision: SpecializedResourceRevision | None,
    timestamp: datetime | None = None,
) -> SpecializedWriteResult:
    """Encoder, borner, valider, vérifier la version, puis publier atomiquement.

    expected_revision None : création exclusive (la cible doit être absente).
    Sinon : la ressource doit avoir exactement cette révision (pas d'écrasement).
    L'espace de sources doit exister : aucun dossier n'est créé. Une écriture
    réussie est journalisée dans history.jsonl (write_specialized_resource).
    """
    _type_of(tool, resource_type)
    if not resource_type.editable or not resource_type.has_capability("save"):
        raise SpecializedCapabilityError("Ce type ne déclare pas save.")
    if expected_revision is None and not resource_type.has_capability("create"):
        raise SpecializedCapabilityError("Ce type ne déclare pas create.")
    try:
        parts = resource_parts(resource_type, path)
    except _Refused as error:
        raise SpecializedResourceRefusedError(str(error)) from None
    data = codec.encode(resource)
    if len(data) > resource_type.max_size:
        raise SpecializedResourceRefusedError("Ressource encodée trop volumineuse.")
    validation = codec.validate(resource)
    _check_levels(resource_type, validation)
    if validation.truncated or validation.blocking(resource_type):
        raise InvalidSpecializedResourceError(validation.issues, validation.truncated)
    if codec.detect_version(data) != resource_type.write_version:
        raise UnsupportedSpecializedVersionError(
            "Le codec n'a pas produit la version écrite du type."
        )
    canonical = _root(root)
    if not _secure_write_available():
        raise SpecializedResourceError("Écriture POSIX sécurisée indisponible.")
    ref = SpecializedResourceRef(
        tool.id, resource_type.id, path, resource_type.write_version
    )
    digest = hashlib.sha256(data).hexdigest()
    try:
        with ExitStack() as stack:
            directory = _open_parent(stack, canonical, parts)
            name = parts[-1]
            previous = _check_target(
                directory, name, expected_revision, resource_type.max_size
            )
            temporary = _TEMPORARY_PREFIX + secrets.token_hex(16)
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o666,
                dir_fd=directory,
            )
            try:
                try:
                    remaining = memoryview(data)
                    while remaining:
                        count = os.write(descriptor, remaining)
                        if count <= 0:
                            raise OSError(errno.EIO, "Écriture incomplète.")
                        remaining = remaining[count:]
                    if previous is not None:
                        os.fchmod(descriptor, previous.st_mode & 0o777)
                    os.fsync(descriptor)
                    prepared = os.fstat(descriptor)
                finally:
                    os.close(descriptor)
                current_temp = os.stat(
                    temporary, dir_fd=directory, follow_symlinks=False
                )
                if not S_ISREG(current_temp.st_mode) or not os.path.samestat(
                    prepared, current_temp
                ):
                    raise SpecializedResourceError("Temporaire remplacé.")
                _check_target(
                    directory, name, expected_revision, resource_type.max_size
                )
                if expected_revision is None:
                    # Publication exclusive : link refuse une cible apparue entre-temps.
                    os.link(
                        temporary,
                        name,
                        src_dir_fd=directory,
                        dst_dir_fd=directory,
                        follow_symlinks=False,
                    )
                    os.unlink(temporary, dir_fd=directory)
                else:
                    os.replace(
                        temporary, name, src_dir_fd=directory, dst_dir_fd=directory
                    )
                os.fsync(directory)
                revision = _current(directory, name, resource_type.max_size)
                if revision.digest != digest:
                    raise SpecializedResourceConflictError(
                        "Ressource modifiée après publication."
                    )
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
    except SpecializedResourceError:
        raise
    except FileExistsError as error:
        raise SpecializedResourceConflictError(
            "Cible ou temporaire déjà présent."
        ) from error
    except FileNotFoundError as error:
        raise SpecializedResourceRefusedError(
            "Espace de sources absent : il n'est pas créé automatiquement."
        ) from error
    except (_Refused, OSError) as error:
        raise SpecializedResourceError(
            "Écriture impossible ; relire la ressource avant de réessayer."
        ) from error
    created = expected_revision is None
    try:
        event = append_generation_history(
            canonical,
            action="write_specialized_resource",
            file=path,
            timestamp=timestamp,
        )
    except (OSError, ValueError) as error:
        raise SpecializedResourceHistoryError(ref, created, revision) from error
    return SpecializedWriteResult(ref, created, revision, event)
