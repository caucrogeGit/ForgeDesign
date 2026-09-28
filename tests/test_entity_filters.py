"""Filtres purs, associations exactes et graphe reconstruit depuis les tuples."""

import builtins
import json
import os
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import cast

import pytest
from test_entity_graph import entity, relation

from forge_design.forge import entities as bridge
from forge_design.forge.entities import EntitiesResult, EntityFieldInfo
from forge_design.forge.source import SourceLocation
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.entity_diagnostics import EntityDiagnostic, EntityDiagnostics
from forge_design.tools.entity_filters import (
    EntityFilter,
    ItemType,
    RelationType,
    SeverityFilter,
    filter_entities,
)
from forge_design.tools.entity_graph import build_entity_graph_from_items


@pytest.fixture
def inventory() -> EntitiesResult:
    entities = tuple(
        replace(entity(n), source=SourceLocation(f"{n}.json"))
        for n in ("Article", "Tag", "Comment", "User", "Straße")
    )
    first = replace(
        entities[0],
        table="articles_table",
        fields=(
            EntityFieldInfo(
                "email_field", "email_type", False, True, False, references="Classe"
            ),
        ),
    )
    many = relation("Article", "Tag", many=True)
    assert many.many_to_many is not None
    many = replace(
        many,
        source_index=2,
        name="tags_business",
        inverse_name="articles_inverse",
        many_to_many=replace(
            many.many_to_many,
            pivot_table="article_tag",
            from_key="article_key",
            to_key="tag_key",
            pivot_fields=(
                EntityFieldInfo("position", "rank_type", False, True, False),
            ),
        ),
    )
    return EntitiesResult(
        (first, *entities[1:]),
        relations=(
            replace(
                relation("Comment", "Article"), source_index=7, name="comment_business"
            ),
            many,
            replace(relation("User", "User"), source_index=9),
        ),
    )


@pytest.fixture
def diagnostics() -> EntityDiagnostics:
    return EntityDiagnostics(
        (
            EntityDiagnostic(
                "same.code", "error", "no parsing", SourceLocation("Article.json", 8)
            ),
            EntityDiagnostic(
                "same.code", "warning", "no parsing", SourceLocation("Tag.json")
            ),
            EntityDiagnostic("same.code", "error", "no parsing", relation_index=2),
            EntityDiagnostic("same.code", "info", "no parsing", relation_index=9),
            EntityDiagnostic("global", "error", "Article Comment User"),
        )
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("  ", None),
        (" Article ", "article"),
        (" STRAẞE ", "strasse"),
    ],
)
def test_normalization(raw: str | None, expected: str | None) -> None:
    assert EntityFilter(query=raw).query == expected


@pytest.mark.parametrize(
    "query", ["Article", "articles_table", "email_field", "email_type", "classe"]
)
def test_entity_search(inventory: EntitiesResult, query: str) -> None:
    view = filter_entities(
        inventory, EntityDiagnostics(), EntityFilter(query=query, item_type="entity")
    )
    assert view.entities == (inventory.entities[0],)
    assert view.graph_entities == view.entities and view.relations == ()


@pytest.mark.parametrize(
    "query",
    [
        "Article",
        "Tag",
        "tags_business",
        "articles_inverse",
        "article_tag",
        "article_key",
        "tag_key",
        "position",
        "rank_type",
    ],
)
def test_relation_search(inventory: EntitiesResult, query: str) -> None:
    view = filter_entities(
        inventory,
        EntityDiagnostics(),
        EntityFilter(query=query, item_type="relation", relation_type="many_to_many"),
    )
    assert view.entities == () and view.relations == (inventory.relations[1],)
    assert view.graph_entities == inventory.entities[:2]
    graph = build_entity_graph_from_items(view.graph_entities, view.relations)
    assert [n.label for n in graph.nodes] == ["Article", "Tag", "article_tag"]
    assert len(graph.edges) == 2
    assert graph == build_entity_graph_from_items(view.graph_entities, view.relations)


def test_foreign_key_unicode_and_one_endpoints(inventory: EntitiesResult) -> None:
    view = filter_entities(
        inventory, EntityDiagnostics(), EntityFilter(query="target_id")
    )
    assert view.entities == () and view.relations == (
        inventory.relations[0],
        inventory.relations[2],
    )
    view = filter_entities(
        inventory, EntityDiagnostics(), EntityFilter(query="comment")
    )
    assert view.entities == (inventory.entities[2],)
    assert view.graph_entities == (inventory.entities[0], inventory.entities[2])
    graph = build_entity_graph_from_items(view.graph_entities, view.relations)
    assert len(graph.nodes) == 2 and len(graph.edges) == 1
    view = filter_entities(
        inventory, EntityDiagnostics(), EntityFilter(query="STRASSE")
    )
    assert view.entities == (inventory.entities[-1],)


