"""Reconnaissance structurelle bornée, sans lecture du contenu du projet."""

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from stat import S_ISDIR, S_ISLNK, S_ISREG
from typing import Literal

from forge_design.forge.project_root import resolve_project_root

OPTIONAL_MVC_DIRECTORIES = (
    "controllers",
    "entities",
    "forms",
    "helpers",
    "models",
    "validators",
    "views",
)


StructureState = Literal["present", "absent", "invalid"]


@dataclass(frozen=True)
class StructureEntry:
    """État observé d'un élément du squelette, sans interprétation des messages."""

    label: str
    required: bool
    state: StructureState


@dataclass(frozen=True)
class ForgeProjectDiagnostic:
    """Diagnostic immuable ; les messages nomment les chemins relatifs concernés.

    ``entries`` donne, dans l'ordre des contrôles, l'état de chaque élément
    vérifié ; ``errors`` et ``warnings`` en restent la forme textuelle publique.
    """

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    entries: tuple[StructureEntry, ...] = ()


def _check(path: Path, label: str, *, directory: bool) -> tuple[StructureState, str]:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "absent", f"{label} : absent."
    except OSError:
        return "invalid", f"{label} : impossible de vérifier le type."
    if S_ISLNK(mode):
        return "invalid", f"{label} : lien symbolique non accepté."
    expected = S_ISDIR if directory else S_ISREG
    if not expected(mode):
        kind = "dossier" if directory else "fichier ordinaire"
        return "invalid", f"{label} : type incorrect, {kind} attendu."
    return "present", ""


def detect_forge_project(root: str | PathLike[str]) -> ForgeProjectDiagnostic:
    """Reconnaître le squelette Forge actuel sans importer ni lire ses fichiers.

    La racine passe toujours par resolve_project_root ; ses exceptions restent
    publiques. Les trois fichiers d'entrée, mvc/ et mvc/routes/ sont nécessaires.
    Les autres dossiers MVC sont optionnels. Les liens de signature sont refusés,
    même internes ; un mvc invalide n'est jamais parcouru. Aucun parcours récursif.
    Comme la résolution de racine, cette inspection ponctuelle suppose que le
    filesystem ne change pas pendant l'appel (pas de garantie contre les courses).
    Un résultat valide ne garantit ni l'authenticité ni l'exécutabilité du projet.
    """
    canonical = resolve_project_root(root)
    errors: list[str] = []
    warnings: list[str] = []
    entries: list[StructureEntry] = []

    def check(label: str, *, directory: bool, required: bool) -> bool:
        state, problem = _check(canonical / label, label, directory=directory)
        entries.append(StructureEntry(label, required, state))
        if state != "present":
            (errors if required else warnings).append(problem)
        return state == "present"

    for name in ("app.py", "bootstrap.py", "config.py"):
        check(name, directory=False, required=True)
    if check("mvc", directory=True, required=True):
        check("mvc/routes", directory=True, required=True)
        for name in OPTIONAL_MVC_DIRECTORIES:
            check(f"mvc/{name}", directory=True, required=False)
    return ForgeProjectDiagnostic(
        not errors, tuple(errors), tuple(warnings), tuple(entries)
    )
