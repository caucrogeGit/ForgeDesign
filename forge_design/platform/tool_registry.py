"""Registre explicite d'instances Tool, sans découverte ni exécution implicite."""

import re

from forge_design.platform.tool import Tool


class DuplicateToolError(ValueError):
    """L'identifiant est déjà enregistré."""


class UnknownToolError(KeyError):
    """L'identifiant n'est pas enregistré."""


class ToolRegistry:
    """Collection hétérogène en ordre d'insertion ; identifiants stables requis.

    La covariance de Tool permet de stocker Tool[object] sans cast. Le résultat
    spécifique est volontairement effacé à cette frontière. Les instances sont
    conservées telles quelles ; leur contrat impose la stabilité de leur id.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool[object]] = {}

    def register(self, tool: Tool[object]) -> None:
        """Ajouter une instance ; refuser un id invalide ou déjà enregistré."""
        tool_id = tool.id
        if re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", tool_id) is None:
            raise ValueError("L'identifiant Tool doit être en kebab-case non vide.")
        if tool_id in self._tools:
            raise DuplicateToolError(f"Tool déjà enregistré : {tool_id}")
        self._tools[tool_id] = tool

    def get(self, tool_id: str) -> Tool[object]:
        """Retourner l'instance ou lever UnknownToolError sans modifier le registre."""
        try:
            return self._tools[tool_id]
        except KeyError:
            raise UnknownToolError(tool_id) from None

    def list(self) -> tuple[Tool[object], ...]:
        """Retourner un instantané immuable en ordre d'enregistrement."""
        return tuple(self._tools.values())
