"""Racine Forge vérifiée une fois pour une opération d'analyse (FD-PERF-001).

``check_forge_root`` fait ce que chaque lecteur faisait jusqu'ici à chaque appel :
résoudre la racine (resolve_project_root) puis reconnaître le squelette Forge
(detect_forge_project), avec les mêmes exceptions. Le résultat est transmis aux
lecteurs d'une même opération (``checked=``) pour qu'ils ne refassent pas ce
travail, par exemple une fois par contrat de vue.

Ce n'est ni un cache, ni un singleton, ni un contexte de projet courant : l'objet
n'existe que pendant l'appel qui l'a créé et ne promet aucun instantané du
système de fichiers. Les protections de chaque fichier lu (descripteurs ancrés,
O_NOFOLLOW, samestat, lectures bornées) restent individuelles.
"""

from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError


@dataclass(frozen=True)
class CheckedForgeRoot:
    """Racine canonique d'un projet reconnu par detect_forge_project."""

    root: Path

    def require(self, root: str | PathLike[str]) -> Path:
        """Racine canonique, si ``root`` est exactement celle vérifiée.

        Aucune nouvelle résolution : un contexte n'est jamais réutilisé pour une
        autre racine, ni pour une forme non canonique de la même.
        """
        if Path(root) != self.root:
            raise ValueError("Racine Forge vérifiée pour une autre racine.")
        return self.root


def check_forge_root(root: str | PathLike[str]) -> CheckedForgeRoot:
    """Résoudre et reconnaître la racine une fois ; mêmes erreurs que les lecteurs."""
    canonical = resolve_project_root(root)
    if not detect_forge_project(canonical).valid:
        raise NotForgeProjectError("La racine n'est pas un projet Forge reconnu.")
    return CheckedForgeRoot(canonical)


def checked_root(root: str | PathLike[str], checked: CheckedForgeRoot | None) -> Path:
    """Racine canonique d'un lecteur : vérification complète sans contexte,
    garde stricte avec un contexte déjà vérifié."""
    if checked is None:
        return check_forge_root(root).root
    return checked.require(root)
