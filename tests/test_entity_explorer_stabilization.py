"""Bornes, races, contrats et cohérence transversale de la verticale."""

import inspect
import json
import os
import re
from dataclasses import fields, replace
from pathlib import Path
from urllib.parse import urlencode

import pytest
from test_entities import contract, entity
from test_entity_graph import entity as info
from test_entity_graph import relation
from test_entity_relations import many, one, write
from test_web_recent_projects import call, project, running

from forge_design import limits
from forge_design.app import create_tool_registry
from forge_design.forge import entities as bridge
from forge_design.forge.entities import EntitiesResult, read_entities
from forge_design.forge.source import SourceLocation, SourceReadError, source_parts
from forge_design.recent_projects import RecentProjects
from forge_design.tools.entity_diagnostics import build_entity_diagnostics
from forge_design.tools.entity_explorer import EntityExplorerTool
from forge_design.tools.entity_filters import EntityFilter, filter_entities
from forge_design.tools.entity_graph import (
    build_entity_graph,
    build_entity_graph_from_items,
)
from forge_design.web.entity_graph_layout import layout_entity_graph
from forge_design.web.source import source_available


def test_public_api_and_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Pas de lecture au démarrage")

    monkeypatch.setattr(bridge, "read_entities", forbidden)
    assert [t.id for t in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
    ]
    assert EntityExplorerTool().id == "entity-explorer"
    for function, parameters in (
        (read_entities, ["root"]),
        (build_entity_graph, ["result"]),
        (build_entity_diagnostics, ["result"]),
        (filter_entities, ["result", "diagnostics", "filters"]),
        (layout_entity_graph, ["graph"]),
    ):
        assert list(inspect.signature(function).parameters) == parameters
    for name in (
        "EntitiesResult",
        "EntityInfo",
        "EntityFieldInfo",
        "RelationInfo",
        "ManyToOneInfo",
        "ManyToManyInfo",
    ):
        assert getattr(bridge, name).__dataclass_params__.frozen
    assert [f.name for f in fields(EntitiesResult)] == [
        "entities",
        "errors",
        "warnings",
        "relations",
    ]


@pytest.mark.parametrize("extra", [0, 1])
def test_entity_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: int
) -> None:
    root = project(tmp_path / "project")
    monkeypatch.setattr(bridge, "MAX_ENTITY_FILES", 2)
    for i in range(2 + extra):
        entity(root, f"a{i}", {**contract(), "name": f"A{i}", "table": f"a{i}"})
    result = read_entities(root)
    assert [e.name for e in result.entities] == ["A0", "A1"]
    assert [w.code for w in result.warnings] == (
        ["entity.analysis_truncated"] if extra else []
    )
    if extra:
        d = build_entity_diagnostics(result)
        assert d.warning_count == 1 and d.items[0].source == SourceLocation(
            "mvc/entities"
        )
        view = filter_entities(result, d, EntityFilter(diagnostics_only=True))
        assert view.entities == view.relations == () and view.diagnostics == d


def test_discovery_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path / "project")
    directory = root / "mvc/entities"
    directory.mkdir()
    for i in range(5):
        (directory / f".ignored{i}").touch()
    monkeypatch.setattr(bridge, "MAX_ENTITY_DIRECTORY_ENTRIES", 3)
    result = read_entities(root)
    assert result.entities == ()
    assert [w.code for w in result.warnings] == ["entity.analysis_truncated"]


