"""Relations déclaratives, continuation et lecture strictement JSON."""

import builtins
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType

import pytest
from test_entities import contract, entity
from test_web_recent_projects import call, project, running

from forge_design.forge.entities import read_entities
from forge_design.limits import MAX_SOURCE_BYTES
from forge_design.recent_projects import RecentProjects


def fixture(root: Path) -> Path:
    project(root)
    for name in ("Article", "Tag", "Comment"):
        data = contract()
        data["name"] = name
        entity(root, name.lower(), data)
    return root / "mvc/entities/relations.json"


def one() -> dict[str, object]:
    return {
        "type": "many_to_one",
        "from": "Comment",
        "to": "Article",
        "name": "article",
        "foreign_key": "article_id",
        "on_delete": "restrict",
    }


def many() -> dict[str, object]:
    return {
        "type": "many_to_many",
        "from": "Article",
        "to": "Tag",
        "name": "tags",
        "pivot": {
            "table": "article_tag",
            "from_key": "article_id",
            "to_key": "tag_id",
            "id": True,
            "unique_pair": True,
        },
    }


def write(path: Path, relations: list[object]) -> None:
    path.write_text(json.dumps({"schema_version": "1.0", "relations": relations}))


def test_relations_values_order_self_and_missing(tmp_path: Path) -> None:
    root = tmp_path / "project"
    path = fixture(root)
    assert read_entities(root).relations == ()
    first = one()
    first.update(
        nullable=False, index=False, inverse_name="comments", on_delete="set_null"
    )
    second = many()
    second["inverse_name"] = "articles"
    second["pivot"] = {
        "table": "article_tag",
        "from_key": "article_id",
        "to_key": "tag_id",
        "id": True,
        "unique_pair": True,
        "on_delete": "no_action",
        "fields": [
            {"name": "position", "type": "integer", "required": True},
            {"name": "note", "type": "string", "max_length": 100, "unique": True},
            {"name": "amount", "type": "decimal", "precision": 10, "scale": 2},
        ],
    }
    self_relation = one()
    self_relation.update(to="Comment")
    write(path, [first, second, self_relation, one(), many()])
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    result = read_entities(root)
    assert not result.errors and len(result.relations) == 5
    assert [r.source_index for r in result.relations] == list(range(5))
    a, b, c, d, e = result.relations
    assert (a.from_entity, a.to_entity, a.name, a.inverse_name) == (
        "Comment",
        "Article",
        "article",
        "comments",
    )
    assert a.source.path == "mvc/entities/relations.json" and a.source.line is None
    assert a.many_to_one and a.many_to_one.foreign_key == "article_id"
    assert not a.many_to_one.nullable and not a.many_to_one.index
    assert a.many_to_one.on_delete == "set_null"
    assert b.many_to_many and b.inverse_name == "articles"
    pivot = b.many_to_many
    assert (pivot.pivot_table, pivot.from_key, pivot.to_key) == (
        "article_tag",
        "article_id",
        "tag_id",
    )
    assert pivot.id and pivot.unique_pair and pivot.on_delete == "no_action"
    assert not pivot.pivot_fields[0].nullable
    assert pivot.pivot_fields[1].max_length == 100 and pivot.pivot_fields[1].unique
    assert pivot.pivot_fields[2].precision == 10 and pivot.pivot_fields[2].scale == 2
    assert c.from_entity == c.to_entity
    assert d.many_to_one and d.many_to_one.nullable and d.many_to_one.index
    assert e.many_to_many and e.many_to_many.on_delete == "cascade"
    assert e.many_to_many.pivot_fields == ()
    with pytest.raises(FrozenInstanceError):
        setattr(pivot, "id", False)
    (root / "mvc/entities/article/article.json").write_text("{")
    result = read_entities(root)
    assert any(i.code == "relation.entity_missing" for i in result.errors)
    assert (
        len(result.relations) == 5
    )  # Déclarations conservées, cibles non disponibles signalées.


@pytest.mark.parametrize(
    "raw,code",
    [
        ("{", "json_invalid"),
        ("[]", "structure_invalid"),
        ("{}", "schema_version_unsupported"),
        ('{"schema_version":"2.0","relations":[]}', "schema_version_unsupported"),
        (
            '{"schema_version":"1.0","format_version":1,"relations":[]}',
            "schema_version_unsupported",
        ),
        ('{"schema_version":"1.0"}', "structure_invalid"),
        ('{"schema_version":"1.0","relations":{}}', "structure_invalid"),
    ],
)
def test_document_errors_keep_entities(tmp_path: Path, raw: str, code: str) -> None:
    root = tmp_path / "project"
    fixture(root).write_text(raw)
    result = read_entities(root)
    assert len(result.entities) == 3 and not result.relations
    assert result.errors[0].code == "relation." + code


