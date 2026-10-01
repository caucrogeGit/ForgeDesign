"""Publication contrôlée d'un template généré, puis journal du succès.

Revalidation avant préparation et juste avant publication, création exclusive,
mise à jour par temporaire du même dossier, vérification relue, fsync, journal.
Ce n'est pas un compare-and-swap : une écriture externe non coopérative entre le
dernier contrôle et os.replace reste possible et n'est détectée qu'après coup.
"""

import hashlib
import os
import secrets
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from stat import S_ISREG

from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.source import source_parts
from forge_design.generate.history import (
    GenerationHistoryEvent,
    append_generation_history,
)
from forge_design.limits import MAX_HISTORY_EVENT_BYTES, MAX_SOURCE_BYTES
from forge_design.safewrite.decision import SafeWriteDecision
from forge_design.safewrite.detection import (
    TemplateChangeResult,
    TemplateRevision,
    TemplateSnapshot,
    TemplateSnapshotError,
    compare_template_snapshots,
    detect_template_change,
    read_template_revision_at,
    snapshot_template,
)

_TEMP_PREFIX = ".forge-design-write-"
# Champs JSON fixes d'un événement, timestamp à microsecondes compris.
_HISTORY_OVERHEAD = 128


@dataclass(frozen=True)
class TemplatePublication:
    path: str
    created: bool
    size: int
    modified_ns: int
    revision: TemplateRevision


@dataclass(frozen=True)
class TemplateWriteResult:
    publication: TemplatePublication
    history_event: GenerationHistoryEvent


class TemplateWriteError(RuntimeError):
    """Écriture impossible ; sauf sous-classe publiée, la cible n'a pas été publiée."""


class TemplateWriteConflictError(TemplateWriteError):
    """La cible ne correspond plus à la révision attendue ; rien n'a été publié."""


class TemplatePublishedError(TemplateWriteError):
    """Le template a été publié, mais une étape suivante a échoué.

    publication est None si le résultat publié n'a pas pu être certifié.
    Aucun rollback : relire la cible avant toute nouvelle tentative.
    """

    def __init__(self, message: str, publication: TemplatePublication | None) -> None:
        super().__init__(message)
        self.publication = publication


class TemplateHistoryError(TemplatePublishedError):
    """Écriture réussie, vérifiée et synchronisée ; traçage incomplet."""

    publication: TemplatePublication

    def __init__(self, message: str, publication: TemplatePublication) -> None:
        super().__init__(message, publication)


