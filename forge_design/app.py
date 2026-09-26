"""Composition explicite des Tools intégrés de Forge Design."""

from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.project_inspector import ProjectInspectorTool
from forge_design.tools.route_explorer import RouteExplorerTool


def create_tool_registry() -> ToolRegistry:
    """Construire un registre indépendant, sans exécuter les Tools enregistrés."""
    registry = ToolRegistry()
    registry.register(ProjectInspectorTool())
    registry.register(RouteExplorerTool())
    return registry
