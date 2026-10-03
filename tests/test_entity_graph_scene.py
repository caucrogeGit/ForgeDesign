"""Adaptateur Entity Explorer → GraphicScene : projection pure et déterministe."""

import builtins
import json
from pathlib import Path
from typing import Any

import pytest

from forge_design.tools.entity_graph import (
    EntityGraph,
    EntityGraphEdge,
    EntityGraphNode,
)
from forge_design.web.entity_graph_layout import layout_entity_graph
from forge_design.web.entity_graph_scene import build_entity_graphic_scene
from forge_design.web.graphics import scene_json_payload

HOSTILE = "</script><svg onload=alert(1)>"


def _graph() -> EntityGraph:
    nodes = (
        EntityGraphNode("entity:0", "entity", "Article", "articles", 4),
        EntityGraphNode("entity:1", "entity", "Ünïcödé Ω", "auteurs", 2),
        EntityGraphNode("entity:2", "entity", HOSTILE, HOSTILE, 1),
        EntityGraphNode("pivot:3", "pivot", "article_tag", "article_tag", 1),
    )
    edges = (
        EntityGraphEdge("relation:0", "entity:0", "entity:1", "many_to_one", "auteur"),
        # Relation parallèle : même source, même cible, identité distincte.
        EntityGraphEdge(
            "relation:1", "entity:0", "entity:1", "many_to_one", "relecteur"
        ),
        EntityGraphEdge(
            "relation:3:from", "entity:0", "pivot:3", "many_to_many_from", HOSTILE
        ),
        EntityGraphEdge("relation:3:to", "pivot:3", "entity:2", "many_to_many_to", ""),
    )
    return EntityGraph(nodes, edges)


def _scene() -> dict[str, Any]:
    return build_entity_graphic_scene(layout_entity_graph(_graph()))


def test_single_entity() -> None:
    graph = EntityGraph((EntityGraphNode("entity:0", "entity", "Solo", "solo", 0),))
    scene = build_entity_graphic_scene(layout_entity_graph(graph))
    assert [node["id"] for node in scene["nodes"]] == ["entity:0"]
    assert scene["edges"] == []
    assert scene["nodes"][0]["lines"] == ["Entité — 0 champs", "Solo", "solo"]


def test_nodes_reuse_entity_graph_identities() -> None:
    scene = _scene()
    assert [node["id"] for node in scene["nodes"]] == [n.id for n in _graph().nodes]
    article = scene["nodes"][0]
    assert article["label"] == "Entité Article"
    assert article["presentation"] == {"variant": "category-1"}
    assert article["data"] == {
        "kind-label": "Entité",
        "name": "Article",
        "table": "articles",
        "field-count": "4",
        "field-label": "Champs",
    }


def test_pivot_is_an_ordinary_node() -> None:
    pivot = _scene()["nodes"][3]
    assert pivot["label"] == "Pivot article_tag"
    assert pivot["presentation"] == {"variant": "category-2"}
    assert pivot["lines"] == ["Pivot — 1 champs", "article_tag"]
    assert pivot["data"]["field-label"] == "Champs supplémentaires"


def test_edges_keep_identities_and_parallel_relations() -> None:
    scene = _scene()
    ids = [edge["id"] for edge in scene["edges"]]
    assert ids == ["relation:0", "relation:1", "relation:3:from", "relation:3:to"]
    assert len(set(ids)) == len(ids)
    first, second = scene["edges"][:2]
    assert (first["source"], first["target"]) == (second["source"], second["target"])
    assert first["data"] == {"kind": "many_to_one", "name": "auteur"}
    assert second["label"] == "relecteur" and "labelAt" in second
    assert "label" not in scene["edges"][3] and "labelAt" not in scene["edges"][3]
    node_ids = {node["id"] for node in scene["nodes"]}
    for edge in scene["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids
        assert len(edge["points"]) == 6 and edge["presentation"] == {"arrow": "end"}


def test_points_match_server_fallback_path() -> None:
    for item in layout_entity_graph(_graph()).edges:
        (sx, sy), (hx, _), (_, lane), (bx, _), (_, ty), (tx, _) = item.points
        assert item.path == f"M {sx} {sy} H {hx} V {lane} H {bx} V {ty} H {tx}"


def test_unicode_and_hostile_text_stay_text() -> None:
    scene = _scene()
    assert scene["nodes"][1]["data"]["name"] == "Ünïcödé Ω"
    payload = str(scene_json_payload(scene))
    for raw in ("<", ">", "&"):
        assert raw not in payload
    assert json.loads(payload) == scene
    assert json.loads(payload)["nodes"][2]["data"]["table"] == HOSTILE


def test_projection_is_deterministic() -> None:
    assert _scene() == _scene()
    assert str(scene_json_payload(_scene())) == str(scene_json_payload(_scene()))


def test_projection_never_touches_the_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = layout_entity_graph(_graph())

    def forbidden(*args: object, **kwargs: object) -> Any:
        raise AssertionError("accès au système de fichiers")

    error: str | None = None
    # Remplacements limités à l'appel : pytest retrouve Path pour son rapport.
    with monkeypatch.context() as patched:
        for name in ("open", "exists", "read_text", "read_bytes", "iterdir", "stat"):
            patched.setattr(Path, name, forbidden)
        patched.setattr(builtins, "open", forbidden)
        try:
            build_entity_graphic_scene(layout)
        except AssertionError as exc:
            error = str(exc)
    assert error is None, error
