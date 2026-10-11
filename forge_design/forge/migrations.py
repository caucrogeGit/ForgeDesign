"""Inventaire des migrations SQL versionnées, sans lecture ni exécution.

Convention Forge (vérifiée par le diagnostic du projet côté Forge) :
``mvc/migrations/AAAAMMJJHHMMSS_nom.sql``. Forge Design ne fait ici que la petite
analyse nécessaire à la synthèse de Project Inspector : entrées directes de
``mvc/migrations`` seulement, nom (suffixe ``.sql`` et convention), type et taille
par métadonnée pour repérer un fichier vide. Aucun contenu SQL n'est ouvert,
interprété ni exécuté ; aucun lien n'est suivi ; aucune récursion.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISLNK, S_ISREG

from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import MAX_MIGRATION_DIRECTORY_ENTRIES

MIGRATIONS_SOURCE = "mvc/migrations"
MIGRATION_NAME = re.compile(r"\d{14}_[A-Za-z0-9_]+\.sql")


@dataclass(frozen=True)
class MigrationInfo:
    name: str
    size: int


@dataclass(frozen=True)
class MigrationIssue:
    code: str
    message: str
    name: str | None = None


@dataclass(frozen=True)
class MigrationsResult:
    migrations: tuple[MigrationInfo, ...]
    issues: tuple[MigrationIssue, ...]
    source_present: bool
    truncated: bool


def _inspect(
    directory: int,
    name: str,
    migrations: list[MigrationInfo],
    issues: list[MigrationIssue],
) -> None:
    """Métadonnées d'une entrée ``.sql`` (sans suivre de lien, sans l'ouvrir)."""
    try:
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except OSError:
        issues.append(
            MigrationIssue("migration.unreadable", "Migration inaccessible.", name)
        )
        return
    if not S_ISREG(info.st_mode):
        kind = "lien symbolique" if S_ISLNK(info.st_mode) else "entrée non ordinaire"
        issues.append(
            MigrationIssue(
                "migration.not_regular", f"Migration ignorée : {kind}.", name
            )
        )
        return
    migrations.append(MigrationInfo(name, info.st_size))
    if MIGRATION_NAME.fullmatch(name) is None:
        issues.append(
            MigrationIssue(
                "migration.name_invalid",
                "Nom non conforme : AAAAMMJJHHMMSS_nom.sql attendu.",
                name,
            )
        )
    if info.st_size == 0:
        issues.append(
            MigrationIssue("migration.empty", "Fichier de migration vide.", name)
        )


def read_migrations(root: Path) -> MigrationsResult:
    """Lister les fichiers ``.sql`` directs de mvc/migrations, en ordre lexical.

    Un dossier absent n'est pas une anomalie (migrations optionnelles). Les
    autres entrées (sous-dossiers, fichiers sans suffixe ``.sql``) sont ignorées,
    comme dans Forge ; un ``.sql`` qui n'est pas un fichier ordinaire (lien,
    dossier) est signalé.
    """
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    migrations: list[MigrationInfo] = []
    issues: list[MigrationIssue] = []
    truncated = False
    try:
        with open_directory(str(canonical)) as project:
            with open_directory("mvc", project) as mvc:
                try:
                    metadata = os.stat("migrations", dir_fd=mvc, follow_symlinks=False)
                except FileNotFoundError:
                    return MigrationsResult((), (), False, False)
                with open_directory("migrations", mvc) as directory:
                    if not os.path.samestat(metadata, os.fstat(directory)):
                        raise OSError("Dossier remplacé.")
                    names: list[str] = []
                    with os.scandir(directory) as iterator:
                        for entry in iterator:
                            if len(names) >= MAX_MIGRATION_DIRECTORY_ENTRIES:
                                truncated = True
                                break
                            names.append(entry.name)
                    for name in sorted(names):
                        if name.endswith(".sql"):
                            _inspect(directory, name, migrations, issues)
    except OSError:
        issues.append(
            MigrationIssue(
                "migration.unreadable", "Dossier mvc/migrations inaccessible ou lié."
            )
        )
    if truncated:
        issues.append(
            MigrationIssue(
                "migration.analysis_truncated",
                "Inventaire limité : certaines entrées n'ont pas été inspectées.",
            )
        )
    return MigrationsResult(tuple(migrations), tuple(issues), True, truncated)