@pytest.mark.parametrize("kind", ["all", "entity", "relation"])
@pytest.mark.parametrize("relation_type", ["all", "many_to_one", "many_to_many"])
def test_types(
    inventory: EntitiesResult, kind: ItemType, relation_type: RelationType
) -> None:
    view = filter_entities(
        inventory,
        EntityDiagnostics(),
        EntityFilter(item_type=kind, relation_type=relation_type),
    )
    assert view.entities == (() if kind == "relation" else inventory.entities)
    assert view.relations == tuple(
        r
        for r in inventory.relations
        if kind != "entity" and (relation_type == "all" or r.type == relation_type)
    )
    assert (view.total_entities, view.total_relations) == (5, 3)


@pytest.mark.parametrize("severity", ["all", "error", "warning", "info"])
@pytest.mark.parametrize("only", [False, True])
def test_diagnostics(
    inventory: EntitiesResult,
    diagnostics: EntityDiagnostics,
    severity: SeverityFilter,
    only: bool,
) -> None:
    view = filter_entities(
        inventory, diagnostics, EntityFilter(severity=severity, diagnostics_only=only)
    )
    expected = tuple(
        d for d in diagnostics.items if severity == "all" or d.severity == severity
    )
    assert view.diagnostics.items == expected
    if not only:
        assert (
            view.entities == inventory.entities
            and view.relations == inventory.relations
        )
    else:
        assert view.entities == tuple(
            e
            for e in inventory.entities
            if any(d.source and d.source.path == e.source.path for d in expected)
        )
        assert view.relations == tuple(
            r
            for r in inventory.relations
            if any(d.relation_index == r.source_index for d in expected)
        )
    assert diagnostics.items[-1].code == "global"


def test_combination_global_and_duplicates(
    inventory: EntitiesResult, diagnostics: EntityDiagnostics
) -> None:
    view = filter_entities(
        inventory,
        diagnostics,
        EntityFilter(
            query="article",
            relation_type="many_to_many",
            severity="error",
            diagnostics_only=True,
        ),
    )
    assert view.entities == (inventory.entities[0],)
    assert view.relations == (inventory.relations[1],)
    assert view.graph_entities == inventory.entities[:2]
    assert view.diagnostics.items[-1].code == "global"
    global_only = EntityDiagnostics((diagnostics.items[-1],))
    view = filter_entities(inventory, global_only, EntityFilter(diagnostics_only=True))
    assert view.entities == view.relations == view.graph_entities == ()
    assert view.diagnostics == global_only
    duplicated = replace(
        inventory, entities=(*inventory.entities, inventory.entities[0])
    )
    view = filter_entities(duplicated, diagnostics, EntityFilter(item_type="relation"))
    assert view.graph_entities == inventory.entities[:4]
    view = filter_entities(duplicated, diagnostics, EntityFilter())
    assert view.entities == duplicated.entities


def test_invalid_and_limit() -> None:
    for key in ("item_type", "relation_type", "severity"):
        with pytest.raises(ValueError):
            replace(EntityFilter(), **{key: "invalid"})
    assert EntityFilter(query="a" * 256).query == "a" * 256
    with pytest.raises(ValueError):
        EntityFilter(query=" " * 257)
    with pytest.raises(ValueError):
        EntityFilter(item_type=cast(ItemType, "invalid"))


def test_purity_immutability(
    inventory: EntitiesResult, diagnostics: EntityDiagnostics
) -> None:
    filters = EntityFilter(query="Article")
    before = repr((inventory, diagnostics, filters))

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Nouvelle analyse interdite")

    with pytest.MonkeyPatch.context() as guard:
        for target, names in (
            (builtins, ("open",)),
            (os, ("open", "stat", "listdir")),
            (Path, ("read_text", "read_bytes", "open")),
            (json, ("loads",)),
            (ToolRegistry, ("get",)),
            (bridge, ("read_entities",)),
        ):
            for name in names:
                guard.setattr(target, name, forbidden)
        view = filter_entities(inventory, diagnostics, filters)
        assert view == filter_entities(inventory, diagnostics, filters)
    assert repr((inventory, diagnostics, filters)) == before
    for obj, attr in ((filters, "query"), (view, "entities")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, attr, None)
    assert isinstance(view.entities, tuple) and isinstance(view.relations, tuple)
    assert isinstance(view.graph_entities, tuple)