@pytest.mark.parametrize(
    "bad,code",
    [
        ("not an object", "structure_invalid"),
        ({"type": "one_to_one"}, "type_unsupported"),
        ({"type": []}, "type_unsupported"),
        ({**one(), "from": None}, "structure_invalid"),
        ({**one(), "foreign_key": None}, "structure_invalid"),
        ({**one(), "on_delete": "RESTRICT"}, "structure_invalid"),
        ({**one(), "nullable": 1}, "structure_invalid"),
        ({**one(), "index": "true"}, "structure_invalid"),
        ({**one(), "inverse_name": None}, "structure_invalid"),
        ({**many(), "pivot": {}}, "structure_invalid"),
        (
            {
                **many(),
                "pivot": {
                    "table": "x",
                    "from_key": "a",
                    "to_key": "b",
                    "id": 1,
                    "unique_pair": True,
                },
            },
            "structure_invalid",
        ),
        (
            {
                **many(),
                "pivot": {
                    "table": "x",
                    "from_key": "a",
                    "to_key": "b",
                    "id": True,
                    "unique_pair": False,
                },
            },
            "structure_invalid",
        ),
        (
            {
                **many(),
                "pivot": {
                    "table": "x",
                    "from_key": "a",
                    "to_key": "b",
                    "id": True,
                    "unique_pair": True,
                    "fields": [None],
                },
            },
            "structure_invalid",
        ),
    ],
)
def test_local_continuation(tmp_path: Path, bad: object, code: str) -> None:
    root = tmp_path / "project"
    write(fixture(root), [one(), bad, many()])
    result = read_entities(root)
    assert [r.source_index for r in result.relations] == [0, 2]
    assert len(result.errors) == 1 and result.errors[0].source_index == 1
    assert result.errors[0].code == "relation." + code


@pytest.mark.parametrize("kind", ["symlink", "directory", "fifo", "size", "encoding"])
def test_relations_unreadable(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "project"
    path = fixture(root)
    if kind == "symlink":
        outside = tmp_path / "secret"
        outside.write_text("secret")
        path.symlink_to(outside)
    elif kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        path.write_bytes(b" " * (MAX_SOURCE_BYTES + 1) if kind == "size" else b"\xff")
    result = read_entities(root)
    assert len(result.entities) == 3 and not result.relations
    assert result.errors[0].code == "relation.unreadable"


def test_no_execution_or_extra_read_and_no_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    path = fixture(root)
    write(path, [one(), many()])
    for name in ("relations.sql", "__init__.py", "other_relations.json"):
        (path.parent / name).write_text("raise AssertionError('forbidden')")
    before = {
        p: (p.stat().st_size, p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    }
    original_open, original_import = os.open, builtins.__import__
    allowed = {"relations.json", "article.json", "tag.json", "comment.json"}
    opened: list[str] = []

    def guarded(
        name: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if not flags & os.O_DIRECTORY:
            assert str(name) in allowed
            opened.append(str(name))
        return original_open(name, flags, mode, dir_fd=dir_fd)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Execution forbidden")

    def imports(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        assert name != "mvc" and not name.startswith("mvc.")
        return original_import(name, globals, locals, fromlist, level)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", guarded)
        patch.setattr(builtins, "exec", forbidden)
        patch.setattr(builtins, "eval", forbidden)
        patch.setattr(builtins, "__import__", imports)
        patch.setattr(subprocess, "run", forbidden)
        patch.setattr(subprocess, "Popen", forbidden)
        assert len(read_entities(root).relations) == 2
    assert set(opened) == allowed and len(opened) == 4
    assert before == {
        p: (p.stat().st_size, p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    }


def test_relations_http(tmp_path: Path) -> None:
    root = tmp_path / "project"
    path = fixture(root)
    store = RecentProjects(tmp_path / "config/recent.json")
    with running(store) as app:
        assert "Aucun projet ouvert." in call(app, "/entities")[1]
        call(app, "/inspector", method="POST", value=str(root))
        assert "Aucune relation déclarée." in call(app, "/entities")[1]
        write(path, [])
        assert "Aucune relation déclarée." in call(app, "/entities")[1]
        relation = one()
        relation["inverse_name"] = "<script>inverse</script>"
        pivot = many()
        pivot["pivot"] = {
            "table": "article_tag",
            "from_key": "article_id",
            "to_key": "tag_id",
            "id": True,
            "unique_pair": True,
            "fields": [{"name": "position", "type": "integer"}],
        }
        write(path, [relation, False, pivot])
        status, html, headers = call(app, "/entities")
        assert status == 200 and headers["Cache-Control"] == "no-store"
        for value in (
            "many_to_one",
            "many_to_many",
            "article_id",
            "tag_id",
            "cascade",
            "restrict",
            "position",
            "Nom inverse",
            "relations[1]",
            "Anomalies",
        ):
            assert value in html
        table = html.split('id="relations-title"', 1)[1]
        assert table.index("many_to_one") < table.index("many_to_many")
        assert "&lt;script&gt;inverse" in html and "<script>" not in html
        assert '<a href="/entities" aria-current="page">' in html
        assert "/source?" not in html and "<svg" in html
        assert call(app, "/routes")[0] == 200
        path.write_text("{")
        html = call(app, "/entities")[1]
        assert "Aucune relation interprétable." in html and "Article" in html


@pytest.mark.parametrize("kind", ["one", "many"])
@pytest.mark.parametrize("side", ["from", "to"])
def test_missing_entity_reference(tmp_path: Path, kind: str, side: str) -> None:
    root = tmp_path / "project"
    path = fixture(root)
    relation = one() if kind == "one" else many()
    relation[side] = "Missing"
    write(path, [relation])
    result = read_entities(root)
    assert len(result.relations) == 1 and len(result.errors) == 1
    assert result.errors[0].code == "relation.entity_missing"
    assert result.errors[0].source_index == 0


def test_parent_symlink_is_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "project"
    path = fixture(root)
    write(path, [one()])
    outside = tmp_path / "outside"
    path.parent.rename(outside)
    path.parent.symlink_to(outside, target_is_directory=True)
    before = (outside / "relations.json").read_bytes()
    result = read_entities(root)
    assert not result.relations and result.errors[0].code == "entity.unreadable"
    assert (outside / "relations.json").read_bytes() == before
