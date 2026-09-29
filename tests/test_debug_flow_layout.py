"""Géométrie horizontale déterministe et bornage visuel."""

from dataclasses import FrozenInstanceError, replace

import pytest
from test_debug_filters import sample

from forge_design.forge.debug_errors import DebugRequest
from forge_design.tools.debug_flow import build_debug_flow
from forge_design.web.debug_flow_layout import layout_debug_flow


@pytest.mark.parametrize("count", range(6))
def test_geometry(count: int) -> None:
    event = replace(
        sample(),
        request=DebugRequest(method="POST", path="/users"),
        route="/users",
        controller="Controller",
        sql="select",
        template="users",
    )
    full = build_debug_flow(event)
    flow = replace(
        full, nodes=full.nodes[:count], edges=full.edges[: max(0, count - 1)]
    )
    layout = layout_debug_flow(flow)
    assert layout == layout_debug_flow(flow)
    assert layout.width > 0 and layout.height > 0
    assert len(layout.nodes) == count
    for node in layout.nodes:
        assert 0 <= node.x < node.x + node.width <= layout.width
        assert 0 <= node.y < node.y + node.height <= layout.height
    for left, right in zip(layout.nodes, layout.nodes[1:]):
        assert left.x + left.width < right.x
    for edge in layout.edges:
        assert 0 <= edge.x1 < edge.x2 <= layout.width
        assert 0 <= edge.y1 == edge.y2 <= layout.height
    for item in (layout, *layout.nodes, *layout.edges):
        with pytest.raises(FrozenInstanceError):
            setattr(item, next(iter(item.__dataclass_fields__)), None)


def test_long_label() -> None:
    event = replace(sample(), template="templates/" + "x" * 1000)
    layout = layout_debug_flow(build_debug_flow(event))
    assert len(layout.nodes[0].detail) == 24 and layout.nodes[0].detail.endswith("…")
    assert layout.nodes[0].node.detail == event.template
