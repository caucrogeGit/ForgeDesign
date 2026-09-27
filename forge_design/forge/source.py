"""Références relatives et lecture confinée des espaces source autorisés."""

import os
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


def source_parts(path: str) -> tuple[str, ...]:
    """Politique lexicale, sans normalisation ni consultation filesystem."""
    parts = tuple(path.split("/"))
    if (
        len(path) > MAX_SOURCE_PATH_LENGTH
        or len(parts) < 3
        or parts[0] != "mvc"
        or parts[1] not in {"routes", "controllers", "views"}
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
        or (parts[1] != "views" and (len(parts) != 3 or not parts[-1].endswith(".py")))
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


def read_project_source(root: Path, path: str) -> str:
    """Lire au plus 1 Mio via descripteurs de dossiers, sans suivre de symlink.

    Le support openat/O_NOFOLLOW est exigé : aucun repli moins strict.
    root est la racine canonique fournie par le contexte projet.
    """
    parts = source_parts(path)
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        raise SourceReadError("Lecture source sécurisée indisponible sur ce système.")
    descriptors: list[int] = []
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors.append(os.open(root, directory_flags))
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
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            data = stream.read(MAX_SOURCE_BYTES + 1)
        if len(data) > MAX_SOURCE_BYTES:
            raise SourceReadError("Source supérieure à 1 Mio.")
        return data.decode("utf-8-sig")
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError) as error:
        raise SourceReadError("Source inaccessible, liée ou non UTF-8.") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