def _validate_request(
    generated: object, change: object, decision: object, timestamp: object
) -> bytes:
    """Contrôles purs, avant toute I/O ; ne pas croire les dataclasses fournies."""
    if not isinstance(change, TemplateChangeResult) or not isinstance(
        decision, SafeWriteDecision
    ):
        raise ValueError("Changement ou décision invalide.")
    path = change.path
    if not (
        decision.path == path
        and change.expected.path == path
        and change.current.path == path
    ):
        raise ValueError("Chemins incohérents entre décision et changement.")
    if decision.status != change.status:
        raise ValueError("Statut de décision incohérent avec le changement.")
    if decision.choice != "proceed":
        raise ValueError("Seul le choix proceed autorise une écriture.")
    if change.status != "unchanged":
        raise ValueError("Écriture refusée : la cible est en conflit.")
    if compare_template_snapshots(change.expected, change.current) != "unchanged":
        raise ValueError("Changement falsifié : snapshots divergents.")
    # Ce que le journal refuserait ne doit pas être découvert après publication.
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise ValueError("Chemin non journalisable.")
    if len(path.encode()) + path.count('"') + _HISTORY_OVERHEAD > (
        MAX_HISTORY_EVENT_BYTES
    ):
        raise ValueError("Chemin trop long pour le journal.")
    if timestamp is not None and (
        not isinstance(timestamp, datetime) or timestamp.utcoffset() is None
    ):
        raise ValueError("Le timestamp doit comporter un fuseau horaire.")
    if not isinstance(generated, str):
        raise ValueError("Le contenu généré doit être une chaîne.")
    try:
        # str.encode direct : une sous-classe ne peut pas détourner l'encodage.
        data = str.encode(generated, "utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("Contenu non encodable en UTF-8.") from error
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Template généré supérieur à 1 Mio.")
    return data


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


def _check_current(directory: int, name: str, expected: TemplateSnapshot) -> None:
    try:
        revision = read_template_revision_at(directory, name)
    except (OSError, TemplateSnapshotError) as error:
        raise TemplateWriteConflictError(
            "Cible remplacée ou illisible depuis la décision."
        ) from error
    if revision != expected.revision:
        raise TemplateWriteConflictError("La cible a changé depuis la décision.")


def _previous_mode(directory: int, name: str, created: bool) -> int | None:
    if created:
        return None
    try:
        return os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode
    except FileNotFoundError as error:
        raise TemplateWriteConflictError(
            "Cible supprimée depuis la décision."
        ) from error


def _create_temp(directory: int, temporary: str) -> int:
    """Création exclusive : une collision n'est jamais supprimée par le nettoyage."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK
    return os.open(
        temporary, flags | getattr(os, "O_CLOEXEC", 0), 0o666, dir_fd=directory
    )


def _fill_temp(
    descriptor: int, data: bytes, previous_mode: int | None
) -> os.stat_result:
    """Écrire tout, conserver le mode existant, fsync ; ferme le descripteur."""
    try:
        remaining = memoryview(data)
        while remaining:
            count = os.write(descriptor, remaining)
            if count <= 0:
                raise OSError("Écriture incomplète du temporaire.")
            remaining = remaining[count:]
        if previous_mode is not None:
            os.fchmod(descriptor, previous_mode & 0o777)
        os.fsync(descriptor)
        return os.fstat(descriptor)
    finally:
        os.close(descriptor)


def _publication(
    root: Path,
    path: str,
    data: bytes,
    prepared: os.stat_result,
    created: bool,
) -> TemplatePublication:
    """Relire par le chemin : contenu exact et inode préparé, sinon publié incertain."""
    try:
        published = snapshot_template(root, path)
    except (OSError, ValueError, TemplateSnapshotError) as error:
        raise TemplatePublishedError(
            "Template publié mais illisible ; relire la cible avant toute "
            "nouvelle tentative.",
            None,
        ) from error
    revision = published.revision
    if (
        revision is None
        or revision.digest != hashlib.sha256(data).hexdigest()
        or revision.size != len(data)
        or (revision.device, revision.inode) != (prepared.st_dev, prepared.st_ino)
    ):
        raise TemplatePublishedError(
            "Template publié puis modifié ou remplacé ; relire la cible avant "
            "toute nouvelle tentative.",
            None,
        )
    return TemplatePublication(
        path, created, revision.size, revision.modified_ns, revision
    )


def write_generated_template(
    project_root: Path,
    *,
    generated: str,
    change: TemplateChangeResult,
    decision: SafeWriteDecision,
    timestamp: datetime | None = None,
) -> TemplateWriteResult:
    """Publier generated sur change.path si la cible vaut encore change.current.

    ValueError : demande refusée avant toute I/O.
    TemplateWriteConflictError : cible changée ; rien n'a été publié.
    TemplateWriteError : échec avant publication ; rien n'a été publié.
    TemplatePublishedError : publié, mais non certifié ou non synchronisé.
    TemplateHistoryError : publié et vérifié, journal non écrit.
    """
    data = _validate_request(generated, change, decision, timestamp)
    path = change.path
    parts = source_parts(path)
    name = parts[-1]
    expected = change.current
    created = not expected.exists

    try:
        fresh = detect_template_change(project_root, expected)
    except TemplateSnapshotError as error:
        raise TemplateWriteConflictError(
            "Cible illisible depuis la décision."
        ) from error
    if fresh.status != "unchanged":
        raise TemplateWriteConflictError("La cible a changé depuis la décision.")
    canonical = resolve_project_root(project_root)
    if not _secure_write_available():
        raise TemplateWriteError("Écriture POSIX sécurisée indisponible.")

    published = False
    try:
        with ExitStack() as stack:
            directory = stack.enter_context(open_directory(str(canonical)))
            for part in parts[:-1]:
                directory = stack.enter_context(open_directory(part, directory))
            previous_mode = _previous_mode(directory, name, created)
            # Après le mode : un chmod concurrent change le ctime contrôlé ici.
            _check_current(directory, name, expected)
            temporary = _TEMP_PREFIX + secrets.token_hex(16)
            try:
                descriptor = _create_temp(directory, temporary)
            except FileExistsError as error:
                # Collision : ce fichier n'est pas le nôtre, ne pas y toucher.
                raise TemplateWriteError("Nom temporaire déjà pris.") from error
            try:
                prepared = _fill_temp(descriptor, data, previous_mode)
                current_temp = os.stat(
                    temporary, dir_fd=directory, follow_symlinks=False
                )
                if not S_ISREG(current_temp.st_mode) or not os.path.samestat(
                    prepared, current_temp
                ):
                    raise TemplateWriteError("Temporaire remplacé avant publication.")
                _check_current(directory, name, expected)
                # Le ctime a une granularité grossière : comparer aussi le mode.
                if _previous_mode(directory, name, created) != previous_mode:
                    raise TemplateWriteConflictError(
                        "Permissions de la cible changées depuis la décision."
                    )
                if created:
                    # link refuse une cible apparue après le dernier contrôle.
                    os.link(
                        temporary,
                        name,
                        src_dir_fd=directory,
                        dst_dir_fd=directory,
                        follow_symlinks=False,
                    )
                    published = True
                    os.unlink(temporary, dir_fd=directory)
                else:
                    os.replace(
                        temporary, name, src_dir_fd=directory, dst_dir_fd=directory
                    )
                    published = True
            except BaseException:
                # Le temporaire est retiré tant qu'il n'est pas devenu la cible.
                if not published:
                    try:
                        os.unlink(temporary, dir_fd=directory)
                    except FileNotFoundError:
                        pass
                raise
            publication = _publication(canonical, path, data, prepared, created)
            try:
                os.fsync(directory)
            except OSError as error:
                raise TemplatePublishedError(
                    "Template publié mais dossier non synchronisé.", publication
                ) from error
    except TemplateWriteError:
        raise
    except FileExistsError as error:
        if published:
            raise TemplatePublishedError(
                "Template publié ; état du temporaire incertain.", None
            ) from error
        raise TemplateWriteConflictError("Cible apparue avant publication.") from error
    except OSError as error:
        if published:
            raise TemplatePublishedError(
                "Template publié ; relire la cible avant toute nouvelle tentative.",
                None,
            ) from error
        raise TemplateWriteError(
            "Écriture impossible ; relire la cible avant de réessayer."
        ) from error

    try:
        event = append_generation_history(
            canonical, action="generate_template", file=path, timestamp=timestamp
        )
    except (OSError, ValueError) as error:
        # Aucun retry ni rollback : restaurer pourrait écraser un tiers.
        raise TemplateHistoryError(
            "Template écrit et vérifié, journal non écrit.", publication
        ) from error
    return TemplateWriteResult(publication, event)
