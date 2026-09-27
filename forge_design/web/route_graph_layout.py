"""Placement pur et déterministe du graphe, sans découverte de relations."""

from collections import deque
from dataclasses import dataclass

from forge_design.tools.route_graph import GraphEdge, GraphNode, RouteGraph


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
    nodes: list[PositionedNode] = []
    top = 60 + 24 * len(graph.edges)
    for node in graph.nodes:
        column = (
            levels.get(node.id, 4) if node.kind == "template" else columns[node.kind]
        )
        row = counts.get(column, 0)
        label = node.label if len(node.label) <= 30 else node.label[:29] + "…"
        nodes.append(
            PositionedNode(node, 30 + column * 360, top + row * 132, 260, 100, label)
        )
        counts[column] = row + 1
    positions = {item.node.id: item for item in nodes}
    edges: list[PositionedEdge] = []
    for index, edge in enumerate(graph.edges):
        source, target = positions[edge.source], positions[edge.target]
        sx, sy = source.x + source.width, source.y + source.height // 2
        tx, ty = target.x, target.y + target.height // 2
        lane = 30 + index * 24
        path = f"M {sx} {sy} H {sx + 20} V {lane} H {tx - 20} V {ty} H {tx}"
        edges.append(PositionedEdge(edge, path, (sx + tx) // 2, lane - 5))
    return RouteGraphLayout(
        tuple(nodes),
        tuple(edges),
        max((n.x + n.width + 30 for n in nodes), default=320),
        max((n.y + n.height + 30 for n in nodes), default=160),
    )
