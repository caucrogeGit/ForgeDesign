"""Placement borné par la taille du graphe, indépendant de sa topologie."""

from dataclasses import dataclass

from forge_design.graphics.lanes import (
    DEFAULT_STUB,
    HorizontalSpan,
    allocate_horizontal_lanes,
    lane_label_position,
    route_via_horizontal_lane,
    svg_path,
)
from forge_design.tools.entity_graph import (
    EntityGraph,
    EntityGraphEdge,
    EntityGraphNode,
)

NODE_WIDTH = 260
NODE_HEIGHT = 100


@dataclass(frozen=True)
class PositionedEntityNode:
    node: EntityGraphNode
    x: int
    y: int
    width: int
    height: int
    label: str
    table: str


@dataclass(frozen=True)
class PositionedEntityEdge:
    edge: EntityGraphEdge
    path: str
    label_x: int
    label_y: int
    label: str
    # Polyligne orthogonale (couloirs partagés) dont path est la forme SVG.
    points: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class EntityGraphLayout:
    nodes: tuple[PositionedEntityNode, ...]
    edges: tuple[PositionedEntityEdge, ...]
    width: int
    height: int


def _short(text: str) -> str:
    return text if len(text) <= 30 else text[:29] + "…"


def layout_entity_graph(graph: EntityGraph) -> EntityGraphLayout:
    """Deux colonnes et des couloirs supérieurs partagés, cycles compris.

    Le contrat d'entrée exige des IDs uniques et des extrémités présentes.
    Deux arêtes ne partagent un couloir que si leurs parcours horizontaux
    sont disjoints ; les segments verticaux peuvent coïncider.
    """
    counts = {"entity": 0, "pivot": 0}
    # Première passe : colonnes et rangs ; les abscisses suffisent aux couloirs.
    slots: list[tuple[EntityGraphNode, int, int]] = []
    for node in graph.nodes:
        slots.append((node, 480 if node.kind == "pivot" else 40, counts[node.kind]))
        counts[node.kind] += 1
    x_of = {node.id: x for node, x, _ in slots}
    plan = allocate_horizontal_lanes(
        [
            HorizontalSpan(
                edge.id,
                x_of[edge.source] + NODE_WIDTH + DEFAULT_STUB,
                x_of[edge.target] - DEFAULT_STUB,
            )
            for edge in graph.edges
        ]
    )
    # Les nœuds se placent sous les couloirs réellement utilisés.
    top = plan.band_bottom + 30
    nodes = [
        PositionedEntityNode(
            node,
            x,
            top + row * 140,
            NODE_WIDTH,
            NODE_HEIGHT,
            _short(node.label),
            _short(node.table),
        )
        for node, x, row in slots
    ]
    positions = {item.node.id: item for item in nodes}
    edges: list[PositionedEntityEdge] = []
    for edge in graph.edges:
        source, target = positions[edge.source], positions[edge.target]
        points = route_via_horizontal_lane(
            (source.x + source.width, source.y + source.height // 2),
            (target.x, target.y + target.height // 2),
            plan.y(edge.id),
        )
        label_x, label_y = lane_label_position(points)
        edges.append(
            PositionedEntityEdge(
                edge, svg_path(points), label_x, label_y, _short(edge.label), points
            )
        )
    return EntityGraphLayout(
        tuple(nodes),
        tuple(edges),
        max((n.x + n.width + 40 for n in nodes), default=340),
        max((n.y + n.height + 40 for n in nodes), default=160),
    )
