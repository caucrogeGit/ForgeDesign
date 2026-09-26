"""Contrat structurel des Tools synchrones en lecture seule."""

from pathlib import Path
from typing import Protocol, TypeVar

Result_co = TypeVar("Result_co", covariant=True)


class Tool(Protocol[Result_co]):
    """Capacité identifiable ; résultat spécifique et erreurs explicites.

    L'identifiant est stable et en kebab-case. L'entrée peut être non canonique :
    sa validation appartient au Tool via le Bridge, pas à ce contrat.
    run ne modifie pas le projet et conserve les exceptions de son API métier.
    Ces obligations sont sémantiques, sans validation ou sandbox générique.
    """

    @property
    def id(self) -> str:
        """Identifiant technique stable en kebab-case."""
        ...

    @property
    def name(self) -> str:
        """Nom d'affichage."""
        ...

    @property
    def description(self) -> str:
        """Responsabilité courte."""
        ...

    def run(self, project_root: Path) -> Result_co:
        """Exécuter le cas d'usage de manière synchrone et en lecture seule."""
        ...
