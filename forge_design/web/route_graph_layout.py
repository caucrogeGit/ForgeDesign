"""Placement pur et déterministe du graphe, sans découverte de relations."""

from collections import deque
from dataclasses import dataclass

from forge_design.graphics.lanes import (
    DEFAULT_STUB,
    HorizontalSpan,
    allocate_horizontal_lanes,
    lane_label_position,
    route_via_horizontal_lane,
    svg_path,
)
from forge_design.tools.route_graph import GraphEdge, GraphNode, RouteGraph

NODE_WIDTH = 260
NODE_HEIGHT = 100


@dataclass(frozen=True)
class PositionedNode:
    node: GraphNode
    x: int
    y: int
    width: int
    height: int
    label: str


@dataclass(frozen=True)
class PositionedEdge:
    edge: GraphEdge
    path: str
    label_x: int
    label_y: int
    # Polyligne orthogonale (couloirs partagés) dont path est la forme SVG.
    points: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class RouteGraphLayout:
    nodes: tuple[PositionedNode, ...]
    edges: tuple[PositionedEdge, ...]
    width: int
    height: int


def layout_route_graph(graph: RouteGraph) -> RouteGraphLayout:
    """Distances minimales multi-sources, sans découverte ni détection de cycle.

    Un template principal reste au niveau 3 même s'il est aussi dépendance.
    Les éventuels templates sans chemin depuis un principal restent au niveau 4.
    """
    templates = {node.id for node in graph.nodes if node.kind == "template"}
    adjacency: dict[str, list[str]] = {key: [] for key in templates}
    levels: dict[str, int] = {}
    for edge in graph.edges:
        if edge.kind == "renders" and edge.target in templates:
            levels[edge.target] = 3
        elif edge.source in templates and edge.target in templates:
            adjacency[edge.source].append(edge.target)
    queue = deque(levels)
    while queue:
        source = queue.popleft()
        for target in adjacency[source]:
            if target not in levels:
                levels[target] = levels[source] + 1
                queue.append(target)
    columns = {"route": 0, "handler": 1, "controller": 2}
    counts: dict[int, int] = {}
    # Première passe : colonnes et rangs ; les abscisses suffisent aux couloirs.
    slots: list[tuple[GraphNode, int, int]] = []
    for node in graph.nodes:
        column = (
            levels.get(node.id, 4) if node.kind == "template" else columns[node.kind]
        )
        row = counts.get(column, 0)
        slots.append((node, 30 + column * 360, row))
        counts[column] = row + 1
    x_of = {node.id: x for node, x, _ in slots}
    plan = allocate_horizontal_lanes(
        [
            HorizontalSpan(
                str(index),
                x_of[edge.source] + NODE_WIDTH + DEFAULT_STUB,
                x_of[edge.target] - DEFAULT_STUB,
            )
            for index, edge in enumerate(graph.edges)
        ]
    )
    # Les nœuds se placent sous les couloirs réellement utilisés.
    top = plan.band_bottom + 30
    nodes: list[PositionedNode] = []
    for node, x, row in slots:
        label = node.label if len(node.label) <= 30 else node.label[:29] + "…"
        nodes.append(
            PositionedNode(node, x, top + row * 132, NODE_WIDTH, NODE_HEIGHT, label)
        )
    positions = {item.node.id: item for item in nodes}
    edges: list[PositionedEdge] = []
    for index, edge in enumerate(graph.edges):
        source, target = positions[edge.source], positions[edge.target]
        points = route_via_horizontal_lane(
            (source.x + source.width, source.y + source.height // 2),
            (target.x, target.y + target.height // 2),
            plan.y(str(index)),
        )
        label_x, label_y = lane_label_position(points)
        edges.append(PositionedEdge(edge, svg_path(points), label_x, label_y, points))
    return RouteGraphLayout(
        tuple(nodes),
        tuple(edges),
        max((n.x + n.width + 30 for n in nodes), default=320),
        max((n.y + n.height + 30 for n in nodes), default=160),
    )
