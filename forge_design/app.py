"""Composition explicite des Tools intégrés de Forge Design."""

from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.project_inspector import ProjectInspectorTool


def create_tool_registry() -> ToolRegistry:
    """Construire un registre indépendant, sans exécuter les Tools enregistrés."""
    registry = ToolRegistry()
    registry.register(ProjectInspectorTool())
    return registry
