"""Validation de la racine de travail, sans lecture du contenu du projet."""

from os import PathLike
from pathlib import Path
from stat import S_ISDIR


class ProjectRootNotFoundError(ValueError):
    """La cible n'existe pas."""


class ProjectRootNotDirectoryError(ValueError):
    """La cible ou un composant du chemin n'est pas un dossier."""


class ProjectRootResolutionError(ValueError):
    """Le chemin ne peut pas être résolu ou vérifié."""


def resolve_project_root(path: str | PathLike[str]) -> Path:
    """Retourner un dossier absolu canonique existant.

    Les chemins relatifs partent du répertoire courant. Un lien fourni comme
    racine est accepté et résolu. Aucun contenu du dossier n'est lu.
    Cette validation ponctuelle ne protège pas les accès futurs contre une
    modification du filesystem : chaque lecteur devra contrôler ses cibles.
    """
    try:
        if path == "":
            raise ValueError("chemin vide")
        root = Path(path).resolve(strict=True)
        mode = root.stat().st_mode
    except FileNotFoundError:
        raise ProjectRootNotFoundError("La racine projet n'existe pas.") from None
    except NotADirectoryError:
        raise ProjectRootNotDirectoryError(
            "Un composant du chemin n'est pas un dossier."
        ) from None
    except (OSError, RuntimeError, ValueError):
        raise ProjectRootResolutionError(
            "Impossible de résoudre ou de vérifier la racine projet."
        ) from None

    if not S_ISDIR(mode):
        raise ProjectRootNotDirectoryError("La racine projet n'est pas un dossier.")
    return root
