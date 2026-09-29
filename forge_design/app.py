"""Composition explicite des Tools intégrés de Forge Design."""

from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.debug_center import DebugCenterTool
from forge_design.tools.entity_explorer import EntityExplorerTool
from forge_design.tools.project_inspector import ProjectInspectorTool
from forge_design.tools.route_explorer import RouteExplorerTool


def create_tool_registry() -> ToolRegistry:
    """Construire un registre indépendant, sans exécuter les Tools enregistrés."""
    registry = ToolRegistry()
    registry.register(ProjectInspectorTool())
    registry.register(RouteExplorerTool())
    registry.register(EntityExplorerTool())
    registry.register(DebugCenterTool())
    return registry
