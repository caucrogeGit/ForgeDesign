"""Adaptateur Entity Explorer → GraphicScene (deuxième client du Graphic Core).

Transformation pure d'un EntityGraphLayout déjà calculé : aucun accès au
projet, aucun nouvel appel au Tool. Les notions Entity Explorer (entité, pivot,
relation, table, champs) restent ici ; le moteur ne reçoit que des nœuds, des
arêtes, du texte, des présentations génériques et des données opaques.
"""

from typing import Any

from forge_design.web.entity_graph_layout import EntityGraphLayout

KIND_LABELS = {"entity": "Entité", "pivot": "Pivot"}
_VARIANTS = {"entity": "category-1", "pivot": "category-2"}
_FIELD_LABELS = {"entity": "Champs", "pivot": "Champs supplémentaires"}
# Niveaux de détail (FD-GRAPHICS-006), indices dans les lignes
# [type — champs, nom, table] : vue d'ensemble sans texte, normal = nom seul,
# detail = toutes les lignes. Le panneau garde les informations complètes.
LEVEL_OVERVIEW: tuple[int, ...] = ()
LEVEL_NORMAL: tuple[int, ...] = (1,)
SCENE_TITLE = "Entités et relations déclarées"
SCENE_DESCRIPTION = (
    "Entités à gauche, pivots à droite. Les flèches indiquent le sens des "
    "relations. Les tableaux suivants présentent tous les détails."
)


def build_entity_graphic_scene(layout: EntityGraphLayout) -> dict[str, Any]:
    """GraphicScene sérialisable ; identités de l'EntityGraph reprises telles quelles.

    Les identités d'arêtes (``relation:<i>``, ``relation:<i>:from|to``) portent
    l'indice de la déclaration : deux relations parallèles restent distinctes.
    """
    nodes: list[dict[str, Any]] = []
    for item in layout.nodes:
        node = item.node
        kind = KIND_LABELS[node.kind]
        lines = [f"{kind} — {node.field_count} champs", item.label]
        if node.kind == "entity":
            lines.append(item.table)
        nodes.append(
            {
                "id": node.id,
                "label": f"{kind} {node.label}",
                "rect": {
                    "x": item.x,
                    "y": item.y,
                    "width": item.width,
                    "height": item.height,
                },
                "lines": lines,
                "levels": {
                    "overview": list(LEVEL_OVERVIEW),
                    "normal": list(LEVEL_NORMAL),
                },
                "presentation": {"variant": _VARIANTS[node.kind]},
                "data": {
                    "kind-label": kind,
                    "name": node.label,
                    "table": node.table,
                    "field-count": str(node.field_count),
                    "field-label": _FIELD_LABELS[node.kind],
                },
            }
        )
    edges: list[dict[str, Any]] = []
    for item in layout.edges:
        edge = item.edge
        scene_edge: dict[str, Any] = {
            "id": edge.id,
            "source": edge.source,
            "target": edge.target,
            "points": [{"x": x, "y": y} for x, y in item.points],
            "presentation": {"arrow": "end"},
            "data": {"kind": edge.kind, "name": edge.label},
        }
        if item.label:
            scene_edge["label"] = item.label
            scene_edge["labelAt"] = {"x": item.label_x, "y": item.label_y}
        edges.append(scene_edge)
    return {
        "width": layout.width,
        "height": layout.height,
        "title": SCENE_TITLE,
        "description": SCENE_DESCRIPTION,
        "nodes": nodes,
        "edges": edges,
    }
