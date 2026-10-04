"""Adaptateur Debug Center → GraphicScene : projection pure du DebugFlowLayout."""

import ast
import builtins
import inspect
import json
import os
import shutil
import subprocess
from dataclasses import replace
from itertools import combinations
from pathlib import Path
from typing import Any

import pytest
from test_debug_filters import sample

from forge_design.forge.debug_errors import DebugError, DebugFrame, DebugRequest
from forge_design.tools.debug_flow import build_debug_flow
from forge_design.web import debug_flow_scene
from forge_design.web.debug_flow_layout import layout_debug_flow
from forge_design.web.debug_flow_scene import (
    MAX_ACCESSIBLE_LABEL,
    build_debug_graphic_scene,
)
from forge_design.web.graphics import scene_json_payload

ROOT = Path(__file__).resolve().parents[1]
HOSTILE = "</text><script>alert(1)</script>"
FIELDS = ("request", "route", "controller", "sql", "template")


def event(*fields: str, value: str = "valeur", **extra: Any) -> DebugError:
    values: dict[str, Any] = {key: value for key in fields if key != "request"}
    if "request" in fields:
        values["request"] = DebugRequest(method="POST", path="/" + value)
    return replace(sample(), **values, **extra)


def scene_of(item: DebugError) -> dict[str, Any]:
    return build_debug_graphic_scene(layout_debug_flow(build_debug_flow(item)))


def test_nominal_ids_order_endpoints_positions_and_size() -> None:
    layout = layout_debug_flow(build_debug_flow(event(*FIELDS)))
    scene = build_debug_graphic_scene(layout)
    assert [n["id"] for n in scene["nodes"]] == [
        "debug-node-request",
        "debug-node-router",
        "debug-node-controller",
        "debug-node-sql",
        "debug-node-template",
    ]
    assert [n["rect"] for n in scene["nodes"]] == [
        {"x": n.x, "y": n.y, "width": n.width, "height": n.height} for n in layout.nodes
    ]
    assert (scene["width"], scene["height"]) == (layout.width, layout.height)
    assert [(e["source"], e["target"]) for e in scene["edges"]] == [
        (e.edge.source, e.edge.target) for e in layout.edges
    ]
    assert [e["points"] for e in scene["edges"]] == [
        [{"x": e.x1, "y": e.y1}, {"x": e.x2, "y": e.y2}] for e in layout.edges
    ]
    assert all(e["presentation"] == {"arrow": "end"} for e in scene["edges"])
    assert [n["presentation"]["variant"] for n in scene["nodes"]] == [
        "category-1",
        "category-2",
        "category-3",
        "category-4",
        "category-5",
    ]
    first = scene["nodes"][0]
    assert first["lines"] == ["Requête", "POST /valeur"]
    assert first["label"] == "Requête — POST /valeur"
    assert first["levels"] == {"overview": [], "normal": [0]}
    assert "data" not in first
    assert "trace d'exécution" in scene["description"]


def test_edge_ids_are_deterministic_and_unique() -> None:
    scene = scene_of(event(*FIELDS))
    ids = [e["id"] for e in scene["edges"]]
    assert ids[0] == '["debug-flow","debug-node-request","debug-node-router"]'
    assert len(set(ids)) == len(ids) == 4
    assert scene == scene_of(event(*FIELDS))
    assert scene_json_payload(scene) == scene_json_payload(scene_of(event(*FIELDS)))


@pytest.mark.parametrize(
    "fields",
    [c for size in range(1, 6) for c in combinations(FIELDS, size)],
)
def test_partial_flows_are_valid_without_request(fields: tuple[str, ...]) -> None:
    scene = scene_of(event(*fields))
    kinds = [n["id"].removeprefix("debug-node-") for n in scene["nodes"]]
    expected = [
        {"route": "router"}.get(field, field) for field in FIELDS if field in fields
    ]
    assert kinds == expected
    assert len(scene["edges"]) == len(kinds) - 1
    for edge, (left, right) in zip(scene["edges"], zip(kinds, kinds[1:])):
        assert (edge["source"], edge["target"]) == (
            f"debug-node-{left}",
            f"debug-node-{right}",
        )


def test_empty_flow_has_no_nodes() -> None:
    scene = scene_of(event())
    assert scene["nodes"] == [] and scene["edges"] == []


def test_sql_is_never_transported_and_no_inference() -> None:
    query = "SELECT password FROM users WHERE token = 'very-secret'"
    item = event(
        "controller",
        sql=query,
        traceback=(DebugFrame("mvc/models/user.py", 3, "save"),),
        message="controller Home.index failed in model User",
    )
    text = json.dumps(scene_of(item), ensure_ascii=False)
    assert "Requête disponible" in text
    assert "SELECT" not in text and "very-secret" not in text
    assert "mvc/models" not in text and "Home.index" not in text
    assert "debug-node-model" not in text and "debug-node-response" not in text


def test_hostile_values_stay_text_and_cannot_close_the_script() -> None:
    scene = scene_of(event(*FIELDS, value=HOSTILE))
    assert any(HOSTILE in n["label"] for n in scene["nodes"])
    payload = str(scene_json_payload(scene))
    assert "<" not in payload and ">" not in payload
    assert json.loads(payload) == scene


def test_long_values_truncated_visually_and_accessibly() -> None:
    long = "x" * 70_000
    scene = scene_of(event("controller", value=long))
    node = scene["nodes"][0]
    assert len(node["label"]) == MAX_ACCESSIBLE_LABEL and node["label"].endswith("…")
    assert node["lines"] == ["Contrôleur", "x" * 23 + "…"]


def test_adapter_receives_only_the_layout() -> None:
    """DebugFlow reste l'autorité : l'adaptateur ne relit jamais DebugError."""
    source = Path(inspect.getfile(debug_flow_scene)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "DebugError" not in imported and "build_debug_flow" not in imported
    assert "debug_errors" not in source and "traceback" not in source
    signature = inspect.signature(build_debug_graphic_scene)
    assert list(signature.parameters) == ["layout"]
    assert signature.parameters["layout"].annotation.__name__ == "DebugFlowLayout"


def test_projection_touches_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    layout = layout_debug_flow(build_debug_flow(event(*FIELDS)))

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("accès interdit")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(os, "stat", forbidden)
        guard.setattr(Path, "read_text", forbidden)
        assert build_debug_graphic_scene(layout)["nodes"]


def test_scene_passes_engine_validation(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node indisponible.")
    payload = tmp_path / "scene.json"
    payload.write_text(json.dumps(scene_of(event(*FIELDS, value=HOSTILE))))
    model = (ROOT / "forge_design/web/static/graphics/model.js").as_uri()
    script = (
        f'import {{ validateScene }} from "{model}";'
        'import { readFileSync } from "node:fs";'
        "const s = validateScene(JSON.parse(readFileSync(process.argv[1], 'utf8')));"
        "const n = s.nodes;"
        "console.log(JSON.stringify([n.length, s.edges.length, n[4].levels]));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, str(payload)],
        capture_output=True,
        check=True,
        text=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == [
        5,
        4,
        {"overview": [], "normal": [0], "detail": [0, 1]},
    ]
