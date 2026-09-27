"""Projection des occurrences, orientation et isolation des transformations."""

import ast
import builtins
import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from jinja2 import Environment

from forge_design.forge import entities as bridge
from forge_design.forge.entities import (
    EntitiesResult,
    EntityFieldInfo,
    EntityInfo,
    ManyToManyInfo,
    ManyToOneInfo,
    RelationInfo,
)
from forge_design.forge.source import SourceLocation
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.entity_graph import EntityGraph, build_entity_graph
from forge_design.web.entity_graph_layout import layout_entity_graph


def entity(name: str) -> EntityInfo:
    return EntityInfo(
        name,
        name.lower(),
        (EntityFieldInfo("title", "string", False, True, False),),
        False,
        False,
        SourceLocation("mvc/entities/example/example.json"),
    )


def relation(source: str, target: str, *, many: bool = False) -> RelationInfo:
    return RelationInfo(
        "many_to_many" if many else "many_to_one",
        source,
        target,
        "business",
        None,
        SourceLocation("mvc/entities/relations.json"),
        0,
        many_to_one=None
        if many
        else ManyToOneInfo("target_id", True, True, "restrict"),
        many_to_many=ManyToManyInfo(
            "shared_pivot", "a_id", "b_id", True, True, "cascade", entity("X").fields
        )
        if many
        else None,
    )


def test_empty_isolated_and_duplicate_names() -> None:
    assert build_entity_graph(EntitiesResult()) == EntityGraph()
    result = EntitiesResult((entity("A"), entity("A"), entity("B")))
    graph = build_entity_graph(result)
    assert [n.label for n in graph.nodes] == ["A", "A", "B"]
    assert len({n.id for n in graph.nodes}) == 3 and graph.edges == ()
    assert [(n.table, n.field_count) for n in graph.nodes] == [
        ("a", 1),
        ("a", 1),
        ("b", 1),
    ]
    graph = build_entity_graph(replace(result, relations=(relation("A", "B"),)))
    assert graph.edges[0].source == graph.nodes[0].id


@pytest.mark.parametrize("many", [False, True])
def test_direction_parallel_and_self(many: bool) -> None:
    result = EntitiesResult(
        (entity("A"), entity("B")),
        relations=(
            relation("B", "A", many=many),
            relation("B", "A", many=many),
            relation("A", "A", many=many),
        ),
    )
    graph = build_entity_graph(result)
    assert graph == build_entity_graph(result)
    assert [n.kind for n in graph.nodes] == ["entity", "entity"] + (
        ["pivot"] * 3 if many else []
    )
    assert len(graph.edges) == (6 if many else 3)
    assert len({e.id for e in graph.edges}) == len(graph.edges)
    assert graph.edges[0].source == graph.nodes[1].id
    assert graph.edges[1 if many else 0].target == graph.nodes[0].id
    assert graph.edges[0].label == "business"
    if many:
        for i in range(3):
            first, second = graph.edges[2 * i : 2 * i + 2]
            pivot = graph.nodes[i + 2]
            assert first.target == pivot.id == second.source
            assert (first.kind, second.kind) == ("many_to_many_from", "many_to_many_to")
            assert pivot.field_count == 1 and pivot.label == "shared_pivot"
            assert second.label == ""
    else:
        assert graph.edges[-1].source == graph.edges[-1].target
        assert all(e.kind == "many_to_one" for e in graph.edges)


@pytest.mark.parametrize("many", [False, True])
@pytest.mark.parametrize(
    "source,target", [("Missing", "A"), ("A", "Missing"), ("X", "Y")]
)
def test_missing_endpoints_no_phantoms(many: bool, source: str, target: str) -> None:
    graph = build_entity_graph(
        EntitiesResult((entity("A"),), relations=(relation(source, target, many=many),))
    )
    assert len(graph.nodes) == 1 and graph.edges == ()


def test_purity_and_immutability(monkeypatch: pytest.MonkeyPatch) -> None:
    result = EntitiesResult(
        (entity("A"), entity("B")), relations=(relation("A", "B", many=True),)
    )
    before = repr(result)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Nouvelle analyse interdite")

    with monkeypatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "lstat", "listdir", "scandir")),
            (Path, ("open", "stat", "lstat", "glob", "rglob", "iterdir")),
            (ast, ("parse",)),
            (json, ("loads", "load")),
            (Environment, ("parse",)),
            (bridge, ("read_entities",)),
            (ToolRegistry, ("get", "list")),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        graph = build_entity_graph(result)
        layout = layout_entity_graph(graph)
        assert graph == build_entity_graph(result)
        assert layout == layout_entity_graph(graph)
    assert repr(result) == before
    assert tuple(n.node for n in layout.nodes) == graph.nodes
    assert tuple(e.edge for e in layout.edges) == graph.edges
    for obj, attr in (
        (graph, "nodes"),
        (graph.nodes[0], "label"),
        (graph.edges[0], "label"),
        (layout, "width"),
        (layout.nodes[0], "x"),
        (layout.edges[0], "path"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, None)
