"""Placement borné par la taille du graphe, indépendant de sa topologie."""

from dataclasses import dataclass

from forge_design.tools.entity_graph import (
    EntityGraph,
    EntityGraphEdge,
    EntityGraphNode,
)


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
    # Polyligne orthogonale dont path est la forme SVG (repli serveur).
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
    """Deux colonnes et un couloir supérieur par arête, cycles compris.

    Le contrat d'entrée exige des IDs uniques et des extrémités présentes.
    Les trajets peuvent partager leurs segments verticaux, pas leurs couloirs.
    """
    counts = {"entity": 0, "pivot": 0}
    nodes: list[PositionedEntityNode] = []
    top = 60 + 26 * len(graph.edges)
    for node in graph.nodes:
        pivot = node.kind == "pivot"
        nodes.append(
            PositionedEntityNode(
                node,
                480 if pivot else 40,
                top + counts[node.kind] * 140,
                260,
                100,
                _short(node.label),
                _short(node.table),
            )
        )
        counts[node.kind] += 1
    positions = {item.node.id: item for item in nodes}
    edges: list[PositionedEntityEdge] = []
    for index, edge in enumerate(graph.edges):
        source, target = positions[edge.source], positions[edge.target]
        sx, sy = source.x + source.width, source.y + source.height // 2
        tx, ty = target.x, target.y + target.height // 2
        lane = 30 + index * 26
        points = (
            (sx, sy),
            (sx + 20, sy),
            (sx + 20, lane),
            (tx - 20, lane),
            (tx - 20, ty),
            (tx, ty),
        )
        path = f"M {sx} {sy} H {sx + 20} V {lane} H {tx - 20} V {ty} H {tx}"
        edges.append(
            PositionedEntityEdge(
                edge, path, (sx + tx) // 2, lane - 5, _short(edge.label), points
            )
        )
    return EntityGraphLayout(
        tuple(nodes),
        tuple(edges),
        max((n.x + n.width + 40 for n in nodes), default=340),
        max((n.y + n.height + 40 for n in nodes), default=160),
    )
