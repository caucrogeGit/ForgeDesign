"""Inventaire confiné des ressources spécialisées (FD-MODULES-002).

Trouve, sous l'espace de sources d'un type, les fichiers ordinaires portant son
suffixe, sans jamais lire ni décoder leur contenu. Mêmes principes que l'hôte
de lecture : chaque dossier ouvert relativement à son parent, sans suivre de
lien (O_NOFOLLOW), identité vérifiée (samestat) ; liens, FIFO et autres entrées
non ordinaires ignorés ; chemins revalidés par resource_parts ; bornes
explicites et troncature signalée. Inventaire au mieux, pas un instantané
atomique du dossier : une entrée remplacée pendant le parcours est écartée.
"""

import os
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from forge_design.forge.filesystem import open_directory
from forge_design.limits import (
    MAX_SPECIALIZED_DIRECTORY_ENTRIES,
    MAX_SPECIALIZED_ISSUES,
    MAX_SPECIALIZED_LISTED_RESOURCES,
    MAX_SPECIALIZED_SCAN_DEPTH,
)
from forge_design.specialized.models import (
    SpecializedIssue,
    SpecializedResourceType,
    SpecializedToolDefinition,
)
from forge_design.specialized.resource import (
    _Refused,  # pyright: ignore[reportPrivateUsage]
    _root,  # pyright: ignore[reportPrivateUsage]
    _type_of,  # pyright: ignore[reportPrivateUsage]
    resource_parts,
)


@dataclass(frozen=True)
class SpecializedResourceListing:
    """Chemins relatifs triés ; ``present`` : l'espace de sources existe."""

    paths: tuple[str, ...]
    present: bool
    truncated: bool
    issues: tuple[SpecializedIssue, ...] = ()


def _issue(message: str, path: str | None = None) -> SpecializedIssue:
    location: tuple[str | int, ...] = (path,) if path else ()
    return SpecializedIssue("resource-refused", "error", message, location=location)


def list_specialized_resources(
    root: Path,
    tool: SpecializedToolDefinition,
    resource_type: SpecializedResourceType,
) -> SpecializedResourceListing:
    """Inventorier sans lire ; racine invalide : exceptions du Bridge (lecture)."""
    _type_of(tool, resource_type)
    canonical = _root(root)
    paths: list[str] = []
    issues: list[SpecializedIssue] = []
    entries = 0
    truncated = False

    def note(message: str, path: str | None = None) -> None:
        nonlocal truncated
        if len(issues) < MAX_SPECIALIZED_ISSUES:
            issues.append(_issue(message, path))
        else:
            truncated = True

    def scan(directory: int, prefix: str, depth: int) -> None:
        nonlocal entries, truncated
        names: list[str] = []
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entries >= MAX_SPECIALIZED_DIRECTORY_ENTRIES:
                    truncated = True
                    break
                entries += 1
                names.append(entry.name)
        for name in sorted(names):
            path = f"{prefix}/{name}"
            try:
                metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if S_ISDIR(metadata.st_mode):
                    if name.startswith("."):
                        continue
                    if depth >= MAX_SPECIALIZED_SCAN_DEPTH:
                        truncated = True
                        continue
                    with open_directory(name, directory) as child:
                        if not os.path.samestat(metadata, os.fstat(child)):
                            raise OSError("Dossier remplacé.")
                        scan(child, path, depth + 1)
                elif S_ISREG(metadata.st_mode) and name.endswith(resource_type.suffix):
                    try:
                        resource_parts(resource_type, path)
                    except _Refused:
                        continue  # même politique lexicale que la lecture
                    if len(paths) >= MAX_SPECIALIZED_LISTED_RESOURCES:
                        truncated = True
                        continue
                    paths.append(path)
            except OSError:
                note("Entrée inaccessible ou remplacée.", path)
            if truncated and len(paths) >= MAX_SPECIALIZED_LISTED_RESOURCES:
                return

    try:
        with ExitStack() as stack:
            directory = stack.enter_context(open_directory(str(canonical)))
            for segment in resource_type.source_prefix.split("/"):
                try:
                    metadata = os.stat(segment, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    return SpecializedResourceListing((), False, False)
                if not S_ISDIR(metadata.st_mode):
                    note("Espace de sources non répertoire ou lié.")
                    return SpecializedResourceListing((), False, False, tuple(issues))
                directory = stack.enter_context(open_directory(segment, directory))
                if not os.path.samestat(metadata, os.fstat(directory)):
                    raise OSError("Dossier remplacé.")
            scan(directory, resource_type.source_prefix, 0)
    except OSError:
        note("Espace de sources inaccessible.")
    return SpecializedResourceListing(
        tuple(sorted(paths)), True, truncated, tuple(issues)
    )
