"""Inventaire borné, métadonnées vérifiées et source brute commune."""

import os
import socket
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_web_recent_projects import project

from forge_design.forge import templates
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceReadError
from forge_design.forge.templates import read_template_source, read_templates
from forge_design.limits import MAX_SOURCE_BYTES


def make_views(tmp_path: Path) -> tuple[Path, Path]:
    root = project(tmp_path / "project")
    views = root / "mvc/views"
    views.mkdir()
    return root, views


def test_roots_and_empty(tmp_path: Path) -> None:
    with pytest.raises(ProjectRootNotFoundError):
        read_templates(tmp_path / "missing")
    (tmp_path / "file").touch()
    with pytest.raises(ProjectRootNotDirectoryError):
        read_templates(tmp_path / "file")
    with pytest.raises(NotForgeProjectError):
        read_templates(tmp_path)
    root = project(tmp_path / "project")
    assert read_templates(root) == templates.TemplatesResult((), (), False, False)
    (root / "mvc/views").mkdir()
    assert read_templates(root) == templates.TemplatesResult((), (), True, False)


def test_inventory_metadata_order_no_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    names = ("z.xml", "a/page.jinja", "é/fragment", "a.html", "empty")
    for index, name in enumerate(names):
        file = views / name
        file.parent.mkdir(exist_ok=True)
        file.write_bytes(b"\xff" * index)
        os.utime(
            file,
            ns=(1_700_000_000_000_000_000 + index, 1_700_000_000_000_000_000 + index),
        )
    expected = tuple(
        templates.TemplateInfo(
            name, (views / name).stat().st_size, (views / name).stat().st_mtime_ns
        )
        for name in sorted(names)
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Inventory must not read contents")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(os, "read", forbidden)
    monkeypatch.setattr(os, "fdopen", forbidden)
    result = read_templates(root)
    assert result.templates == expected and result.issues == ()
    assert result == read_templates(root)
    with pytest.raises(FrozenInstanceError):
        setattr(result, "truncated", True)
    with pytest.raises(FrozenInstanceError):
        setattr(result.templates[0], "size", 0)


@pytest.mark.parametrize(
    "name",
    [
        ".hidden",
        "env",
        "ENV",
        "id_rsa",
        "ID_ED25519.pub",
        "secret.pem",
        "secret.KEY",
        "bad:name",
        "bad\\name",
        ".hidden/page",
        "env/page",
    ],
)
def test_sensitive_exclusions(tmp_path: Path, name: str) -> None:
    root, views = make_views(tmp_path)
    path = views / name
    path.parent.mkdir(exist_ok=True)
    path.touch()
    assert read_templates(root).templates == ()
    with pytest.raises(SourceReadError):
        read_template_source(root, name)


def test_special_and_linked_files(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("external")
    (views / "linked").symlink_to(outside / "secret")
    (views / "directory").symlink_to(outside, target_is_directory=True)
    os.mkfifo(views / "fifo")
    with socket.socket(socket.AF_UNIX) as special:
        special.bind(str(views / "socket"))
        assert read_templates(root).templates == ()
    for name in ("linked", "directory/secret", "fifo"):
        with pytest.raises(SourceReadError):
            read_template_source(root, name)


@pytest.mark.parametrize("segment", ["mvc", "views"])
def test_linked_root_components(tmp_path: Path, segment: str) -> None:
    root, views = make_views(tmp_path)
    (views / "page").write_text("source")
    target = root / ("mvc" if segment == "mvc" else "mvc/views")
    external = tmp_path / "external"
    target.rename(external)
    target.symlink_to(external, target_is_directory=True)
    if segment == "mvc":
        with pytest.raises(NotForgeProjectError):
            read_templates(root)
    else:
        result = read_templates(root)
        assert result.templates == () and result.source_present
        assert result.issues[0].code == "template.unreadable"
    with pytest.raises((NotForgeProjectError, SourceReadError)):
        read_template_source(root, "page")


@pytest.mark.parametrize("count", [3, 4])
def test_file_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    monkeypatch.setattr(templates, "MAX_TEMPLATE_FILES", 3)
    root, views = make_views(tmp_path)
    for i in range(count):
        (views / f"{i}.html").touch()
    result = read_templates(root)
    assert len(result.templates) == 3
    assert result.truncated == (count > 3)
    assert len(result.issues) == int(count > 3)
    if result.issues:
        assert result.issues[0].code == "template.analysis_truncated"


@pytest.mark.parametrize("count", [4, 5])
def test_entries_include_ignored_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    monkeypatch.setattr(templates, "MAX_TEMPLATE_DIRECTORY_ENTRIES", 4)
    root, views = make_views(tmp_path)
    for i in range(count):
        (views / f".ignored{i}").touch()
    result = read_templates(root)
    assert not result.templates and result.truncated == (count > 4)


def test_depth_and_global_entry_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    monkeypatch.setattr(templates, "MAX_TEMPLATE_SCAN_DEPTH", 2)
    (views / "a/b").mkdir(parents=True)
    (views / "a/b/page").touch()
    assert not read_templates(root).truncated
    (views / "a/b/c").mkdir()
    (views / "a/b/c/deep").touch()
    result = read_templates(root)
    assert result.truncated and [t.path for t in result.templates] == ["a/b/page"]
    monkeypatch.setattr(templates, "MAX_TEMPLATE_DIRECTORY_ENTRIES", 2)
    result = read_templates(root)
    assert result.truncated and not result.templates


@pytest.mark.parametrize(
    "data",
    [
        b"",
        "été 😀 sans newline".encode(),
        b"\xef\xbb\xbfbonjour",
        b"x" * MAX_SOURCE_BYTES,
        b'{% extends "base" %}{% include "nav" %}{{ dangerous_call() }}{% if',
    ],
)
def test_raw_source(tmp_path: Path, data: bytes) -> None:
    root, views = make_views(tmp_path)
    path = views / "page"
    path.write_bytes(data)
    result = read_template_source(root, "page")
    assert result.path == "page" and result.size == len(data)
    assert result.modified_ns == path.stat().st_mtime_ns
    assert result.text == data.decode("utf-8-sig")
    with pytest.raises(FrozenInstanceError):
        setattr(result, "text", "changed")


@pytest.mark.parametrize("data", [b"\xff", b"x" * (MAX_SOURCE_BYTES + 1)])
def test_unreadable_source(tmp_path: Path, data: bytes) -> None:
    root, views = make_views(tmp_path)
    (views / "page").write_bytes(data)
    assert read_templates(root).templates[0].size == len(data)
    with pytest.raises(SourceReadError):
        read_template_source(root, "page")


@pytest.mark.parametrize(
    "path",
    [
        "",
        "..",
        "../secret",
        "/absolute",
        "a/../secret",
        "a//b",
        "a\\b",
        "a:b",
        "a\x00b",
        "x" * 4096,
    ],
)
def test_invalid_path_before_root(tmp_path: Path, path: str) -> None:
    with pytest.raises(SourceReadError):
        read_template_source(tmp_path / "absent", path)


@pytest.mark.parametrize("target", ["page", "sub", "views"])
def test_replacement_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    root, views = make_views(tmp_path)
    (views / "page").write_text("old")
    (views / "sub").mkdir()
    (views / "sub/page").write_text("old")
    original = os.open
    replaced = False

    def raced(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal replaced
        if path == target and dir_fd is not None and not replaced:
            replaced = True
            file = views if target == "views" else views / target
            file.rename(file.with_name(file.name + "-old"))
            if target == "page":
                file.write_text("new")
            else:
                file.mkdir()
                (file / "new").touch()
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", raced)
    result = read_templates(root)
    assert replaced and any(i.code == "template.unreadable" for i in result.issues)
    assert not any(t.path.endswith("new") for t in result.templates)


def test_source_replacement_and_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    file = views / "page"
    file.write_text("old")
    original = os.stat
    replaced = False

    def raced(
        path: str | bytes | int | os.PathLike[str] | os.PathLike[bytes],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal replaced
        result = original(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)
        if path == "page" and dir_fd is not None and not replaced:
            replaced = True
            file.rename(views / "old")
            file.write_text("new")
        return result

    monkeypatch.setattr(os, "stat", raced)
    with pytest.raises(SourceReadError, match="remplacée"):
        read_template_source(root, "page")
    monkeypatch.undo()
    original_fstat = os.fstat
    count = 0

    def mutate(fd: int) -> os.stat_result:
        nonlocal count
        result = original_fstat(fd)
        if result.st_ino == file.stat().st_ino:
            count += 1
            if count == 2:
                file.write_text("different")
                return original_fstat(fd)
        return result

    monkeypatch.setattr(os, "fstat", mutate)
    with pytest.raises(SourceReadError, match="modifiée"):
        read_template_source(root, "page")


def test_production_limits(tmp_path: Path) -> None:
    assert templates.MAX_TEMPLATE_FILES == 512
    assert templates.MAX_TEMPLATE_DIRECTORY_ENTRIES == 4096
    assert templates.MAX_TEMPLATE_SCAN_DEPTH == 32
    root, views = make_views(tmp_path)
    for i in range(512):
        (views / f"{i:04}.html").touch()
    assert len(read_templates(root).templates) == 512
    assert not read_templates(root).truncated
    (views / "extra").touch()
    result = read_templates(root)
    assert len(result.templates) == 512 and result.truncated
    deep = views
    for _ in range(32):
        deep = deep / "d"
        deep.mkdir()
    (deep / "page").touch()
    # Profondeur isolée de la borne fichiers.
    for file in views.glob("*.html"):
        file.unlink()
    assert not read_templates(root).truncated
    (deep / "over").mkdir()
    assert read_templates(root).truncated


def test_local_failure_keeps_other_templates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    (views / "bad").touch()
    (views / "good").touch()
    original = os.open

    def denied(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == "bad" and dir_fd is not None:
            raise PermissionError("denied")
        return original(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", denied)
    result = read_templates(root)
    assert [t.path for t in result.templates] == ["good"]
    assert result.issues == (
        templates.TemplateIssue(
            "template.unreadable", "Template ou dossier inaccessible.", "bad"
        ),
    )
