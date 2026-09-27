"""Placement fini, y compris en présence de boucles et relations parallèles."""

import re

import pytest
from test_entity_graph import entity, relation

from forge_design.forge.entities import EntitiesResult
from forge_design.tools.entity_graph import EntityGraph, build_entity_graph
from forge_design.web.entity_graph_layout import EntityGraphLayout, layout_entity_graph


def check_bounds(layout: EntityGraphLayout) -> None:
    assert layout.width > 0 and layout.height > 0
    for i, node in enumerate(layout.nodes):
        assert 0 <= node.x < node.x + node.width <= layout.width
        assert 0 <= node.y < node.y + node.height <= layout.height
        for other in layout.nodes[i + 1 :]:
            assert (
                node.x + node.width <= other.x
                or other.x + other.width <= node.x
                or node.y + node.height <= other.y
                or other.y + other.height <= node.y
            )
    for edge in layout.edges:
        assert 0 < edge.label_x < layout.width and 0 < edge.label_y < layout.height
        # Ce layout utilise exclusivement M x y, H x et V y.
        for command, first, second in re.findall(
            r"([MHV]) (\d+)(?: (\d+))?", edge.path
        ):
            if command == "M":
                assert (
                    0 <= int(first) <= layout.width
                    and 0 <= int(second) <= layout.height
                )
            else:
                assert (
                    0
                    <= int(first)
                    <= (layout.width if command == "H" else layout.height)
                )


def test_empty_and_long_isolated() -> None:
    check_bounds(layout_entity_graph(EntityGraph()))
    graph = build_entity_graph(EntitiesResult((entity("x" * 200),)))
    layout = layout_entity_graph(graph)
    check_bounds(layout)
    assert layout.nodes[0].label == "x" * 29 + "…"
    assert layout.nodes[0].node.label == "x" * 200 and layout.edges == ()


@pytest.mark.parametrize("count", [1, 2, 3, 30])
def test_cycles_parallels_and_pivots(count: int) -> None:
    graph = build_entity_graph(
        EntitiesResult(
            tuple(entity(str(i)) for i in range(count)),
            relations=tuple(
                relation(str(i), str((i + 1) % count), many=many)
                for i in range(count)
                for many in (False, True)
            ),
        )
    )
    layout = layout_entity_graph(graph)
    check_bounds(layout)
    assert layout == layout_entity_graph(graph)
    assert len(layout.nodes) == count * 2 and len(layout.edges) == count * 3
    assert len({e.path for e in layout.edges}) == len(graph.edges)
    assert tuple(n.node for n in layout.nodes) == graph.nodes
    if count == 1:
        assert graph.edges[0].source == graph.edges[0].target
        assert " H " in layout.edges[0].path and " V " in layout.edges[0].path


def test_identical_parallel_edges_keep_distinct_lanes() -> None:
    graph = build_entity_graph(
        EntitiesResult((entity("A"), entity("B")), relations=(relation("A", "B"),) * 3)
    )
    layout = layout_entity_graph(graph)
    check_bounds(layout)
    assert len({e.path for e in layout.edges}) == 3
    assert len({e.label_y for e in layout.edges}) == 3
