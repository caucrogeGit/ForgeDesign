"""Contrats JSON directs, confinement et absence d'exécution."""

import builtins
import json
import os
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_web_recent_projects import project

from forge_design.forge.entities import read_entities
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import MAX_SOURCE_BYTES


def contract() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "name": "Contact",
        "table": "contact",
        "fields": [
            {"name": "title", "type": "string", "max_length": 255, "required": True}
        ],
        "options": {"timestamps": False, "soft_delete": False},
    }


def entity(root: Path, folder: str, data: object) -> Path:
    directory = root / "mvc/entities" / folder
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (folder + ".json")
    target.write_text(json.dumps(data), encoding="utf-8")
    return target


def test_absent_and_non_forge(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    result = read_entities(root)
    assert not result.entities and result.warnings[0].code == "entity.source_missing"
    with pytest.raises(NotForgeProjectError):
        read_entities(tmp_path)


def test_values_order_defaults_immutability(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    data = contract()
    data["options"] = {"timestamps": True, "soft_delete": True}
    data["fields"] = [
        {
            "name": "title",
            "type": "string",
            "required": True,
            "nullable": True,
            "unique": True,
            "max_length": 255,
            "default": "<script>",
        },
        {"name": "price", "type": "decimal", "precision": 10, "scale": 2, "default": 0},
        {
            "name": "owner_id",
            "type": "foreign_key",
            "references": "User",
            "default": None,
        },
        {"name": "custom", "type": "future_type", "default": {"a": [1, False]}},
    ]
    target = entity(root, "zeta", data)
    target.write_bytes(b"\xef\xbb\xbf" + target.read_bytes())
    simple = contract()
    del simple["options"]
    entity(root, "alpha", simple)
    result = read_entities(root)
    assert not result.errors
    assert [e.source.path for e in result.entities] == [
        "mvc/entities/alpha/alpha.json",
        "mvc/entities/zeta/zeta.json",
    ]
    first, last = result.entities
    assert not first.timestamps and not first.soft_delete
    assert last.name == "Contact" and last.table == "contact"
    assert last.timestamps and last.soft_delete
    title, price, owner, custom = last.fields
    assert (
        title.required
        and not title.nullable
        and title.unique
        and title.max_length == 255
    )
    assert price.precision == 10 and price.scale == 2 and price.default_json == "0"
    assert (
        owner.references == "User" and owner.default_json == "null" and owner.nullable
    )
    assert custom.type == "future_type" and custom.default_json == '{"a": [1, false]}'
    assert first.fields[0].default_json is None
    with pytest.raises(FrozenInstanceError):
        setattr(title, "name", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(result, "entities", ())


@pytest.mark.parametrize(
    "change,code",
    [
        ({"schema_version": "2.0"}, "entity.schema_version_unsupported"),
        ({"format_version": 1}, "entity.schema_version_unsupported"),
        ({"name": 42}, "entity.structure_invalid"),
        ({"table": None}, "entity.structure_invalid"),
        ({"fields": {}}, "entity.structure_invalid"),
        ({"fields": []}, "entity.structure_invalid"),
        ({"fields": [None]}, "entity.structure_invalid"),
        ({"fields": [{"name": "x"}]}, "entity.structure_invalid"),
        (
            {"fields": [{"name": "x", "type": "string", "required": 1}]},
            "entity.structure_invalid",
        ),
        (
            {"fields": [{"name": "x", "type": "decimal", "scale": True}]},
            "entity.structure_invalid",
        ),
        ({"options": None}, "entity.structure_invalid"),
        ({"options": {"timestamps": "false"}}, "entity.structure_invalid"),
    ],
)
def test_invalid_local_entity(
    tmp_path: Path, change: dict[str, object], code: str
) -> None:
    root = project(tmp_path / "project")
    data = contract()
    data.update(change)
    entity(root, "bad", data)
    entity(root, "good", contract())
    result = read_entities(root)
    assert len(result.entities) == 1 and result.entities[0].source.path.endswith(
        "good.json"
    )
    assert result.errors[0].code == code


@pytest.mark.parametrize(
    "content,code",
    [
        (b"{", "entity.json_invalid"),
        (b"\xff", "entity.unreadable"),
        (b" " * (MAX_SOURCE_BYTES + 1), "entity.unreadable"),
        (b"NaN", "entity.json_invalid"),
        (b"[]", "entity.structure_invalid"),
    ],
)
def test_bad_bytes(tmp_path: Path, content: bytes, code: str) -> None:
    root = project(tmp_path / "project")
    entity(root, "bad", contract()).write_bytes(content)
    assert read_entities(root).errors[0].code == code


@pytest.mark.parametrize(
    "kind", ["missing", "file-link", "folder-link", "parent-link", "directory", "fifo"]
)
def test_refused_sources(tmp_path: Path, kind: str) -> None:
    root = project(tmp_path / "project")
    target = entity(root, "contact", contract())
    outside = tmp_path / "outside"
    if kind == "folder-link":
        target.parent.rename(outside)
        target.parent.symlink_to(outside, target_is_directory=True)
    elif kind == "parent-link":
        target.parent.parent.rename(outside)
        target.parent.parent.symlink_to(outside, target_is_directory=True)
    else:
        target.unlink()
        if kind == "file-link":
            outside.write_text(json.dumps(contract()))
            target.symlink_to(outside)
        elif kind == "directory":
            target.mkdir()
        elif kind == "fifo":
            os.mkfifo(target)
    result = read_entities(root)
    assert not result.entities
    assert result.errors[0].code == (
        "entity.source_missing" if kind == "missing" else "entity.unreadable"
    )


def test_only_canonical_json_opened_and_no_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    target = entity(root, "contact", contract())
    for name in ("contact.py", "contact_base.py", "contact.sql", "other.json"):
        (target.parent / name).write_text("raise AssertionError('forbidden')")
    for name in (
        "relations.json",
        "relations.sql",
        "__init__.py",
        ".env",
        "secret.key",
    ):
        (target.parent.parent / name).write_text("forbidden")
    for name in ("env", ".git", "__pycache__", "id_rsa", "nested/deeper"):
        (target.parent.parent / name).mkdir(parents=True)
    before = {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    }
    original_open = os.open
    opened: list[str] = []

    def guarded(
        path: str | Path, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if not flags & os.O_DIRECTORY:
            assert path == "contact.json"
            opened.append(str(path))
        return original_open(path, flags, mode, dir_fd=dir_fd)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Forbidden operation")

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", guarded)
        patch.setattr(builtins, "exec", forbidden)
        patch.setattr(builtins, "eval", forbidden)
        patch.setattr(subprocess, "run", forbidden)
        patch.setattr(Path, "open", forbidden)
        result = read_entities(root)
        assert len(result.entities) == 1
        assert read_entities(root) == result
    assert opened == ["contact.json", "contact.json"]
    assert before == {
        p: (p.read_bytes(), p.stat().st_mtime_ns)
        for p in root.rglob("*")
        if p.is_file()
    }


def test_inaccessible_entry_does_not_hide_following_entity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    entity(root, "bad", contract())
    entity(root, "good", contract())
    original = os.stat

    def stat(
        path: str | Path | int,
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        if path == "bad" and dir_fd is not None:
            raise PermissionError("simulated")
        return original(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "stat", stat)
    result = read_entities(root)
    assert len(result.entities) == 1
    assert result.entities[0].source.path.endswith("good/good.json")
    assert result.errors[0].code == "entity.unreadable"
