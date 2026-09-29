"""Lecture confinée et sauvegarde explicite d'un seul design, sans génération."""

import hashlib
import json
import os
import secrets
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISREG

from pydantic import ValidationError

from forge_design.design.models import DesignFile, DesignNodeType
from forge_design.design.nesting import validate_design_nesting
from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import (
    SourceLocation,
    SourceReadError,
    read_project_source_bytes,
    read_source_bytes,
    source_parts,
    template_source,
)
from forge_design.json_strict import loads_strict_json
from forge_design.limits import MAX_DESIGN_ISSUES, MAX_SOURCE_BYTES


@dataclass(frozen=True)
class DesignRevision:
    size: int
    modified_ns: int
    digest: str
    device: int
    inode: int
    changed_ns: int


@dataclass(frozen=True)
class DesignIssue:
    code: str
    message: str
    path: str | None = None
    location: tuple[str | int, ...] = ()
    parent_type: DesignNodeType | None = None
    child_type: DesignNodeType | None = None


@dataclass(frozen=True)
class DesignReadResult:
    path: str
    size: int | None
    modified_ns: int | None
    revision: DesignRevision | None
    design: DesignFile | None
    issues: tuple[DesignIssue, ...]


@dataclass(frozen=True)
class DesignWriteResult:
    path: str
    created: bool
    size: int
    modified_ns: int
    revision: DesignRevision


class DesignWriteError(RuntimeError):
    """Sauvegarde impossible ; après publication, l'état disque doit être relu."""


class DesignWriteConflictError(DesignWriteError):
    """La cible ne satisfait plus la précondition de révision."""


class InvalidDesignForWriteError(ValueError):
    def __init__(self, issues: tuple[DesignIssue, ...]) -> None:
        self.issues = issues
        super().__init__("Design refusé pour la sauvegarde.")


def design_source(reference: str) -> SourceLocation | None:
    if (
        not reference.endswith(".design.json")
        or not reference.rsplit("/", 1)[-1].removesuffix(".design.json")
        or reference.startswith("mvc/views/")
    ):
        return None
    return template_source(reference)


def _root(root: Path) -> Path:
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    return canonical


def _revision(data: bytes, metadata: os.stat_result) -> DesignRevision:
    return DesignRevision(
        len(data),
        metadata.st_mtime_ns,
        hashlib.sha256(data).hexdigest(),
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_ctime_ns,
    )


def _validation_issues(error: ValidationError, path: str) -> tuple[DesignIssue, ...]:
    errors = error.errors(include_url=False, include_context=False, include_input=False)
    over = len(errors) > MAX_DESIGN_ISSUES
    issues = tuple(
        DesignIssue(
            "design.validation_error",
            "Valeur non conforme au design.",
            path,
            tuple(item["loc"]),
        )
        for item in errors[: MAX_DESIGN_ISSUES - int(over)]
    )
    if over:
        issues += (
            DesignIssue(
                "design.analysis_truncated", "Limite de diagnostics atteinte.", path
            ),
        )
    return issues


def _nesting_issues(design: DesignFile, path: str) -> tuple[DesignIssue, ...]:
    return tuple(
        DesignIssue(
            "design.analysis_truncated"
            if item.code == "design.nesting.analysis_truncated"
            else "design.nesting_error",
            item.message,
            path,
            item.path,
            item.parent_type,
            item.child_type,
        )
        for item in validate_design_nesting(design).issues
    )


def read_design(root: Path, design_path: str) -> DesignReadResult:
    location = design_source(design_path)
    if location is None:
        raise SourceReadError("Chemin de design refusé.")
    canonical = _root(root)
    try:
        data, metadata = read_project_source_bytes(canonical, location.path)
    except SourceReadError:
        return DesignReadResult(
            design_path,
            None,
            None,
            None,
            None,
            (
                DesignIssue(
                    "design.unreadable",
                    "Design inaccessible ou illisible.",
                    design_path,
                ),
            ),
        )
    revision = _revision(data, metadata)
    design = None
    issues: tuple[DesignIssue, ...] = ()
    try:
        parsed = loads_strict_json(data.decode("utf-8-sig"))
    except UnicodeError:
        issues = (DesignIssue("design.unreadable", "Design non UTF-8.", design_path),)
    except (ValueError, RecursionError):
        issues = (
            DesignIssue("design.json_invalid", "Document JSON invalide.", design_path),
        )
    else:
        try:
            design = DesignFile.model_validate(parsed)
        except ValidationError as error:
            issues = _validation_issues(error, design_path)
        else:
            issues = _nesting_issues(design, design_path)
    return DesignReadResult(
        design_path, revision.size, revision.modified_ns, revision, design, issues
    )


