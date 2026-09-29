"""Inventaire physique borné et texte brut des templates locaux, sans Jinja."""

import os
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import (
    read_project_source_details,
    source_parts,
    template_source,
)
from forge_design.limits import (
    MAX_TEMPLATE_DIRECTORY_ENTRIES,
    MAX_TEMPLATE_FILES,
    MAX_TEMPLATE_SCAN_DEPTH,
)


@dataclass(frozen=True)
class TemplateInfo:
    path: str
    size: int
    modified_ns: int


@dataclass(frozen=True)
class TemplateIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class TemplatesResult:
    templates: tuple[TemplateInfo, ...]
    issues: tuple[TemplateIssue, ...]
    source_present: bool
    truncated: bool


@dataclass(frozen=True)
class TemplateSource:
    path: str
    size: int
    modified_ns: int
    text: str


def _root(root: Path) -> Path:
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    return canonical


def read_template_source(root: Path, template_path: str) -> TemplateSource:
    source_parts("mvc/views/" + template_path)
    canonical = _root(root)
    content = read_project_source_details(canonical, "mvc/views/" + template_path)
    return TemplateSource(
        template_path, content.size, content.modified_ns, content.text
    )


def read_templates(root: Path) -> TemplatesResult:
    """Scanner des descripteurs ancrés ; aucune lecture du contenu des fichiers.

    À volume borné, parcours lexical déterministe. Au-delà du budget de noms,
    le sous-ensemble découvert dépend de l'énumération du filesystem.
    """
    canonical = _root(root)
    templates: list[TemplateInfo] = []
    issues: list[TemplateIssue] = []
    entries = 0
    discovery_exhausted = False
    truncated = False
    present = False

    def truncate() -> None:
        nonlocal truncated
        if not truncated:
            issues.append(
                TemplateIssue(
                    "template.analysis_truncated",
                    "Inventaire limité : certains templates n'ont pas été inspectés.",
                )
            )
        truncated = True

    def scan(directory: int, prefix: str, depth: int) -> None:
        nonlocal entries, discovery_exhausted
        if discovery_exhausted:
            return
        names: list[str] = []
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if entries >= MAX_TEMPLATE_DIRECTORY_ENTRIES:
                    discovery_exhausted = True
                    truncate()
                    break
                entries += 1
                names.append(entry.name)
        for name in sorted(names):
            path = prefix + name
            if template_source(path) is None:
                continue
            try:
                metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if S_ISDIR(metadata.st_mode):
                    if depth >= MAX_TEMPLATE_SCAN_DEPTH:
                        truncate()
                        continue
                    with open_directory(name, directory) as child:
                        if not os.path.samestat(metadata, os.fstat(child)):
                            raise OSError("Dossier remplacé.")
                        scan(child, path + "/", depth + 1)
                elif S_ISREG(metadata.st_mode):
                    if len(templates) >= MAX_TEMPLATE_FILES:
                        truncate()
                        continue
                    descriptor = os.open(
                        name,
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                        dir_fd=directory,
                    )
                    try:
                        opened = os.fstat(descriptor)
                        if not S_ISREG(opened.st_mode) or not os.path.samestat(
                            metadata, opened
                        ):
                            raise OSError("Fichier remplacé.")
                        templates.append(
                            TemplateInfo(path, opened.st_size, opened.st_mtime_ns)
                        )
                    finally:
                        os.close(descriptor)
            except OSError:
                issues.append(
                    TemplateIssue(
                        "template.unreadable", "Template ou dossier inaccessible.", path
                    )
                )

    try:
        with open_directory(str(canonical)) as project:
            with open_directory("mvc", project) as mvc:
                try:
                    metadata = os.stat("views", dir_fd=mvc, follow_symlinks=False)
                except FileNotFoundError:
                    return TemplatesResult((), (), False, False)
                present = True
                with open_directory("views", mvc) as views:
                    if not os.path.samestat(metadata, os.fstat(views)):
                        raise OSError("Dossier remplacé.")
                    scan(views, "", 0)
    except OSError:
        issues.append(
            TemplateIssue(
                "template.unreadable", "Racine mvc/views inaccessible ou liée."
            )
        )
    return TemplatesResult(
        tuple(sorted(templates, key=lambda item: item.path)),
        tuple(issues),
        present,
        truncated,
    )
