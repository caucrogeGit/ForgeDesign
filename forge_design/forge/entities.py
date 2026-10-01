"""Lecture des seuls contrats JSON canoniques directs, sans exécution Forge."""

import json
import os
from collections import Counter
from dataclasses import dataclass
from itertools import islice
from os import PathLike
from stat import S_ISDIR, S_ISREG
from typing import Literal, cast

from forge_design.forge.filesystem import open_directory as _directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceLocation, SourceReadError, source_parts
from forge_design.limits import (
    MAX_ENTITY_DIRECTORY_ENTRIES,
    MAX_ENTITY_FIELDS,
    MAX_ENTITY_FILES,
    MAX_ENTITY_PIVOT_FIELDS,
    MAX_ENTITY_RELATIONS,
    MAX_SOURCE_BYTES,
)


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
class ManyToOneInfo:
    foreign_key: str
    nullable: bool
    index: bool
    on_delete: str


@dataclass(frozen=True)
class ManyToManyInfo:
    pivot_table: str
    from_key: str
    to_key: str
    id: bool
    unique_pair: bool
    on_delete: str
    pivot_fields: tuple[EntityFieldInfo, ...] = ()


@dataclass(frozen=True)
class RelationInfo:
    type: Literal["many_to_one", "many_to_many"]
    from_entity: str
    to_entity: str
    name: str
    inverse_name: str | None
    source: SourceLocation
    source_index: int
    many_to_one: ManyToOneInfo | None = None
    many_to_many: ManyToManyInfo | None = None


@dataclass(frozen=True)
class EntityIssue:
    code: str
    message: str
    source: SourceLocation | None = None
    source_index: int | None = None


@dataclass(frozen=True)
class EntitiesResult:
    entities: tuple[EntityInfo, ...] = ()
    errors: tuple[EntityIssue, ...] = ()
    warnings: tuple[EntityIssue, ...] = ()
    relations: tuple[RelationInfo, ...] = ()


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
        tuple(_field(item) for item in cast(list[object], fields)[:MAX_ENTITY_FIELDS]),
        _boolean(options, "timestamps", False),
        _boolean(options, "soft_delete", False),
        source,
    )


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


def _load(
    parent: int,
    folder: str,
    errors: list[EntityIssue],
    warnings: list[EntityIssue],
    metadata: os.stat_result,
) -> EntityInfo | None:
    source = SourceLocation(f"mvc/entities/{folder}/{folder}.json")
    try:
        with _directory(folder, parent) as directory:
            if not os.path.samestat(metadata, os.fstat(directory)):
                raise OSError("Dossier remplacé après découverte.")
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
        entity = _entity(data, source)
        if len(cast(list[object], data["fields"])) > MAX_ENTITY_FIELDS:
            warnings.append(
                EntityIssue(
                    "entity.fields_truncated",
                    f"Champs limités aux {MAX_ENTITY_FIELDS} premières déclarations.",
                    source,
                )
            )
        return entity
    except (ValueError, RecursionError):
        errors.append(
            EntityIssue(
                "entity.structure_invalid",
                "Structure minimale d’entité invalide.",
                source,
            )
        )
        return None


_RELATIONS_SOURCE = SourceLocation("mvc/entities/relations.json")


def _on_delete(value: object) -> str:
    text = _text(value)
    if text not in {"restrict", "cascade", "set_null", "no_action"}:
        raise ValueError("Politique on_delete inconnue.")
    return text


def _relation(data: dict[str, object], index: int) -> RelationInfo:
    kind = data["type"]
    one = None
    many = None
    if kind == "many_to_one":
        one = ManyToOneInfo(
            _text(data.get("foreign_key")),
            _boolean(data, "nullable", True),
            _boolean(data, "index", True),
            _on_delete(data.get("on_delete")),
        )
    else:
        pivot = _object(data.get("pivot"))
        if pivot.get("id") is not True or pivot.get("unique_pair") is not True:
            raise ValueError("id et unique_pair doivent valoir true.")
        fields = pivot.get("fields", [])
        if not isinstance(fields, list):
            raise ValueError("Liste de champs pivot attendue.")
        many = ManyToManyInfo(
            _text(pivot.get("table")),
            _text(pivot.get("from_key")),
            _text(pivot.get("to_key")),
            True,
            True,
            _on_delete(pivot.get("on_delete", "cascade")),
            tuple(
                _field(item)
                for item in cast(list[object], fields)[:MAX_ENTITY_PIVOT_FIELDS]
            ),
        )
    return RelationInfo(
        cast(Literal["many_to_one", "many_to_many"], kind),
        _text(data.get("from")),
        _text(data.get("to")),
        _text(data.get("name")),
        _text(data["inverse_name"]) if "inverse_name" in data else None,
        _RELATIONS_SOURCE,
        index,
        one,
        many,
    )