def _payload(design: DesignFile, path: str) -> bytes:
    try:
        validated = DesignFile.model_validate(design.model_dump(exclude_unset=True))
    except ValidationError as error:
        raise InvalidDesignForWriteError(_validation_issues(error, path)) from error
    except (ValueError, TypeError, RecursionError) as error:
        raise InvalidDesignForWriteError(
            (DesignIssue("design.validation_error", "Design non sérialisable.", path),)
        ) from error
    issues = _nesting_issues(validated, path)
    if issues:
        raise InvalidDesignForWriteError(issues)
    try:
        data = (
            json.dumps(
                validated.model_dump(exclude_unset=True),
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise InvalidDesignForWriteError(
            (DesignIssue("design.validation_error", "Design non sérialisable.", path),)
        ) from error
    if len(data) > MAX_SOURCE_BYTES:
        raise InvalidDesignForWriteError(
            (DesignIssue("design.validation_error", "Design supérieur à 1 Mio.", path),)
        )
    return data


def _current(directory: int, name: str) -> tuple[DesignRevision, os.stat_result]:
    metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if not S_ISREG(metadata.st_mode):
        raise SourceReadError("Cible non régulière ou liée.")
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
    )
    try:
        opened = os.fstat(descriptor)
        if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
            raise SourceReadError("Cible remplacée.")
        if opened.st_size > MAX_SOURCE_BYTES:
            raise SourceReadError("Cible supérieure à 1 Mio.")
        data = read_source_bytes(descriptor, opened)
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if (
            not os.path.samestat(opened, current)
            or current.st_ctime_ns != opened.st_ctime_ns
        ):
            raise SourceReadError("Cible remplacée pendant la lecture.")
        return _revision(data, opened), opened
    finally:
        os.close(descriptor)


def _check(
    directory: int, name: str, expected: DesignRevision | None
) -> os.stat_result | None:
    if expected is None:
        try:
            os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            return None
        raise DesignWriteConflictError("Le design existe déjà.")
    try:
        revision, metadata = _current(directory, name)
    except (OSError, SourceReadError) as error:
        raise DesignWriteConflictError(
            "Design absent, remplacé ou illisible."
        ) from error
    if revision != expected:
        raise DesignWriteConflictError("Le design a changé depuis sa lecture.")
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


def write_design(
    root: Path,
    design_path: str,
    design: DesignFile,
    *,
    expected_revision: DesignRevision | None,
) -> DesignWriteResult:
    location = design_source(design_path)
    if location is None:
        raise SourceReadError("Chemin de design refusé.")
    data = _payload(design, design_path)
    canonical = _root(root)
    if not _secure_write_available():
        raise DesignWriteError("Écriture POSIX sécurisée indisponible.")
    parts = source_parts(location.path)
    try:
        with ExitStack() as stack:
            directory = stack.enter_context(open_directory(str(canonical)))
            for part in parts[:-1]:
                directory = stack.enter_context(open_directory(part, directory))
            name = parts[-1]
            previous = _check(directory, name, expected_revision)
            temporary = ".forge-design-write-" + secrets.token_hex(16)
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
                            raise OSError("Écriture incomplète.")
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
                    raise DesignWriteError("Temporaire remplacé.")
                _check(directory, name, expected_revision)
                if expected_revision is None:
                    # Publication exclusive : contrairement à replace, link refuse
                    # aussi une cible créée entre le dernier contrôle et cet appel.
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
                revision, _ = _current(directory, name)
                if revision.digest != hashlib.sha256(data).hexdigest():
                    raise DesignWriteConflictError("Design modifié après publication.")
                return DesignWriteResult(
                    design_path,
                    expected_revision is None,
                    revision.size,
                    revision.modified_ns,
                    revision,
                )
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
    except DesignWriteError:
        raise
    except FileExistsError as error:
        raise DesignWriteConflictError("Cible ou temporaire déjà présent.") from error
    except (OSError, SourceReadError) as error:
        raise DesignWriteError(
            "Sauvegarde impossible ; relire la cible avant de réessayer."
        ) from error
