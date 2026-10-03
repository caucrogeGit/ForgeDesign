"""Allocation générique de couloirs : géométrie pure, déterministe, minimale."""

import ast
import itertools
import random
from pathlib import Path

import pytest

from forge_design.graphics import lanes
from forge_design.graphics.lanes import (
    HorizontalSpan,
    allocate_horizontal_lanes,
    lane_label_position,
    route_via_horizontal_lane,
    svg_path,
)

ROOT = Path(__file__).resolve().parents[1]
GAP = lanes.DEFAULT_LANE_GAP


def span(edge_id: str, start: int, end: int) -> HorizontalSpan:
    return HorizontalSpan(edge_id, start, end)


def max_overlap(spans: list[HorizontalSpan], gap: int = GAP) -> int:
    """Borne inférieure brute : parcours [gauche, droite + gap) couvrant un point."""
    best = 0
    for probe in spans:
        best = max(
            best,
            sum(1 for other in spans if other.left <= probe.left < other.right + gap),
        )
    return best


def check_plan(spans: list[HorizontalSpan], gap: int = GAP) -> None:
    plan = allocate_horizontal_lanes(spans, gap=gap)
    assert set(plan.indices) == {s.edge_id for s in spans}
    assert set(plan.indices.values()) == set(range(plan.count))
    assert plan.count == max_overlap(spans, gap)
    for a, b in itertools.combinations(spans, 2):
        if plan.indices[a.edge_id] == plan.indices[b.edge_id]:
            assert a.right + gap <= b.left or b.right + gap <= a.left


def test_empty_one_and_many() -> None:
    empty = allocate_horizontal_lanes([])
    assert empty.count == 0 and dict(empty.indices) == {}
    assert empty.band_bottom == lanes.DEFAULT_LANE_ORIGIN
    one = allocate_horizontal_lanes([span("a", 0, 100)])
    assert one.count == 1 and one.y("a") == lanes.DEFAULT_LANE_ORIGIN
    chain = [span(str(i), i * 200, i * 200 + 100) for i in range(500)]
    assert allocate_horizontal_lanes(chain).count == 1


def test_eight_edges_two_lanes_witness() -> None:
    spans = [
        span("r1", 310, 370),
        span("r2", 310, 370),
        span("h1", 670, 730),
        span("h2", 670, 1090),
        span("t1", 1390, 1450),
        span("t2", 1390, 1450),
        span("d1", 1750, 1810),
        span("d2", 1750, 1810),
    ]
    plan = allocate_horizontal_lanes(spans)
    assert plan.count == 2
    assert plan.band_bottom == 30 + 2 * 24
    check_plan(spans)


def test_touching_gap_and_nesting() -> None:
    # Bornes qui se touchent, ou séparées de moins que l'écart : couloirs distincts.
    assert (
        allocate_horizontal_lanes([span("a", 0, 100), span("b", 100, 200)]).count == 2
    )
    assert (
        allocate_horizontal_lanes([span("a", 0, 100), span("b", 119, 200)]).count == 2
    )
    assert (
        allocate_horizontal_lanes([span("a", 0, 100), span("b", 120, 200)]).count == 1
    )
    nested = [span("out", 0, 1000), span("in1", 100, 200), span("in2", 400, 500)]
    plan = allocate_horizontal_lanes(nested)
    assert plan.count == 2
    assert plan.indices["in1"] == plan.indices["in2"] != plan.indices["out"]


def test_parallel_and_backward_spans() -> None:
    parallel = [span(str(i), 310, 370) for i in range(5)]
    plan = allocate_horizontal_lanes(parallel)
    assert plan.count == 5 and len({plan.y(s.edge_id) for s in parallel}) == 5
    # Une arête de retour (cible à gauche) occupe [min, max] comme une autre.
    backward = [span("back", 760, 20), span("fwd", 320, 460)]
    assert allocate_horizontal_lanes(backward).count == 2
    assert span("back", 760, 20).left == 20 and span("back", 760, 20).right == 760


@pytest.mark.parametrize("seed", range(40))
def test_random_plans_are_optimal_and_disjoint(seed: int) -> None:
    rng = random.Random(seed)
    spans: list[HorizontalSpan] = []
    for i in range(rng.randint(0, 40)):
        a, b = rng.randint(0, 2000), rng.randint(0, 2000)
        spans.append(span(f"e{i}", a, b))
    check_plan(spans)
    check_plan(spans, gap=1)


def test_deterministic_and_independent_of_input_object_identity() -> None:
    spans = [span(f"e{i}", (i * 37) % 500, (i * 37) % 500 + 90) for i in range(30)]
    first = allocate_horizontal_lanes(spans)
    second = allocate_horizontal_lanes(
        [HorizontalSpan(*vars(s).values()) for s in spans]
    )
    assert dict(first.indices) == dict(second.indices) and first == second
    # Ex aequo : l'ordre d'entrée tranche, sans dépendre d'un hachage.
    tie = allocate_horizontal_lanes([span("z", 0, 10), span("a", 0, 10)])
    assert (tie.indices["z"], tie.indices["a"]) == (0, 1)
    names = [f"edge-{i}" for i in (7, 3, 9, 0, 5, 1, 8, 2, 6, 4)]
    ties = allocate_horizontal_lanes([span(name, 5, 50) for name in names])
    assert [ties.indices[name] for name in names] == list(range(10))


def test_lanes_stack_upwards_from_band_bottom() -> None:
    plan = allocate_horizontal_lanes(
        [span("a", 0, 10), span("b", 0, 10), span("c", 0, 10)], spacing=10, origin=5
    )
    assert [plan.y(e) for e in "abc"] == [25, 15, 5]
    assert plan.band_bottom == 35
    assert all(plan.y(e) < plan.band_bottom for e in "abc")


def test_invalid_input() -> None:
    with pytest.raises(ValueError, match="dupliquée"):
        allocate_horizontal_lanes([span("a", 0, 1), span("a", 5, 9)])
    for options in ({"spacing": 0}, {"gap": 0}, {"gap": -1}):
        with pytest.raises(ValueError):
            allocate_horizontal_lanes([span("a", 0, 1)], **options)
    plan = allocate_horizontal_lanes([span("a", 0, 1)])
    with pytest.raises(TypeError):
        plan.indices["a"] = 3  # type: ignore[index]


def test_route_label_and_path() -> None:
    points = route_via_horizontal_lane((290, 300), (390, 500), 54)
    assert points == (
        (290, 300),
        (310, 300),
        (310, 54),
        (370, 54),
        (370, 500),
        (390, 500),
    )
    assert svg_path(points) == "M 290 300 H 310 V 54 H 370 V 500 H 390"
    assert lane_label_position(points) == (340, 49)
    # Boucle sur soi et retour vers la gauche : toujours orthogonal.
    loop = route_via_horizontal_lane((300, 90), (40, 90), 30)
    assert svg_path(loop) == "M 300 90 H 320 V 30 H 20 V 90 H 40"
    assert lane_label_position(loop) == (170, 25)
    for a, b in zip(loop, loop[1:]):
        assert a[0] == b[0] or a[1] == b[1]


def test_primitive_is_pure_geometry() -> None:
    tree = ast.parse((ROOT / "forge_design/graphics/lanes.py").read_text())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported <= {"heapq", "collections", "dataclasses", "types"}