@pytest.mark.parametrize("extra", [0, 1])
def test_relation_and_fields_limits(tmp_path: Path, extra: int) -> None:
    root = project(tmp_path / "project")
    entity(
        root,
        "article",
        {
            **contract(),
            "name": "Article",
            "fields": [
                {"name": f"f{i}", "type": "string"}
                for i in range(limits.MAX_ENTITY_FIELDS + extra)
            ],
        },
    )
    pivot = many()
    pivot["pivot"] = {
        "table": "article_tag",
        "from_key": "article_id",
        "to_key": "tag_id",
        "id": True,
        "unique_pair": True,
        "fields": [
            {"name": f"p{i}", "type": "string"}
            for i in range(limits.MAX_ENTITY_PIVOT_FIELDS + extra)
        ],
    }
    items: list[object] = [pivot]
    items.extend(one() for _ in range(limits.MAX_ENTITY_RELATIONS - 1 + extra))
    write(root / "mvc/entities/relations.json", items)
    result = read_entities(root)
    assert len(result.entities[0].fields) == limits.MAX_ENTITY_FIELDS
    assert len(result.relations) == limits.MAX_ENTITY_RELATIONS
    many_info = result.relations[0].many_to_many
    assert many_info and len(many_info.pivot_fields) == limits.MAX_ENTITY_PIVOT_FIELDS
    assert [r.source_index for r in result.relations] == list(
        range(limits.MAX_ENTITY_RELATIONS)
    )
    assert {w.code for w in result.warnings} == (
        {
            "entity.fields_truncated",
            "relation.analysis_truncated",
            "relation.fields_truncated",
        }
        if extra
        else set()
    )
    diagnostics = build_entity_diagnostics(result)
    for issue, diagnostic in zip(result.errors + result.warnings, diagnostics.items):
        assert (issue.code, issue.source, issue.source_index) == (
            diagnostic.code,
            diagnostic.source,
            diagnostic.relation_index,
        )
    assert diagnostics.warning_count == len(result.warnings)
    graph = build_entity_graph(result)
    assert len(graph.nodes) == 1 and graph.edges == ()


