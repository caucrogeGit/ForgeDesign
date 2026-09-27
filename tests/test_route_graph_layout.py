"""Placement sans accès au projet, y compris pour les nœuds partagés."""

import ast
import builtins
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from jinja2 import Environment

from forge_design.forge import routes as bridge
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.route_graph import GraphEdge, GraphNode, RouteGraph
from forge_design.web.route_graph_layout import layout_route_graph


@pytest.mark.parametrize("count", [0, 1, 2])
def test_empty_and_routes(count: int) -> None:
    graph = RouteGraph(
        tuple(GraphNode(str(i), "route", "GET /") for i in range(count)), ()
    )
    layout = layout_route_graph(graph)
    assert layout.width > 0 and layout.height > 0
    assert [n.node for n in layout.nodes] == list(graph.nodes)
    assert all(n.x == 30 for n in layout.nodes)
    if count == 2:
        assert layout.nodes[1].y >= layout.nodes[0].y + layout.nodes[0].height
    assert layout == layout_route_graph(graph)


def test_shared_graph_columns_edges_and_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = RouteGraph(
        (
            GraphNode("r1", "route", "GET /"),
            GraphNode("r2", "route", "POST /"),
            GraphNode("h", "handler", "Contact.list"),
            GraphNode("h2", "handler", "Contact.post"),
            GraphNode("c", "controller", "mvc/controllers/contact.py"),
            GraphNode("t", "template", "page.html"),
            GraphNode("d1", "template", "base.html", "missing"),
            GraphNode("d2", "template", "x" * 100),
        ),
        (
            GraphEdge("r1", "h", "handles"),
            GraphEdge("r2", "h", "handles"),
            GraphEdge("h", "c", "defined-in"),
            GraphEdge("h2", "c", "defined-in"),
            GraphEdge("h", "t", "renders"),
            GraphEdge("h2", "t", "renders"),
            GraphEdge("t", "d1", "extends"),
            GraphEdge("t", "d2", "includes"),
        ),
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Accès interdit pendant le layout")

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "lstat")),
            (Path, ("open", "stat", "lstat")),
            (ast, ("parse",)),
            (Environment, ("parse",)),
            (bridge, ("read_routes",)),
            (ToolRegistry, ("get", "list")),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        layout = layout_route_graph(graph)
        assert layout == layout_route_graph(graph)
    assert tuple(n.node for n in layout.nodes) == graph.nodes
    assert tuple(e.edge for e in layout.edges) == graph.edges
    assert [n.x for n in layout.nodes] == [30, 30, 390, 390, 750, 1110, 1470, 1470]
    assert len(layout.nodes) == 8 and len(layout.edges) == 8
    assert layout.nodes[-1].label == "x" * 29 + "…"
    assert layout.nodes[-1].node.label == "x" * 100
    for i, node in enumerate(layout.nodes):
        assert node.x + node.width <= layout.width
        assert node.y + node.height <= layout.height
        for other in layout.nodes[i + 1 :]:
            assert (
                node.x + node.width <= other.x
                or other.x + other.width <= node.x
                or node.y + node.height <= other.y
                or other.y + other.height <= node.y
            )
    with pytest.raises(FrozenInstanceError):
        setattr(layout.nodes[0], "x", 0)


def test_template_with_both_roles_and_partial_chain() -> None:
    graph = RouteGraph(
        (
            GraphNode("h", "handler", "handler"),
            GraphNode("t", "template", "a"),
            GraphNode("b", "template", "b"),
        ),
        (
            GraphEdge("h", "t", "renders"),
            GraphEdge("t", "b", "includes"),
            GraphEdge("h", "b", "renders"),
        ),
    )
    layout = layout_route_graph(graph)
    assert [n.x for n in layout.nodes] == [390, 1110, 1110]
    assert len(layout.edges) == 3


@pytest.mark.parametrize("count", [10, 20, 100])
def test_representative_size_shared_templates(count: int) -> None:
    graph = RouteGraph(
        tuple(GraphNode(f"r{i}", "route", f"GET /route/{i}") for i in range(count))
        + (
            GraphNode("h", "handler", "Contact.list"),
            GraphNode("c", "controller", "mvc/controllers/contact.py"),
        )
        + tuple(GraphNode(f"t{i}", "template", f"page{i}.html") for i in range(8)),
        tuple(GraphEdge(f"r{i}", "h", "handles") for i in range(count))
        + (GraphEdge("h", "c", "defined-in"), GraphEdge("h", "t0", "renders"))
        + tuple(GraphEdge(f"t{i}", f"t{i + 1}", "includes") for i in range(7))
        + (GraphEdge("t7", "t0", "includes", in_cycle=True),),
    )
    layout = layout_route_graph(graph)
    assert layout == layout_route_graph(graph)
    assert 0 < layout.width < 5000 and 0 < layout.height < 20000
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
