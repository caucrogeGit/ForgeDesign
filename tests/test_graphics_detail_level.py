"""Niveau de détail : contenus déclarés par les adaptateurs, politique au moteur."""

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from forge_design.tools.entity_graph import (
    EntityGraph,
    EntityGraphEdge,
    EntityGraphNode,
)
from forge_design.tools.route_graph import GraphEdge, GraphNode, RouteGraph
from forge_design.web.entity_graph_layout import layout_entity_graph
from forge_design.web.entity_graph_scene import build_entity_graphic_scene
from forge_design.web.route_graph_layout import layout_route_graph
from forge_design.web.route_graph_scene import build_route_graphic_scene

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "forge_design/web/static"
LONG = "x" * 40


def route_scene() -> dict[str, Any]:
    graph = RouteGraph(
        (
            GraphNode("r", "route", "GET /"),
            GraphNode("h", "handler", "Home.index"),
            GraphNode("t", "template", LONG, "missing"),
        ),
        (GraphEdge("r", "h", "handles"), GraphEdge("h", "t", "renders")),
    )
    return build_route_graphic_scene(layout_route_graph(graph))


def entity_scene() -> dict[str, Any]:
    graph = EntityGraph(
        (
            EntityGraphNode("entity:0", "entity", "Article", "articles", 2),
            EntityGraphNode("entity:1", "entity", LONG, "long", 1),
            EntityGraphNode("pivot:2", "pivot", "article_tag", "article_tag", 1),
        ),
        (EntityGraphEdge("relation:0", "entity:0", "entity:1", "many_to_one", "a"),),
    )
    return build_entity_graphic_scene(layout_entity_graph(graph))


def test_route_levels_are_declared_by_the_adapter() -> None:
    scene = route_scene()
    for node in scene["nodes"]:
        assert node["levels"] == {"overview": [], "normal": [0, 1]}
        kind, name, _presence = node["lines"]
        assert [node["lines"][i] for i in node["levels"]["normal"]] == [kind, name]
        # Le label accessible reste complet quel que soit le niveau visuel.
        assert node["label"]
    first, second = scene["nodes"][:2]
    assert first["levels"] is not second["levels"]
    assert first["levels"]["normal"] is not second["levels"]["normal"]


def test_entity_levels_are_declared_by_the_adapter() -> None:
    scene = entity_scene()
    for node in scene["nodes"]:
        assert node["levels"] == {"overview": [], "normal": [1]}
        assert node["lines"][1] == node["data"]["name"][:29] + (
            "…" if len(node["data"]["name"]) > 30 else node["data"]["name"][29:]
        )
        assert node["label"].endswith(node["data"]["name"])


def test_thresholds_are_runtime_only() -> None:
    for scene in (route_scene(), entity_scene()):
        text = json.dumps(scene)
        for word in ("threshold", "scale", "overviewBelow", "detailAbove"):
            assert word not in text, word


def test_css_hides_by_level_with_generic_classes() -> None:
    css = (STATIC / "shell.css").read_text(encoding="utf-8")
    rule = re.search(
        r"([^}]*)\{ display: none; \}",
        css[css.index("*/", css.index("FD-GRAPHICS-006")) + 2 :],
    )
    assert rule is not None
    selectors = {item.strip() for item in rule.group(1).split(",")}
    assert selectors == {
        ".gx-detail-overview .gx-node-text:not(.gx-at-overview)",
        ".gx-detail-normal .gx-node-text:not(.gx-at-normal)",
        ".gx-detail-overview .gx-edge-label",
    }
    for name in re.findall(r"\.gx-detail-[a-z-]+|\.gx-at-[a-z-]+", css):
        assert name.split("-")[-1] in {"overview", "normal", "detail"}, name
    # Aucune classe métier : le CSS ne connaît que des niveaux et catégories.
    for word in ("route", "entity", "pivot", "handler", "controller", "template"):
        assert not re.search(rf"\.gx-[a-z-]*{word}", css), word


def test_scene_text_size_matches_thresholds() -> None:
    css = (STATIC / "shell.css").read_text(encoding="utf-8")
    module = (STATIC / "graphics/detail-level.js").read_text(encoding="utf-8")
    assert "export const SCENE_TEXT_SIZE = 12;" in module
    assert ".gx-node-text { font: 12px monospace;" in css
    assert ".gx-edge-label { font: 12px sans-serif;" in css


@pytest.mark.parametrize("build", [route_scene, entity_scene], ids=["route", "entity"])
def test_real_scenes_pass_engine_validation(
    build: Callable[[], dict[str, Any]], tmp_path: Path
) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible.")
    scene = build()
    payload = tmp_path / "scene.json"
    payload.write_text(json.dumps(scene), encoding="utf-8")
    model = (STATIC / "graphics/model.js").as_uri()
    script = (
        f'import {{ validateScene }} from "{model}";'
        'import { readFileSync } from "node:fs";'
        "const s = validateScene(JSON.parse(readFileSync(process.argv[1], 'utf8')));"
        "console.log(JSON.stringify(s.nodes.map((n) => n.levels)));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, str(payload)],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    levels = json.loads(result.stdout)
    assert len(levels) == len(scene["nodes"])
    for item, source in zip(levels, scene["nodes"], strict=True):
        assert item["overview"] == []
        assert item["normal"] == source["levels"]["normal"]
        assert item["detail"] == list(range(len(source["lines"])))
