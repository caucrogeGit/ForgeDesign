"""Adaptateur Route Explorer → GraphicScene : projection pure et transport sûr."""

import json
from typing import Any

import pytest

from forge_design.tools.route_graph import GraphEdge, GraphNode, RouteGraph
from forge_design.web.graphics import scene_json_payload
from forge_design.web.route_graph_layout import layout_route_graph
from forge_design.web.route_graph_scene import build_route_graphic_scene


def _graph() -> RouteGraph:
    route = json.dumps(("route", "GET", "/"))
    handler = json.dumps(("handler", "HomeController.index"))
    controller = json.dumps(("controller", "mvc/controllers/home.py"))
    template = json.dumps(("template", "home.html"))
    hostile = json.dumps(("template", "</script><script>alert(1)</script>"))
    return RouteGraph(
        (
            GraphNode(route, "route", "GET /"),
            GraphNode(handler, "handler", "HomeController.index"),
            GraphNode(controller, "controller", "mvc/controllers/home.py"),
            GraphNode(template, "template", "home.html", "present"),
            GraphNode(
                hostile, "template", "</script><script>alert(1)</script>", "missing"
            ),
        ),
        (
            GraphEdge(route, handler, "handles"),
            GraphEdge(handler, controller, "defined-in"),
            GraphEdge(handler, template, "renders"),
            GraphEdge(template, hostile, "includes", in_cycle=True),
        ),
    )


def _scene() -> dict[str, Any]:
    return build_route_graphic_scene(layout_route_graph(_graph()))


def test_nodes_reuse_route_graph_identities() -> None:
    graph = _graph()
    scene = _scene()
    assert [node["id"] for node in scene["nodes"]] == [n.id for n in graph.nodes]
    first = scene["nodes"][0]
    assert first["label"] == "GET /"
    assert first["lines"] == ["Route", "GET /", "—"]
    assert first["presentation"] == {"variant": "category-1", "tone": "default"}
    assert first["data"] == {"kind-label": "Route", "presence-label": "—"}
    assert set(first["rect"]) == {"x", "y", "width", "height"}


def test_presentation_is_generic() -> None:
    variants = [node["presentation"]["variant"] for node in _scene()["nodes"]]
    assert variants == [
        "category-1",
        "category-2",
        "category-3",
        "category-4",
        "category-4",
    ]
    missing = _scene()["nodes"][4]
    assert missing["presentation"]["tone"] == "warning"
    assert missing["lines"][2] == "Absent"  # le ton n'est jamais la seule information


def test_edges_are_unique_and_reference_nodes() -> None:
    scene = _scene()
    ids = {node["id"] for node in scene["nodes"]}
    edge_ids = [edge["id"] for edge in scene["edges"]]
    assert len(set(edge_ids)) == len(edge_ids) == 4
    for edge in scene["edges"]:
        assert edge["source"] in ids and edge["target"] in ids
        assert json.loads(edge["id"]) == [
            edge["source"],
            edge["target"],
            edge["label"].split()[0],
        ]
        assert len(edge["points"]) == 6 and edge["presentation"]["arrow"] == "end"
    cycle = scene["edges"][3]
    assert cycle["label"] == "includes (cycle)"
    assert cycle["presentation"]["line"] == "dashed"


def test_points_match_server_fallback_path() -> None:
    layout = layout_route_graph(_graph())
    for item in layout.edges:
        (sx, sy), (hx, _), (_, lane), (bx, _), (_, ty), (tx, _) = item.points
        assert item.path == f"M {sx} {sy} H {hx} V {lane} H {bx} V {ty} H {tx}"


def test_projection_is_pure() -> None:
    assert _scene() == _scene()
    assert json.dumps(_scene(), sort_keys=True)


@pytest.mark.parametrize("character", ["<", ">", "&", " ", " "])
def test_payload_cannot_close_script(character: str) -> None:
    scene = _scene()
    scene["nodes"][0]["label"] = f"a{character}b</script><!--"
    payload = str(scene_json_payload(scene))
    for raw in ("<", ">", "&", " ", " "):
        assert raw not in payload
    assert json.loads(payload) == scene
