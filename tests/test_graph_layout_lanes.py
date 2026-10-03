"""Route et Entity Explorer routent par la même allocation de couloirs."""

import ast
import itertools
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from test_entity_graph import entity, relation

from forge_design.forge.entities import EntitiesResult
from forge_design.graphics.lanes import DEFAULT_LANE_GAP, DEFAULT_LANE_SPACING
from forge_design.tools.entity_graph import build_entity_graph
from forge_design.tools.route_graph import GraphEdge, GraphNode, RouteGraph
from forge_design.web.entity_graph_layout import layout_entity_graph
from forge_design.web.route_graph_layout import layout_route_graph

ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = ("route_graph_layout.py", "entity_graph_layout.py")

Points = tuple[tuple[int, int], ...]


def route_witness() -> RouteGraph:
    """Huit arêtes, deux couloirs : chevauchement maximal 2."""
    nodes = (
        GraphNode("r1", "route", "GET /a"),
        GraphNode("r2", "route", "GET /b"),
        GraphNode("h1", "handler", "A.a"),
        GraphNode("h2", "handler", "A.b"),
        GraphNode("c", "controller", "mvc/controllers/a.py"),
        GraphNode("t", "template", "page.html"),
        GraphNode("d1", "template", "one.html"),
        GraphNode("d2", "template", "two.html"),
        GraphNode("e1", "template", "deep1.html"),
        GraphNode("e2", "template", "deep2.html"),
    )
    edges = (
        GraphEdge("r1", "h1", "handles"),
        GraphEdge("r2", "h2", "handles"),
        GraphEdge("h1", "c", "defined-in"),
        GraphEdge("h2", "t", "renders"),
        GraphEdge("t", "d1", "includes"),
        GraphEdge("t", "d2", "includes"),
        GraphEdge("d1", "e1", "includes"),
        GraphEdge("d2", "e2", "includes"),
    )
    return RouteGraph(nodes, edges)


def lane_of(points: Points) -> int:
    return points[2][1]


def check_lanes(edges: Sequence[Points], label_at: Sequence[tuple[int, int]]) -> int:
    """Invariants communs ; renvoie le nombre de couloirs utilisés."""
    lanes = sorted({lane_of(points) for points in edges})
    for points, (label_x, label_y) in zip(edges, label_at, strict=True):
        assert len(points) == 6
        for a, b in itertools.pairwise(points):
            assert a[0] == b[0] or a[1] == b[1]
        # Libellé au milieu du segment de son propre couloir.
        assert label_y == lane_of(points) - 5
        assert label_x == (points[2][0] + points[3][0]) // 2
    for a, b in itertools.combinations(edges, 2):
        if lane_of(a) == lane_of(b):
            (al, ar), (bl, br) = sorted((a[2][0], a[3][0])), sorted((b[2][0], b[3][0]))
            assert ar + DEFAULT_LANE_GAP <= bl or br + DEFAULT_LANE_GAP <= al
    assert all(
        later - earlier == DEFAULT_LANE_SPACING
        for earlier, later in itertools.pairwise(lanes)
    )
    return len(lanes)


def test_route_eight_edges_share_two_lanes() -> None:
    graph = route_witness()
    layout = layout_route_graph(graph)
    count = check_lanes(
        [e.points for e in layout.edges], [(e.label_x, e.label_y) for e in layout.edges]
    )
    assert count == 2
    # Le haut dépend du nombre de couloirs, pas du nombre d'arêtes.
    assert min(n.y for n in layout.nodes) == 30 + 2 * DEFAULT_LANE_SPACING + 30
    assert layout.height < 60 + 24 * len(graph.edges) + 100 + 30
    # Topologie et identités inchangées.
    assert tuple(e.edge for e in layout.edges) == graph.edges
    assert tuple(n.node for n in layout.nodes) == graph.nodes
    assert layout == layout_route_graph(graph)


def test_route_parallel_edges_keep_distinct_lanes() -> None:
    graph = RouteGraph(
        (GraphNode("r", "route", "GET /"), GraphNode("h", "handler", "A.a")),
        (GraphEdge("r", "h", "handles"),) * 3,
    )
    layout = layout_route_graph(graph)
    count = check_lanes(
        [e.points for e in layout.edges], [(e.label_x, e.label_y) for e in layout.edges]
    )
    assert count == 3 and len({e.path for e in layout.edges}) == 3


