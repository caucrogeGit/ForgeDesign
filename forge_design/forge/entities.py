"""Lecture des seuls contrats JSON canoniques directs, sans exécution Forge."""

import json
import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from os import PathLike
from stat import S_ISDIR, S_ISREG
from typing import cast

from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceLocation
from forge_design.limits import MAX_SOURCE_BYTES


@dataclass(frozen=True)
class EntityFieldInfo:
    name: str
    type: str
    required: bool
    nullable: bool
    unique: bool
    max_length: int | None = None
    precision: int | None = None
    scale: int | None = None
    default_json: str | None = None
    references: str | None = None


@dataclass(frozen=True)
class EntityInfo:
    name: str
    table: str
    fields: tuple[EntityFieldInfo, ...]
    timestamps: bool
    soft_delete: bool
    source: SourceLocation


@dataclass(frozen=True)
class EntityIssue:
    code: str
    message: str
    source: SourceLocation | None = None


@dataclass(frozen=True)
class EntitiesResult:
    entities: tuple[EntityInfo, ...] = ()
    errors: tuple[EntityIssue, ...] = ()
    warnings: tuple[EntityIssue, ...] = ()


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Objet attendu.")
    return cast(dict[str, object], value)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Chaîne non vide attendue.")
    value.encode("utf-8")
    return value


def _boolean(data: dict[str, object], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ValueError("Booléen attendu.")
    return value


def _integer(data: dict[str, object], key: str) -> int | None:
    if key not in data:
        return None
    value = data[key]
    if type(value) is not int:
        raise ValueError("Entier attendu.")
    return value


def _field(value: object) -> EntityFieldInfo:
    data = _object(value)
    required = _boolean(data, "required", False)
    nullable = _boolean(data, "nullable", True)
    return EntityFieldInfo(
        _text(data.get("name")),
        _text(data.get("type")),
        required,
        nullable and not required,
        _boolean(data, "unique", False),
        _integer(data, "max_length"),
        _integer(data, "precision"),
        _integer(data, "scale"),
        json.dumps(data["default"], ensure_ascii=True, allow_nan=False)
        if "default" in data
        else None,
        _text(data["references"]) if "references" in data else None,
    )


def _entity(data: dict[str, object], source: SourceLocation) -> EntityInfo:
    fields = data.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("Liste de champs non vide attendue.")
    options = _object(data.get("options", {}))
    return EntityInfo(
        _text(data.get("name")),
        _text(data.get("table")),
        tuple(_field(item) for item in cast(list[object], fields)),
        _boolean(options, "timestamps", False),
        _boolean(options, "soft_delete", False),
        source,
    )


@contextmanager
def _directory(name: str, parent: int | None = None) -> Generator[int, None, None]:
    descriptor = os.open(
        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
    )
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def _read(parent: int, name: str) -> str:
    metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not S_ISREG(metadata.st_mode):
        raise OSError("Fichier ordinaire sans lien attendu.")
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
    )
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
            raise OSError("Source remplacée.")
        if opened.st_size > MAX_SOURCE_BYTES:
            raise OSError("Source trop grande.")
        data = stream.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise OSError("Source trop grande.")
    return data.decode("utf-8-sig")


def _constant(value: str) -> object:
    raise ValueError("Constante JSON non standard.")


def _load(parent: int, folder: str, errors: list[EntityIssue]) -> EntityInfo | None:
    source = SourceLocation(f"mvc/entities/{folder}/{folder}.json")
    try:
        with _directory(folder, parent) as directory:
            content = _read(directory, folder + ".json")
    except FileNotFoundError:
        errors.append(
            EntityIssue("entity.source_missing", "JSON attendu absent.", source)
        )
        return None
    except (OSError, UnicodeError):
        errors.append(
            EntityIssue("entity.unreadable", "Source illisible ou refusée.", source)
        )
        return None
    try:
        raw: object = json.loads(content, parse_constant=_constant)
    except (ValueError, RecursionError):
        errors.append(EntityIssue("entity.json_invalid", "JSON invalide.", source))
        return None
    try:
        data = _object(raw)
        if "format_version" in data or data.get("schema_version") != "1.0":
            errors.append(
                EntityIssue(
                    "entity.schema_version_unsupported",
                    'Contrat non pris en charge : schema_version "1.0" attendu.',
                    source,
                )
            )
            return None
        return _entity(data, source)
    except (ValueError, RecursionError):
        errors.append(
            EntityIssue(
                "entity.structure_invalid",
                "Structure minimale d’entité invalide.",
                source,
            )
        )
        return None


def read_entities(root: str | PathLike[str]) -> EntitiesResult:
    """Inspecter les dossiers directs, en ordre lexical, via descripteurs ancrés."""
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    errors: list[EntityIssue] = []
    entities: list[EntityInfo] = []
    location = SourceLocation("mvc/entities")
    if not all(
        hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")
    ):
        return EntitiesResult(
            errors=(
                EntityIssue(
                    "entity.unreadable", "Lecture sécurisée indisponible.", location
                ),
            )
        )
    try:
        with _directory(str(canonical)) as project, _directory("mvc", project) as mvc:
            with _directory("entities", mvc) as directory:
                for name in sorted(os.listdir(directory)):
                    if (
                        not re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name)
                        or name == "env"
                        or name.startswith(
                            ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
                        )
                    ):
                        continue
                    try:
                        metadata = os.stat(
                            name, dir_fd=directory, follow_symlinks=False
                        )
                    except OSError:
                        errors.append(
                            EntityIssue(
                                "entity.unreadable",
                                "Dossier d’entité inaccessible.",
                                SourceLocation(f"mvc/entities/{name}"),
                            )
                        )
                        continue
                    if S_ISREG(metadata.st_mode):
                        continue
                    if not S_ISDIR(metadata.st_mode):
                        errors.append(
                            EntityIssue(
                                "entity.unreadable",
                                "Dossier d’entité refusé.",
                                SourceLocation(f"mvc/entities/{name}"),
                            )
                        )
                        continue
                    if entity := _load(directory, name, errors):
                        entities.append(entity)
    except FileNotFoundError:
        return EntitiesResult(
            tuple(entities),
            tuple(errors),
            (
                EntityIssue(
                    "entity.source_missing",
                    "Dossier des entités absent ou disparu.",
                    location,
                ),
            ),
        )
    except OSError:
        errors.append(
            EntityIssue("entity.unreadable", "Dossier inaccessible ou lié.", location)
        )
    return EntitiesResult(tuple(entities), tuple(errors))
