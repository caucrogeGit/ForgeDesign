"""Environnement Python du projet Forge, pour les processus lancés sur demande.

Partagé par la preview réelle et le diagnostic Forge (FD-RUNTIME-001) :
l'interpréteur est toujours ``<racine>/.venv/bin/python`` — jamais une
recherche dans PATH, jamais un chemin reçu par HTTP, jamais un repli sur
l'interpréteur de Forge Design — et l'environnement du processus enfant est une
liste blanche construite positivement (aucune variable PYTHON*, aucun secret
hérité par défaut).
"""

import os
from collections.abc import Mapping
from pathlib import Path
from stat import S_ISREG

from forge_design.forge.filesystem import open_directory

# Variables transmises au processus enfant ; toutes les autres sont écartées.
CHILD_ENVIRONMENT_WHITELIST = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "TMPDIR",
)


def project_interpreter(root: Path) -> Path | None:
    """<racine>/.venv/bin/python : dossiers sans lien, cible fichier exécutable.

    Le chemin non résolu est retourné : l'interpréteur reconnaît son venv par
    l'emplacement invoqué, pas par la cible du lien.
    """
    try:
        with open_directory(str(root / ".venv" / "bin")):
            pass
        python = root / ".venv" / "bin" / "python"
        target = python.resolve(strict=True)
        if not S_ISREG(target.stat().st_mode) or not os.access(target, os.X_OK):
            return None
    except (OSError, RuntimeError):
        return None
    return python


def child_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Liste blanche construite positivement à partir de ``source``."""
    return {
        name: source[name] for name in CHILD_ENVIRONMENT_WHITELIST if name in source
    }