@pytest.mark.parametrize("count", [1, 2, 5])
def test_entity_lanes_parallels_and_cycles(count: int) -> None:
    graph = build_entity_graph(
        EntitiesResult(
            tuple(entity(str(i)) for i in range(count)),
            relations=tuple(
                relation(str(i), str((i + 1) % count), many=many)
                for i in range(count)
                for many in (False, True)
            )
            + (relation("0", str(count - 1)),) * 2,
        )
    )
    layout = layout_entity_graph(graph)
    lanes = check_lanes(
        [e.points for e in layout.edges], [(e.label_x, e.label_y) for e in layout.edges]
    )
    # Deux colonnes : tous les parcours couvrent la gouttière, aucun partage possible.
    assert lanes == len(graph.edges)
    assert min(n.y for n in layout.nodes) == 30 + lanes * DEFAULT_LANE_SPACING + 30
    assert tuple(e.edge for e in layout.edges) == graph.edges
    assert layout == layout_entity_graph(graph)


def test_paths_are_the_svg_form_of_points() -> None:
    for layout in (
        layout_route_graph(route_witness()),
        layout_entity_graph(
            build_entity_graph(
                EntitiesResult(
                    (entity("A"), entity("B")),
                    relations=(relation("A", "B", many=True),),
                )
            )
        ),
    ):
        for item in layout.edges:
            (sx, sy), (hx, _), (_, lane), (bx, _), (_, ty), (tx, _) = item.points
            assert item.path == f"M {sx} {sy} H {hx} V {lane} H {bx} V {ty} H {tx}"


def _source(name: str) -> str:
    return (ROOT / "forge_design/web" / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", LAYOUTS)
def test_layouts_use_the_shared_primitive(name: str) -> None:
    tree = ast.parse(_source(name))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "forge_design.graphics.lanes"
        for alias in node.names
    }
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    required = {
        "allocate_horizontal_lanes",
        "route_via_horizontal_lane",
        "lane_label_position",
        "svg_path",
    }
    assert required <= imported and required <= called
    # Plus de couloir par indice d'arête ni de hauteur proportionnelle aux arêtes.
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            operands = {ast.unparse(node.left), ast.unparse(node.right)}
            assert "index" not in operands, ast.unparse(node)
            assert not any("graph.edges" in text for text in operands), ast.unparse(
                node
            )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not node.value.startswith("M "), "chemin SVG fabriqué localement"


def test_single_lane_allocator_in_the_code_base() -> None:
    """Une seule copie : aucun autre module ne réimplémente la partition."""
    owners: list[str] = []
    for path in sorted((ROOT / "forge_design").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.ClassDef)
        }
        if names & {
            "allocate_horizontal_lanes",
            "route_via_horizontal_lane",
            "svg_path",
        }:
            owners.append(path.relative_to(ROOT).as_posix())
        if "heapq" in text and "lane" in text:
            assert path.name == "lanes.py", path
    assert owners == ["forge_design/graphics/lanes.py"]


DETERMINISM = """
import json, sys
sys.path.insert(0, sys.argv[1])
from test_graph_layout_lanes import route_witness
from test_entity_graph import entity, relation
from forge_design.forge.entities import EntitiesResult
from forge_design.tools.entity_graph import build_entity_graph
from forge_design.web.entity_graph_layout import layout_entity_graph
from forge_design.web.route_graph_layout import layout_route_graph
entities = build_entity_graph(EntitiesResult(
    (entity("A"), entity("B")),
    relations=(relation("A", "B"), relation("A", "B"), relation("B", "A", many=True)),
))
layouts = (layout_route_graph(route_witness()), layout_entity_graph(entities))
edges = [[(e.points, e.path, e.label_x, e.label_y) for e in l.edges] for l in layouts]
print(json.dumps(edges))
"""


def test_byte_identical_across_processes_and_hash_seeds() -> None:
    outputs = {
        subprocess.run(
            [sys.executable, "-c", DETERMINISM, str(ROOT / "tests")],
            capture_output=True,
            check=True,
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            text=True,
        ).stdout
        for seed in ("1", "2", "3")
    }
    assert len(outputs) == 1 and next(iter(outputs)).startswith("[[")
