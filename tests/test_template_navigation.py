"""États locaux confinés, sans contenu cible, cache limité à l'appel."""

import os
import socket
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_templates import make_views

from forge_design.forge import source
from forge_design.forge.template_structure import TemplateReference
from forge_design.limits import MAX_SOURCE_BYTES, MAX_TEMPLATE_REFERENCES
from forge_design.tools import template_navigation as navigation
from forge_design.tools.template_navigation import resolve_template_references


def ref(path: str | None, *, dynamic: bool = False, line: int = 1) -> TemplateReference:
    return TemplateReference("include", path, dynamic, line)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "..",
        "../secret",
        "/absolute",
        ".hidden/page",
        "a/../b",
        "a\\b",
        "C:page",
        "a\x00b",
        "env",
        "private.key",
        "ID_RSA",
        "a//b",
        "x" * 4096,
    ],
)
def test_lexical_no_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No filesystem access")

    monkeypatch.setattr(navigation, "inspect_project_source", forbidden)
    result = resolve_template_references(tmp_path, (ref(path),))[0]
    assert result.status == "invalid-path" and result.target_path is None


@pytest.mark.parametrize(
    "reference", [ref(None), ref(None, dynamic=True), ref("../x", dynamic=True)]
)
def test_dynamic_no_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reference: TemplateReference
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No lexical path or I/O for dynamic")

    monkeypatch.setattr(navigation, "inspect_project_source", forbidden)
    monkeypatch.setattr(navigation, "template_source", forbidden)
    assert resolve_template_references(tmp_path, (reference,))[0].status == "dynamic"


def test_present_missing_no_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    (views / "nested").mkdir()
    (views / "nested/page").write_text("{% if")
    (views / "binary").write_bytes(b"\xff")
    (views / "large").write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No content or parsing")

    monkeypatch.setattr(os, "fdopen", forbidden)
    monkeypatch.setattr(os, "read", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    references = tuple(ref(p) for p in ("nested/page", "absent", "binary", "large"))
    result = resolve_template_references(root, references)
    assert [item.status for item in result] == [
        "available",
        "missing",
        "available",
        "unreadable",
    ]
    assert result[0].target_path == "nested/page"
    assert result[1].target_path is None
    with pytest.raises(FrozenInstanceError):
        setattr(result[0], "status", "missing")


def test_special_files(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    (views / "target").touch()
    (views / "link").symlink_to(views / "target")
    (views / "parent").symlink_to(views, target_is_directory=True)
    (views / "folder").mkdir()
    os.mkfifo(views / "fifo")
    with socket.socket(socket.AF_UNIX) as special:
        special.bind(str(views / "socket"))
        result = resolve_template_references(
            root,
            tuple(
                ref(p) for p in ("link", "parent/target", "folder", "fifo", "socket")
            ),
        )
        assert all(item.status == "unreadable" for item in result)


def test_cache_duplicates_and_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    references = tuple(
        TemplateReference(kind, "page", False, i + 1)
        for i, kind in enumerate(("extends", "include", "import", "from-import"))
    )
    original = navigation.inspect_project_source
    calls: list[str] = []

    def inspect(root: Path, path: str) -> source.SourceMetadata:
        calls.append(path)
        return original(root, path)

    monkeypatch.setattr(navigation, "inspect_project_source", inspect)
    for state in ("missing", "available", "missing", "unreadable"):
        result = resolve_template_references(root, references)
        assert [item.reference for item in result] == list(references)
        assert all(item.status == state for item in result)
        assert calls[-1] == "mvc/views/page"
        if state == "missing" and len(calls) == 1:
            (views / "page").touch()
        elif state == "available":
            (views / "page").unlink()
        elif state == "missing":
            (views / "page").symlink_to(root / "app.py")
    assert len(calls) == 4


def test_replacement_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, views = make_views(tmp_path)
    target = views / "page"
    target.write_text("old")
    original = os.stat

    def raced(
        path: str | bytes | int | os.PathLike[str] | os.PathLike[bytes],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        metadata = original(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        if path == "page" and dir_fd is not None:
            target.rename(views / "old")
            target.write_text("new")
        return metadata

    monkeypatch.setattr(os, "stat", raced)
    assert resolve_template_references(root, (ref("page"),))[0].status == "unreadable"


def test_inaccessible_and_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def denied(root: Path, path: str) -> source.SourceMetadata:
        calls.append(path)
        raise source.SourceReadError("inaccessible")

    monkeypatch.setattr(navigation, "inspect_project_source", denied)
    refs = tuple(ref(f"page{i}") for i in range(MAX_TEMPLATE_REFERENCES))
    result = resolve_template_references(tmp_path, refs)
    assert len(calls) == 512 and all(item.status == "unreadable" for item in result)
    with pytest.raises(ValueError):
        resolve_template_references(tmp_path, refs + (ref("extra"),))
    assert len(calls) == 512
