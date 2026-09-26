"""Reconnaissance structurelle bornée, sans lecture du contenu du projet."""

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from stat import S_ISDIR, S_ISLNK, S_ISREG

from forge_design.forge.project_root import resolve_project_root


@dataclass(frozen=True)
class ForgeProjectDiagnostic:
    """Diagnostic immuable ; les messages nomment les chemins relatifs concernés."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _check(path: Path, label: str, *, directory: bool) -> str | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return f"{label} : absent."
    except OSError:
        return f"{label} : impossible de vérifier le type."
    if S_ISLNK(mode):
        return f"{label} : lien symbolique non accepté."
    expected = S_ISDIR if directory else S_ISREG
    if not expected(mode):
        kind = "dossier" if directory else "fichier ordinaire"
        return f"{label} : type incorrect, {kind} attendu."
    return None


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
    for name in ("app.py", "bootstrap.py", "config.py"):
        if problem := _check(canonical / name, name, directory=False):
            errors.append(problem)
    if problem := _check(canonical / "mvc", "mvc", directory=True):
        errors.append(problem)
    else:
        if problem := _check(canonical / "mvc/routes", "mvc/routes", directory=True):
            errors.append(problem)
        for name in (
            "controllers",
            "entities",
            "forms",
            "helpers",
            "models",
            "validators",
            "views",
        ):
            label = f"mvc/{name}"
            if problem := _check(canonical / label, label, directory=True):
                warnings.append(problem)
    return ForgeProjectDiagnostic(not errors, tuple(errors), tuple(warnings))
