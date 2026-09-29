"""Disposition horizontale pure du flux runtime connu."""

from dataclasses import dataclass

from forge_design.tools.debug_flow import DebugFlow, DebugFlowEdge, DebugFlowNode


@dataclass(frozen=True)
class PositionedDebugNode:
    node: DebugFlowNode
    x: int
    y: int
    width: int
    height: int
    detail: str


@dataclass(frozen=True)
class PositionedDebugEdge:
    edge: DebugFlowEdge
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class DebugFlowLayout:
    nodes: tuple[PositionedDebugNode, ...]
    edges: tuple[PositionedDebugEdge, ...]
    width: int
    height: int


def layout_debug_flow(flow: DebugFlow) -> DebugFlowLayout:
    nodes = tuple(
        PositionedDebugNode(
            node,
            20 + index * 300,
            20,
            220,
            90,
            (
                (node.detail or "")[:23] + "…"
                if len(node.detail or "") > 24
                else node.detail or ""
            ),
        )
        for index, node in enumerate(flow.nodes)
    )
    by_id = {item.node.id: item for item in nodes}
    edges: list[PositionedDebugEdge] = []
    for edge in flow.edges:
        source, target = by_id[edge.source], by_id[edge.target]
        edges.append(
            PositionedDebugEdge(
                edge,
                source.x + source.width,
                source.y + source.height // 2,
                target.x,
                target.y + target.height // 2,
            )
        )
    return DebugFlowLayout(
        nodes, tuple(edges), nodes[-1].x + nodes[-1].width + 20 if nodes else 40, 130
    )
