"""Lecture locale de la version déclarée, sans résolution de dépendances."""

import os
import re
from dataclasses import dataclass
from os import PathLike
from stat import S_ISREG
from typing import Literal

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root

_SOURCE = "requirements.txt"
_MAX_BYTES = 1024 * 1024


class NotForgeProjectError(ValueError):
    """La racine ne présente pas les signatures Forge nécessaires."""


@dataclass(frozen=True)
class ForgeVersionInfo:
    """Source relative ; détails sans copie du contenu potentiellement sensible."""

    status: Literal["found", "absent", "unreadable", "conflict"]
    version: str | None
    source: str | None
    details: tuple[str, ...] = ()


def _parse(content: str) -> ForgeVersionInfo:
    versions: list[Version] = []
    errors: list[str] = []
    unresolved: list[str] = []
    for number, raw in enumerate(content.splitlines(), 1):
        line = re.split(r"\s+#", raw.strip(), maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        # Ne jamais suivre un include, un chemin éditable ou une continuation.
        if line.startswith(
            ("-r", "-c", "-e", "--requirement", "--constraint", "--editable")
        ) or line.endswith("\\"):
            errors.append(f"Ligne {number} : directive non prise en charge.")
            continue
        name = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", line)
        if name is None or canonicalize_name(name[0]) != "forge-mvc":
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement:
            errors.append(f"Ligne {number} : déclaration Forge invalide.")
            continue
        specs = sorted(requirement.specifier, key=str)
        if (
            requirement.url is not None
            or requirement.marker is not None
            or not specs
            or any(s.operator != "==" or "*" in s.version for s in specs)
        ):
            unresolved.append(
                f"Ligne {number} : aucune version exacte inconditionnelle."
            )
            continue
        versions.extend(Version(s.version) for s in specs)
    if errors:
        return ForgeVersionInfo("unreadable", None, _SOURCE, tuple(errors))
    if len(set(versions)) > 1:
        return ForgeVersionInfo(
            "conflict", None, _SOURCE, ("Déclarations Forge exactes contradictoires.",)
        )
    if unresolved:
        return ForgeVersionInfo("absent", None, _SOURCE, tuple(unresolved))
    if not versions:
        return ForgeVersionInfo(
            "absent", None, _SOURCE, ("Aucune déclaration Forge exacte.",)
        )
    return ForgeVersionInfo("found", str(versions[0]), _SOURCE)


def read_forge_version(root: str | PathLike[str]) -> ForgeVersionInfo:
    """Lire uniquement requirements.txt d'un projet reconnu par le Bridge.

    Retourne found/absent/unreadable/conflict. Les racines invalides conservent
    les exceptions de resolve_project_root ; un projet non reconnu déclenche
    NotForgeProjectError. Aucun import, commande, accès réseau ou include.
    Les versions sont normalisées selon PEP 440, sans contrôle de compatibilité.
    Les liens et fichiers spéciaux sont refusés ; la lecture est bornée à 1 Mio.
    La racine et ses parents doivent rester stables durant l'appel, comme pour
    resolve_project_root et detect_forge_project.
    """
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    path = canonical / _SOURCE
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return ForgeVersionInfo("absent", None, None, ("requirements.txt absent.",))
    except OSError:
        return ForgeVersionInfo("unreadable", None, _SOURCE, ("Source inaccessible.",))
    if not S_ISREG(metadata.st_mode):
        return ForgeVersionInfo(
            "unreadable", None, _SOURCE, ("Un fichier ordinaire sans lien est requis.",)
        )
    try:
        flags = (
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
                return ForgeVersionInfo(
                    "unreadable", None, _SOURCE, ("Source modifiée pendant l'accès.",)
                )
            data = stream.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            return ForgeVersionInfo(
                "unreadable", None, _SOURCE, ("Source supérieure à 1 Mio.",)
            )
        content = data.decode("utf-8-sig")
    except (OSError, UnicodeError):
        return ForgeVersionInfo(
            "unreadable", None, _SOURCE, ("Lecture UTF-8 impossible.",)
        )
    return _parse(content)
