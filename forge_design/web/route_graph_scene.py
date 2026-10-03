"""Adaptateur Route Explorer → GraphicScene (premier client du Graphic Core).

Transformation pure de RouteGraph + RouteGraphLayout déjà calculés : aucun accès
au projet, aucun nouvel appel au Tool. Les notions Route Explorer (route,
handler, contrôleur, template, présence) restent ici et deviennent des
présentations génériques ; le moteur JavaScript n'en connaît aucune.
"""

import json
from typing import Any

from forge_design.forge.routes import TemplatePresenceStatus
from forge_design.tools.route_graph import GraphNodeKind
from forge_design.web.route_graph_layout import RouteGraphLayout

KIND_LABELS: dict[GraphNodeKind, str] = {
    "route": "Route",
    "handler": "Handler",
    "controller": "Contrôleur",
    "template": "Template",
}
PRESENCE_LABELS: dict[TemplatePresenceStatus, str] = {
    "present": "Présent",
    "missing": "Absent",
    "invalid-path": "Chemin refusé",
    "unreadable": "Non vérifiable",
    "not-applicable": "—",
}
_VARIANTS: dict[GraphNodeKind, str] = {
    "route": "category-1",
    "handler": "category-2",
    "controller": "category-3",
    "template": "category-4",
}
# Le ton accompagne toujours un texte (ligne de présence) : jamais la couleur seule.
_WARNING: frozenset[TemplatePresenceStatus] = frozenset(
    {"missing", "invalid-path", "unreadable"}
)
SCENE_TITLE = "Graphe des routes"
SCENE_DESCRIPTION = (
    "Relations connues de gauche à droite : routes, handlers, contrôleurs, "
    "templates principaux puis dépendances."
)


def _edge_id(source: str, target: str, kind: str) -> str:
    # (source, target, kind) est unique dans un RouteGraph : identité dérivée.
    return json.dumps((source, target, kind), ensure_ascii=True, separators=(",", ":"))


def build_route_graphic_scene(layout: RouteGraphLayout) -> dict[str, Any]:
    """GraphicScene sérialisable depuis le layout (qui porte le RouteGraph).

    Identités de nœuds reprises du RouteGraph ; identités d'arêtes dérivées de
    (source, cible, type), unique dans un RouteGraph.
    """
    nodes: list[dict[str, Any]] = []
    for item in layout.nodes:
        node = item.node
        nodes.append(
            {
                "id": node.id,
                "label": node.label,
                "rect": {
                    "x": item.x,
                    "y": item.y,
                    "width": item.width,
                    "height": item.height,
                },
                "lines": [
                    KIND_LABELS[node.kind],
                    item.label,
                    PRESENCE_LABELS[node.presence],
                ],
                "presentation": {
                    "variant": _VARIANTS[node.kind],
                    "tone": "warning" if node.presence in _WARNING else "default",
                },
                "data": {
                    "kind-label": KIND_LABELS[node.kind],
                    "presence-label": PRESENCE_LABELS[node.presence],
                },
            }
        )
    edges: list[dict[str, Any]] = []
    for item in layout.edges:
        edge = item.edge
        edges.append(
            {
                "id": _edge_id(edge.source, edge.target, edge.kind),
                "source": edge.source,
                "target": edge.target,
                "label": edge.kind + (" (cycle)" if edge.in_cycle else ""),
                "labelAt": {"x": item.label_x, "y": item.label_y},
                "points": [{"x": x, "y": y} for x, y in item.points],
                "presentation": {
                    "line": "dashed" if edge.in_cycle else "solid",
                    "arrow": "end",
                },
            }
        )
    return {
        "width": layout.width,
        "height": layout.height,
        "title": SCENE_TITLE,
        "description": SCENE_DESCRIPTION,
        "nodes": nodes,
        "edges": edges,
    }