def test_duplicate_diagnostics_and_filtered_first_occurrence(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    for folder in ("a", "b"):
        entity(root, folder, contract())
    result = read_entities(root)
    assert [w.code for w in result.warnings] == [
        "entity.name_duplicate",
        "entity.table_duplicate",
    ] * 2
    d = build_entity_diagnostics(result)
    assert (
        filter_entities(
            result, d, EntityFilter(severity="warning", diagnostics_only=True)
        ).entities
        == result.entities
    )
    synthetic = replace(result, relations=(relation("Contact", "Contact"),))
    view = filter_entities(synthetic, d, EntityFilter(item_type="relation"))
    assert view.graph_entities == result.entities[:1]
    assert len(build_entity_graph(synthetic).nodes) == 2


@pytest.mark.parametrize("kind", ["folder", "relations"])
def test_replacement_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    root = project(tmp_path / "project")
    target = entity(root, "contact", contract())
    write(target.parent.parent / "relations.json", [])
    original = os.open
    changed = False

    def raced(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        nonlocal changed
        if (
            not changed
            and dir_fd is not None
            and path == ("contact" if kind == "folder" else "relations.json")
        ):
            changed = True
            victim = (
                target.parent
                if kind == "folder"
                else target.parent.parent / "relations.json"
            )
            victim.rename(root / "old")
            if kind == "folder":
                victim.mkdir()
                (victim / "contact.json").write_text(json.dumps(contract()))
            else:
                victim.write_text('{"schema_version":"1.0","relations":[]}')
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", raced)
    result = read_entities(root)
    assert changed
    assert [e.code for e in result.errors] == [
        f"{'entity' if kind == 'folder' else 'relation'}.unreadable"
    ]
    if kind == "folder":
        assert not result.entities


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(
            "[" * 10000 + "0" + "]" * 10000,
            id="deep",
        ),
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
@pytest.mark.parametrize("kind", ["entity", "relation"])
def test_pathological_json(tmp_path: Path, raw: str, kind: str) -> None:
    root = project(tmp_path / "project")
    target = entity(root, "contact", contract())
    if kind == "relation":
        target = target.parent.parent / "relations.json"
    target.write_text(raw)
    assert f"{kind}.json_invalid" in [e.code for e in read_entities(root).errors]


@pytest.mark.parametrize(
    "name",
    [
        "env",
        ".env",
        "id_rsa",
        "id_ed25519",
        "x.pem",
        "x.key",
        "ENV",
        "Env",
        "ID_RSA",
        "foo.PEM",
        "foo.KEY",
    ],
)
def test_sensitive_names_match_source(tmp_path: Path, name: str) -> None:
    root = project(tmp_path / "project")
    entity(root, name, contract())
    assert read_entities(root).entities == ()
    with pytest.raises(SourceReadError):
        source_parts(f"mvc/entities/{name}/{name}.json")


def test_large_graph_bounds_and_ids() -> None:
    result = EntitiesResult(
        tuple(info(f"A{i}") for i in range(100)),
        relations=tuple(
            replace(
                relation(f"A{i % 100}", f"A{(i + 1) % 100}", many=i % 2 == 0),
                source_index=i,
            )
            for i in range(200)
        ),
    )
    graph = build_entity_graph(result)
    assert len(graph.nodes) == 200 and len(graph.edges) == 300
    assert len({n.id for n in graph.nodes}) == len(graph.nodes)
    assert len({e.id for e in graph.edges}) == len(graph.edges)
    layout = layout_entity_graph(graph)
    for n in layout.nodes:
        assert 0 <= n.x < n.x + n.width <= layout.width
        assert 0 <= n.y < n.y + n.height <= layout.height
    for e in layout.edges:
        numbers = [int(n) for n in re.findall(r"\d+", e.path)]
        assert all(0 <= n <= max(layout.width, layout.height) for n in numbers)
        assert 0 <= e.label_x <= layout.width and 0 <= e.label_y <= layout.height
    assert layout == layout_entity_graph(graph)
    for query in ("A1", "no-match"):
        view = filter_entities(
            result, build_entity_diagnostics(result), EntityFilter(query=query)
        )
        filtered = build_entity_graph_from_items(view.graph_entities, view.relations)
        assert all(
            e.source in {n.id for n in filtered.nodes}
            and e.target in {n.id for n in filtered.nodes}
            for e in filtered.edges
        )


def test_unicode_limit_roundtrip() -> None:
    f = EntityFilter(query="ß" * 128)
    assert EntityFilter(query=f.query) == f
    with pytest.raises(ValueError):
        EntityFilter(query="ß" * 129)


def test_http_truncation_missing_source_and_parameters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    entity(root, "article", {**contract(), "name": "Article"})
    data = one()
    data["from"] = "Article"
    data["to"] = "Missing"
    write(root / "mvc/entities/relations.json", [data, data])
    monkeypatch.setattr(bridge, "MAX_ENTITY_RELATIONS", 1)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        status, _, headers = call(app, "/source?path=mvc/entities/relations.json")
        assert status == 409 and headers["Cache-Control"] == "no-store"
        call(app, "/inspector", method="POST", value=str(root))
        for query in ("", "?diagnostics=only", "?severity=warning"):
            status, html, headers = call(app, "/entities" + query)
            assert status == 200 and headers["Cache-Control"] == "no-store"
            assert "script-src 'self'" in headers["Content-Security-Policy"]
            assert "relation.analysis_truncated" in html and "Avertissement" in html
            assert "Missing" in html and "relations[0]" in html
        assert call(app, "/entities?" + urlencode({"q": "ß" * 129}))[0] == 400
        for query, expected in (
            ("path=mvc/entities/relations.json", 200),
            ("path=mvc/entities/missing/missing.json", 404),
            ("path=../config.py", 400),
            (
                "path=mvc/entities/relations.json&path=../config.py&line=1&line=999&unknown=x",
                200,
            ),
        ):
            status, html, headers = call(app, "/source?" + query)
            assert status == expected and headers["Cache-Control"] == "no-store"
        assert source_available(SourceLocation("mvc/entities/relations.json"))
        assert call(app, "/entities", method="POST")[0] == 405
        assert call(app, "/source", method="POST")[0] == 405


def test_structure_bombs_remain_bounded(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    field = {"name": "f", "type": "string"}
    target = entity(
        root, "article", {**contract(), "name": "Article", "fields": [field] * 12000}
    )
    pivot = many()
    pivot["pivot"] = {
        "table": "p",
        "from_key": "a",
        "to_key": "b",
        "id": True,
        "unique_pair": True,
        "fields": [field] * 12000,
    }
    items: list[object] = [pivot]
    items.extend([None] * 10000)
    path = root / "mvc/entities/relations.json"
    write(path, items)
    assert target.stat().st_size < limits.MAX_SOURCE_BYTES
    assert path.stat().st_size < limits.MAX_SOURCE_BYTES
    result = read_entities(root)
    assert len(result.entities[0].fields) == limits.MAX_ENTITY_FIELDS
    assert len(result.relations) == 1
    many_info = result.relations[0].many_to_many
    assert many_info and len(many_info.pivot_fields) == limits.MAX_ENTITY_PIVOT_FIELDS
    assert len(result.errors) == limits.MAX_ENTITY_RELATIONS
    assert len(result.warnings) == 3
