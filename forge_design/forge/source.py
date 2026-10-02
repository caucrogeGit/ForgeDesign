"""Références relatives et lecture confinée des espaces source autorisés."""

import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from forge_design.limits import MAX_SOURCE_BYTES, MAX_SOURCE_PATH_LENGTH


@dataclass(frozen=True)
class SourceLocation:
    path: str
    line: int | None = None


class SourceReadError(ValueError):
    """Source refusée ou non lisible selon le contrat de la vue source."""


def _is_entity_source(parts: tuple[str, ...]) -> bool:
    return parts == ("mvc", "entities", "relations.json") or (
        len(parts) == 4
        and re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", parts[2]) is not None
        and parts[3] == parts[2] + ".json"
    )


def unsafe_relative_path(path: str) -> bool:
    """Politique lexicale commune des chemins relatifs lus dans un projet.

    Refuse les chemins trop longs, segments vides ou cachés (donc . et ..),
    segment env, clés (.pem, .key, id_rsa…), antislash, deux-points et NUL.
    Aucune normalisation ni consultation filesystem.
    """
    parts = path.split("/")
    return (
        len(path) > MAX_SOURCE_PATH_LENGTH
        or any(not part or part.startswith(".") for part in parts)
        or any(
            part.casefold() == "env"
            or part.casefold().endswith((".pem", ".key"))
            or part.casefold().startswith(
                ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
            )
            for part in parts
        )
        or any(c in path for c in ("\\", ":", "\x00"))
    )


def source_parts(path: str) -> tuple[str, ...]:
    """Politique lexicale, sans normalisation ni consultation filesystem."""
    parts = tuple(path.split("/"))
    if (
        unsafe_relative_path(path)
        or len(parts) < 3
        or parts[0] != "mvc"
        or parts[1] not in {"routes", "controllers", "views", "entities"}
        or (
            parts[1] in {"routes", "controllers"}
            and (len(parts) != 3 or not parts[-1].endswith(".py"))
        )
        or (parts[1] == "entities" and not _is_entity_source(parts))
    ):
        raise SourceReadError("Chemin source refusé.")
    return parts


def template_source(reference: str) -> SourceLocation | None:
    path = "mvc/views/" + reference
    try:
        source_parts(path)
    except SourceReadError:
        return None
    return SourceLocation(path)


@dataclass(frozen=True)
class SourceContent:
    text: str
    size: int
    modified_ns: int


def read_project_source(root: Path, path: str) -> str:
    """Contrat historique : retourner exclusivement le texte source."""
    return read_project_source_details(root, path).text


@dataclass(frozen=True)
class SourceMetadata:
    size: int
    modified_ns: int


@contextmanager
def _open_project_source(
    root: Path, path: str
) -> Generator[tuple[int, os.stat_result], None, None]:
    """Ouverture confinée commune, sans lecture ; root doit être canonique."""
    parts = source_parts(path)
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise SourceReadError("Lecture source sécurisée indisponible sur ce système.")
    descriptors: list[int] = []
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        # Ancrer aussi chaque parent de la racine : O_NOFOLLOW sur le seul
        # chemin complet ne protège pas ses segments intermédiaires.
        root_parts = root.absolute().parts
        descriptors.append(os.open(root_parts[0], directory_flags))
        for part in root_parts[1:]:
            if part == "..":
                raise SourceReadError("Racine source non canonique.")
            descriptors.append(os.open(part, directory_flags, dir_fd=descriptors[-1]))
        for part in parts[:-1]:
            descriptor = os.open(part, directory_flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            if not S_ISDIR(os.fstat(descriptor).st_mode):
                raise SourceReadError("Parent source refusé.")
        metadata = os.stat(parts[-1], dir_fd=descriptors[-1], follow_symlinks=False)
        if not S_ISREG(metadata.st_mode):
            raise SourceReadError("La source doit être un fichier ordinaire sans lien.")
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=descriptors[-1],
        )
        descriptors.append(descriptor)
        opened = os.fstat(descriptor)
        if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
            raise SourceReadError("Source remplacée pendant l’ouverture.")
        if opened.st_size > MAX_SOURCE_BYTES:
            raise SourceReadError("Source supérieure à 1 Mio.")
        yield descriptor, opened
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError) as error:
        raise SourceReadError("Source inaccessible, liée ou non UTF-8.") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def inspect_project_source(root: Path, path: str) -> SourceMetadata:
    """Vérifier ouverture/identité/taille sans lire ou décoder le contenu."""
    with _open_project_source(root, path) as (_, opened):
        return SourceMetadata(opened.st_size, opened.st_mtime_ns)


def read_source_bytes(descriptor: int, opened: os.stat_result) -> bytes:
    """Lire un descripteur régulier déjà contrôlé, en vérifiant sa stabilité."""
    with os.fdopen(os.dup(descriptor), "rb") as stream:
        data = stream.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise SourceReadError("Source supérieure à 1 Mio.")
    current = os.fstat(descriptor)
    if (
        current.st_size != opened.st_size
        or current.st_mtime_ns != opened.st_mtime_ns
        or current.st_ctime_ns != opened.st_ctime_ns
        or len(data) != opened.st_size
    ):
        raise SourceReadError("Source modifiée pendant la lecture.")
    return data


def read_project_source_bytes(root: Path, path: str) -> tuple[bytes, os.stat_result]:
    """Octets et métadonnées issus de la même lecture confinée."""
    with _open_project_source(root, path) as (descriptor, opened):
        return read_source_bytes(descriptor, opened), opened


def read_project_source_details(root: Path, path: str) -> SourceContent:
    """Lire au plus 1 Mio UTF-8 via l'ouverture sécurisée commune."""
    data, opened = read_project_source_bytes(root, path)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as error:
        raise SourceReadError("Source inaccessible, liée ou non UTF-8.") from error
    return SourceContent(text, opened.st_size, opened.st_mtime_ns)
