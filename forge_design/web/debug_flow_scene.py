"""Adaptateur Debug Center → GraphicScene (troisième client du Graphic Core).

Transformation pure d'un DebugFlowLayout déjà calculé : aucun accès au projet,
au journal ni au DebugError. DebugFlow reste la seule autorité sur ce qui peut
apparaître : des étapes renseignées, reliées dans un ordre conceptuel, jamais une
trace d'exécution. Le vocabulaire Debug (requête, route, contrôleur, SQL,
template) reste ici et devient des présentations génériques ; le moteur n'en
connaît aucun.
"""

import json
from typing import Any

from forge_design.tools.debug_flow import DebugFlowKind
from forge_design.web.debug_flow_layout import DebugFlowLayout

# Catégories génériques : elles ne signifient rien par elles-mêmes pour le moteur.
_VARIANTS: dict[DebugFlowKind, str] = {
    "request": "category-1",
    "router": "category-2",
    "controller": "category-3",
    "model": "category-6",
    "sql": "category-4",
    "template": "category-5",
    "response": "default",
}
# Nom accessible borné : une valeur de journal peut atteindre 64 Kio ; la valeur
# complète reste dans les sections Requête HTTP et Contexte Forge de la page.
MAX_ACCESSIBLE_LABEL = 256
# Niveaux de détail (FD-GRAPHICS-006), indices dans [libellé, détail] :
# vue d'ensemble sans texte, normal le libellé, detail le libellé et son détail.
LEVEL_OVERVIEW: tuple[int, ...] = ()
LEVEL_NORMAL: tuple[int, ...] = (0,)
SCENE_TITLE = "Flux des étapes runtime connues"
SCENE_DESCRIPTION = (
    "Seules les informations présentes dans le journal Forge sont représentées, "
    "dans un ordre conceptuel de gauche à droite. Ce schéma ne constitue pas une "
    "trace d'exécution."
)


def _accessible(label: str, detail: str | None) -> str:
    text = f"{label} — {detail}" if detail else label
    if len(text) <= MAX_ACCESSIBLE_LABEL:
        return text
    return text[: MAX_ACCESSIBLE_LABEL - 1] + "…"


def _edge_id(source: str, target: str) -> str:
    # (source, cible) est unique dans un DebugFlow séquentiel : identité dérivée.
    return json.dumps(("debug-flow", source, target), separators=(",", ":"))


def build_debug_graphic_scene(layout: DebugFlowLayout) -> dict[str, Any]:
    """GraphicScene sérialisable ; identités DebugFlow reprises telles quelles."""
    nodes: list[dict[str, Any]] = []
    for item in layout.nodes:
        node = item.node
        # Le détail affiché est celui, déjà tronqué, du layout (SQL : « Requête
        # disponible », jamais la requête).
        lines = [node.label, item.detail] if item.detail else [node.label]
        nodes.append(
            {
                "id": node.id,
                "label": _accessible(node.label, node.detail),
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
            }
        )
    edges = [
        {
            "id": _edge_id(item.edge.source, item.edge.target),
            "source": item.edge.source,
            "target": item.edge.target,
            "points": [{"x": item.x1, "y": item.y1}, {"x": item.x2, "y": item.y2}],
            "presentation": {"arrow": "end"},
        }
        for item in layout.edges
    ]
    return {
        "width": layout.width,
        "height": layout.height,
        "title": SCENE_TITLE,
        "description": SCENE_DESCRIPTION,
        "nodes": nodes,
        "edges": edges,
    }
