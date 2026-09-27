"""Placement pur et déterministe du graphe, sans découverte de relations."""

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
    """Colonnes fixes ; priorité principale pour les templates à double rôle.

    Chaque arête dispose d'un couloir horizontal au-dessus des nœuds. Aucun
    parcours transitif : seules les cibles de renders déterminent les principaux.
    """
    principals = {edge.target for edge in graph.edges if edge.kind == "renders"}
    columns = {"route": 0, "handler": 1, "controller": 2, "template": 4}
    counts = [0] * 5
    nodes: list[PositionedNode] = []
    top = 60 + 24 * len(graph.edges)
    for node in graph.nodes:
        column = (
            3
            if node.kind == "template" and node.id in principals
            else columns[node.kind]
        )
        label = node.label if len(node.label) <= 30 else node.label[:29] + "…"
        nodes.append(
            PositionedNode(
                node, 30 + column * 360, top + counts[column] * 132, 260, 100, label
            )
        )
        counts[column] += 1
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
