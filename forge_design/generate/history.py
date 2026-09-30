"""Journal JSONL de succès déclarés par l'appelant, sans écriture de template."""

import errno
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from stat import S_ISREG
from typing import Literal

from forge_design.forge.filesystem import open_directory
from forge_design.limits import MAX_HISTORY_EVENT_BYTES

HistoryAction = Literal["generate_template"]


@dataclass(frozen=True)
class GenerationHistoryEvent:
    timestamp: str
    action: HistoryAction
    file: str


def _validate_file(value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("Le fichier doit être un chemin relatif non vide.")
    if (
        "\\" in value
        or ":" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("Chemin relatif non canonique.")


def _serialize_history_event(event: GenerationHistoryEvent) -> bytes:
    data = (
        json.dumps(
            {"timestamp": event.timestamp, "action": event.action, "file": event.file},
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    if len(data) > MAX_HISTORY_EVENT_BYTES:
        raise ValueError("Événement supérieur à la limite du journal.")
    return data


def _check_regular(metadata: os.stat_result) -> None:
    if not S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise OSError(
            errno.EPERM, "Le journal doit être un fichier régulier sans hardlink."
        )


def _open_history(directory: int) -> tuple[int, bool]:
    flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0)
    previous = None
    try:
        descriptor = os.open(
            "history.jsonl", flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory
        )
        created = True
    except FileExistsError:
        previous = os.stat("history.jsonl", dir_fd=directory, follow_symlinks=False)
        _check_regular(previous)
        descriptor = os.open("history.jsonl", flags, dir_fd=directory)
        created = False
    try:
        opened = os.fstat(descriptor)
        _check_regular(opened)
        current = os.stat("history.jsonl", dir_fd=directory, follow_symlinks=False)
        if (
            (previous is not None and not os.path.samestat(previous, opened))
            or not os.path.samestat(opened, current)
            or current.st_nlink != 1
        ):
            raise OSError(errno.EPERM, "Journal remplacé pendant son ouverture.")
    except BaseException:
        # Nettoyage seulement ; ne convertir aucune erreur en succès.
        os.close(descriptor)
        raise
    return descriptor, created


def append_generation_history(
    project_root: Path,
    *,
    action: HistoryAction,
    file: str,
    timestamp: datetime | None = None,
) -> GenerationHistoryEvent:
    """Consigner un succès déjà acquis ; un échec peut laisser une ligne sur disque."""
    if action != "generate_template":
        raise ValueError("Action de journal inconnue.")
    _validate_file(file)
    instant = datetime.now(UTC) if timestamp is None else timestamp
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Le timestamp doit comporter un fuseau horaire.")
    event = GenerationHistoryEvent(
        instant.astimezone(UTC).isoformat().replace("+00:00", "Z"), action, file
    )
    data = _serialize_history_event(event)
    if not all(
        hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    ):
        raise OSError(errno.ENOTSUP, "Append POSIX sécurisé indisponible.")
    with open_directory(str(project_root)) as root:
        created_directory = False
        try:
            os.mkdir(".forge-design", 0o700, dir_fd=root)
            created_directory = True
        except FileExistsError:
            pass
        previous = os.stat(".forge-design", dir_fd=root, follow_symlinks=False)
        with open_directory(".forge-design", root) as directory:
            if not os.path.samestat(previous, os.fstat(directory)):
                raise OSError(errno.EPERM, "Dossier du journal remplacé.")
            descriptor, created_file = _open_history(directory)
            try:
                if os.write(descriptor, data) != len(data):
                    raise OSError(errno.EIO, "Écriture incomplète du journal.")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            if created_file:
                os.fsync(directory)
            if created_directory:
                os.fsync(root)
    return event