def _read_relations(
    directory: int,
    entities: list[EntityInfo],
    errors: list[EntityIssue],
    warnings: list[EntityIssue],
) -> tuple[RelationInfo, ...]:
    def issue(code: str, message: str, index: int | None = None) -> None:
        errors.append(
            EntityIssue("relation." + code, message, _RELATIONS_SOURCE, index)
        )

    try:
        content = _read(directory, "relations.json")
    except FileNotFoundError:
        return ()
    except (OSError, UnicodeError):
        issue("unreadable", "Source de relations illisible ou refusée.")
        return ()
    try:
        raw: object = json.loads(content, parse_constant=_constant)
    except (ValueError, RecursionError):
        issue("json_invalid", "JSON des relations invalide.")
        return ()
    try:
        data = _object(raw)
        if "format_version" in data or data.get("schema_version") != "1.0":
            issue(
                "schema_version_unsupported",
                'schema_version "1.0" attendu, sans format legacy.',
            )
            return ()
        items = data.get("relations")
        if not isinstance(items, list):
            raise ValueError("Liste attendue.")
    except ValueError:
        issue("structure_invalid", "Document de relations invalide.")
        return ()
    names = {entity.name for entity in entities}
    result: list[RelationInfo] = []
    if len(cast(list[object], items)) > MAX_ENTITY_RELATIONS:
        warnings.append(
            EntityIssue(
                "relation.analysis_truncated",
                f"Relations limitées à {MAX_ENTITY_RELATIONS} déclarations.",
                _RELATIONS_SOURCE,
            )
        )
    for index, item in enumerate(cast(list[object], items)[:MAX_ENTITY_RELATIONS]):
        try:
            relation_data = _object(item)
            if relation_data.get("type") not in ("many_to_one", "many_to_many"):
                issue("type_unsupported", "Type de relation non pris en charge.", index)
                continue
            relation = _relation(relation_data, index)
            if relation.many_to_many is not None:
                pivot = _object(relation_data["pivot"])
                if (
                    len(cast(list[object], pivot.get("fields", [])))
                    > MAX_ENTITY_PIVOT_FIELDS
                ):
                    warnings.append(
                        EntityIssue(
                            "relation.fields_truncated",
                            f"Champs pivot limités à {MAX_ENTITY_PIVOT_FIELDS}.",
                            _RELATIONS_SOURCE,
                            index,
                        )
                    )
        except (ValueError, RecursionError):
            issue(
                "structure_invalid", "Structure minimale de relation invalide.", index
            )
            continue
        missing = tuple(
            dict.fromkeys(
                name
                for name in (relation.from_entity, relation.to_entity)
                if name not in names
            )
        )
        if missing:
            issue(
                "entity_missing", "Entité non disponible : " + ", ".join(missing), index
            )
        result.append(relation)
    return tuple(result)


def read_entities(root: str | PathLike[str]) -> EntitiesResult:
    """Inspecter les dossiers directs, en ordre lexical, via descripteurs ancrés."""
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    errors: list[EntityIssue] = []
    warnings: list[EntityIssue] = []
    entities: list[EntityInfo] = []
    relations: tuple[RelationInfo, ...] = ()
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
                # Borne aussi les entrées ignorées : listdir matérialisait tout.
                with os.scandir(directory) as entries:
                    names = [
                        entry.name
                        for entry in islice(entries, MAX_ENTITY_DIRECTORY_ENTRIES + 1)
                    ]
                if len(names) > MAX_ENTITY_DIRECTORY_ENTRIES:
                    warnings.append(
                        EntityIssue(
                            "entity.analysis_truncated",
                            f"Découverte bornée : {MAX_ENTITY_DIRECTORY_ENTRIES}.",
                            location,
                        )
                    )
                inspected = 0
                for name in sorted(names[:MAX_ENTITY_DIRECTORY_ENTRIES]):
                    try:
                        source_parts(f"mvc/entities/{name}/{name}.json")
                    except SourceReadError:
                        continue
                    if inspected == MAX_ENTITY_FILES:
                        warnings.append(
                            EntityIssue(
                                "entity.analysis_truncated",
                                f"Inspection limitée à {MAX_ENTITY_FILES} candidats.",
                                location,
                            )
                        )
                        break
                    inspected += 1
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
                    if entity := _load(directory, name, errors, warnings, metadata):
                        entities.append(entity)
                relations = _read_relations(directory, entities, errors, warnings)
    except FileNotFoundError:
        warnings.append(
            EntityIssue(
                "entity.source_missing",
                "Dossier des entités absent ou disparu.",
                location,
            )
        )
    except OSError:
        errors.append(
            EntityIssue("entity.unreadable", "Dossier inaccessible ou lié.", location)
        )
    name_counts = Counter(entity.name for entity in entities)
    table_counts = Counter(entity.table for entity in entities)
    for entity in entities:
        for code, count, label in (
            ("entity.name_duplicate", name_counts[entity.name], "Nom métier"),
            ("entity.table_duplicate", table_counts[entity.table], "Table"),
        ):
            if count > 1:
                warnings.append(
                    EntityIssue(
                        code,
                        f"{label} partagé par {count} entités interprétées.",
                        entity.source,
                    )
                )
    return EntitiesResult(tuple(entities), tuple(errors), tuple(warnings), relations)
