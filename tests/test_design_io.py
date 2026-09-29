"""I/O design réelles, confinement, conflits optimistes et non-écriture collatérale."""

import hashlib
import json
import os
import socket
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from test_templates import make_views

from forge_design.design import (
    DesignFile,
    DesignWriteConflictError,
    DesignWriteError,
    InvalidDesignForWriteError,
    design_source,
    io,
    read_design,
    write_design,
)
from forge_design.forge import source
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceReadError
from forge_design.limits import MAX_DESIGN_NODES, MAX_SOURCE_BYTES

FIXTURES = Path(__file__).parent / "fixtures/design"


def model(name: str = "minimal") -> DesignFile:
    return DesignFile.model_validate_json(
        (FIXTURES / (name + ".design.json")).read_text()
    )


def snapshot(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), path.stat().st_mtime_ns


@pytest.mark.parametrize("name", ["minimal", "contacts-list"])
def test_round_trip_and_sentinels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    root, views = make_views(tmp_path)
    xdg = tmp_path / "xdg"
    xdg.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    sentinels = [views / "list.html", views / "list.view.json", xdg / "preferences"]
    for path in sentinels:
        path.write_text("SENTINELLE é")
    before = [snapshot(path) for path in sentinels]
    for filename in ("app.py", "config.py", "mvc/controllers/hostile.py"):
        path = root / filename
        path.parent.mkdir(exist_ok=True)
        path.write_text("raise RuntimeError('must not import')")
    original = model(name)
    result = write_design(root, "é.design.json", original, expected_revision=None)
    assert result.created
    data = (views / "é.design.json").read_bytes()
    assert (
        not data.startswith(b"\xef\xbb\xbf")
        and data.endswith(b"\n")
        and not data.endswith(b"\n\n")
    )
    assert result.revision.digest == hashlib.sha256(data).hexdigest()
    read = read_design(root, "é.design.json")
    assert (
        read.issues == ()
        and read.revision == result.revision
        and read.design is not None
    )
    assert read.design.model_dump(exclude_unset=True) == original.model_dump(
        exclude_unset=True
    )
    again = write_design(
        root, "é.design.json", read.design, expected_revision=read.revision
    )
    assert not again.created and (views / "é.design.json").read_bytes() == data
    changed = DesignFile.model_validate(
        original.model_dump(exclude_unset=True) | {"view": "modifié"}
    )
    updated = write_design(
        root, "é.design.json", changed, expected_revision=again.revision
    )
    assert updated.revision != again.revision
    reread = read_design(root, "é.design.json")
    assert reread.design == changed and reread.revision == updated.revision
    assert [snapshot(path) for path in sentinels] == before
    assert not list(views.glob(".forge-design-write-*"))
    assert not (root / ".forge-design").exists()
    with pytest.raises(FrozenInstanceError):
        result.created = False  # type: ignore[misc]


@pytest.mark.parametrize(
    "reference",
    [
        "design.json",
        ".design.json",
        "foo.DESIGN.json",
        "foo.design.JSON",
        "foo.design.json.bak",
        "foo.json",
        "../x.design.json",
        "../../outside.design.json",
        "/absolute.design.json",
        ".hidden/x.design.json",
        "a\\b.design.json",
        "a:b.design.json",
        "a\x00.design.json",
        "env/x.design.json",
        "id_rsa.design.json",
        "cert.pem/x.design.json",
        "a.key/x.design.json",
        "mvc/views/a.design.json",
        "a//b.design.json",
    ],
)
def test_lexical_refusal(tmp_path: Path, reference: str) -> None:
    assert design_source(reference) is None
    with pytest.raises(SourceReadError):
        read_design(tmp_path, reference)
    with pytest.raises(SourceReadError):
        write_design(tmp_path, reference, model(), expected_revision=None)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "reference", ["a.design.json", "contacts/list.design.json", "équipe/😀.design.json"]
)
def test_sources(reference: str) -> None:
    location = design_source(reference)
    assert location is not None and location.path == "mvc/views/" + reference


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"{", "design.json_invalid"),
        (b'{"a":1,"a":2}', "design.json_invalid"),
        (b'{"nested":{"a":1,"a":2}}', "design.json_invalid"),
        (b'{"a":NaN}', "design.json_invalid"),
        (b'{"a":Infinity}', "design.json_invalid"),
        (b'{"a":-Infinity}', "design.json_invalid"),
        (b"{/*comment*/}", "design.json_invalid"),
        (b'{"a":1,}', "design.json_invalid"),
        (b"{}", "design.validation_error"),
        (b"\xff", "design.unreadable"),
        (b"[" * 10000 + b"]" * 10000, "design.json_invalid"),
    ],
)
def test_invalid_read_metadata(tmp_path: Path, raw: bytes, code: str) -> None:
    root, views = make_views(tmp_path)
    path = views / "a.design.json"
    path.write_bytes(raw)
    before = snapshot(path)
    result = read_design(root, path.name)
    assert result.design is None and result.issues[0].code == code
    assert result.size == len(raw) and result.modified_ns == path.stat().st_mtime_ns
    assert (
        result.revision is not None
        and result.revision.digest == hashlib.sha256(raw).hexdigest()
    )
    assert snapshot(path) == before


def test_bom_nesting_and_locations(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    path = views / "a.design.json"
    data = model().model_dump(exclude_unset=True)
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(data).encode())
    assert read_design(root, path.name).issues == ()
    data["root"]["children"] = [{"type": "button"}]
    path.write_text(json.dumps(data))
    result = read_design(root, path.name)
    assert result.design is not None
    issue = result.issues[0]
    assert (
        issue.code,
        issue.path,
        issue.location,
        issue.parent_type,
        issue.child_type,
    ) == (
        "design.nesting_error",
        path.name,
        ("root", "children", 0),
        "page",
        "button",
    )
    data["root"]["children"] = [{"type": "unknown"}]
    path.write_text(json.dumps(data))
    result = read_design(root, path.name)
    assert result.design is None
    assert result.issues[0].location == ("root", "children", 0, "type")


def test_nesting_truncation(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    data = model().model_dump(exclude_unset=True)
    data["root"]["children"] = [{"type": "section"}] * MAX_DESIGN_NODES
    (views / "a.design.json").write_text(json.dumps(data))
    result = read_design(root, "a.design.json")
    assert (
        result.design is not None
        and result.issues[-1].code == "design.analysis_truncated"
    )
    with pytest.raises(InvalidDesignForWriteError):
        write_design(root, "b.design.json", result.design, expected_revision=None)
    assert not (views / "b.design.json").exists()


def test_missing_and_project(tmp_path: Path) -> None:
    with pytest.raises(NotForgeProjectError):
        read_design(tmp_path, "a.design.json")
    with pytest.raises(NotForgeProjectError):
        write_design(tmp_path, "a.design.json", model(), expected_revision=None)
    root, views = make_views(tmp_path)
    with pytest.raises(FileNotFoundError):
        read_design(root, "a.design.json")
    with pytest.raises(DesignWriteError):
        write_design(root, "absent/a.design.json", model(), expected_revision=None)
    assert not (views / "absent").exists()


@pytest.mark.parametrize(
    "kind", ["large", "symlink", "parent", "fifo", "directory", "socket"]
)
def test_unsafe_sources(tmp_path: Path, kind: str) -> None:
    root, views = make_views(tmp_path)
    path = views / "a.design.json"
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "a.design.json"
    target.write_text("sentinel")
    sock = None
    if kind == "large":
        path.write_bytes(b" " * (MAX_SOURCE_BYTES + 1))
    elif kind == "symlink":
        path.symlink_to(target)
    elif kind == "parent":
        (views / "linked").symlink_to(outside, target_is_directory=True)
        path = views / "linked/a.design.json"
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "directory":
        path.mkdir()
    else:
        sock = socket.socket(socket.AF_UNIX)
        sock.bind(str(path))
    try:
        reference = path.relative_to(views).as_posix()
        result = read_design(root, reference)
        assert result.design is None and result.issues[0].code == "design.unreadable"
        assert result.revision is None
        with pytest.raises(DesignWriteError):
            write_design(root, reference, model(), expected_revision=None)
        assert target.read_text() == "sentinel"
    finally:
        if sock is not None:
            sock.close()


@pytest.mark.parametrize(
    "change",
    ["exists", "content", "mtime", "same_size", "removed", "symlink", "replaced"],
)
def test_conflicts(tmp_path: Path, change: str) -> None:
    root, views = make_views(tmp_path)
    path = views / "a.design.json"
    written = write_design(root, path.name, model(), expected_revision=None)
    outside = tmp_path / "outside.design.json"
    outside.write_text("sentinel")
    expected = written.revision
    if change == "exists":
        expected = None
    elif change == "content":
        path.write_text("external")
    elif change == "mtime":
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1000000))
    elif change == "same_size":
        content, stamp = snapshot(path)
        path.write_bytes(content.replace(b"0.1", b"0.2"))
        os.utime(path, ns=(path.stat().st_atime_ns, stamp))
    elif change == "removed":
        path.unlink()
    elif change == "symlink":
        path.unlink()
        path.symlink_to(outside)
    else:
        content, stamp = snapshot(path)
        replacement = views / "replacement"
        replacement.write_bytes(content)
        os.utime(replacement, ns=(stamp, stamp))
        os.replace(replacement, path)
    before = snapshot(path) if path.exists() else None
    with pytest.raises(DesignWriteConflictError):
        write_design(root, path.name, model(), expected_revision=expected)
    assert (snapshot(path) if path.exists() else None) == before
    assert outside.read_text() == "sentinel"
    assert not list(views.glob(".forge-design-write-*"))


@pytest.mark.parametrize("mutation", ["key", "nan", "nesting", "oversize", "cycle"])
def test_mutation_revalidation(tmp_path: Path, mutation: str) -> None:
    root, views = make_views(tmp_path)
    original = model()
    payload = original.model_dump(exclude_unset=True)
    payload["root"]["props"] = {}
    mutated = DesignFile.model_validate(payload)
    assert mutated.root.props is not None
    if mutation == "key":
        mutated.root.props[""] = "x"
    elif mutation == "nan":
        mutated.root.props["x"] = float("nan")
    elif mutation == "oversize":
        mutated.root.props["x"] = "é" * MAX_SOURCE_BYTES
    else:
        from forge_design.design import DesignNode

        node = DesignNode(type="button", children=[])
        mutated.root.children.append(node)
        if mutation == "cycle":
            assert node.children is not None
            node.children.append(node)
    result = write_design(root, "a.design.json", original, expected_revision=None)
    before = snapshot(views / "a.design.json")
    with pytest.raises(InvalidDesignForWriteError):
        write_design(root, "a.design.json", mutated, expected_revision=result.revision)
    assert snapshot(views / "a.design.json") == before
    assert sorted(p.name for p in views.iterdir()) == ["a.design.json"]


@pytest.mark.parametrize("failure", ["write", "fsync", "replace"])
def test_failure_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    root, views = make_views(tmp_path)
    result = write_design(root, "a.design.json", model(), expected_revision=None)
    before = snapshot(views / "a.design.json")

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("simulated")

    monkeypatch.setattr(io.os, failure, fail)
    with pytest.raises(DesignWriteError):
        write_design(root, "a.design.json", model(), expected_revision=result.revision)
    assert snapshot(views / "a.design.json") == before
    assert sorted(p.name for p in views.iterdir()) == ["a.design.json"]


def test_mode_hardlink_and_exclusive_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    first = write_design(root, "a.design.json", model(), expected_revision=None)
    path = views / "a.design.json"
    os.chmod(path, 0o640)
    os.link(path, views / "old-inode")
    read = read_design(root, path.name)
    old = snapshot(views / "old-inode")
    write_design(
        root, path.name, model("contacts-list"), expected_revision=read.revision
    )
    assert path.stat().st_mode & 0o777 == 0o640
    assert snapshot(views / "old-inode") == old
    assert path.stat().st_ino != (views / "old-inode").stat().st_ino

    def collision(count: int) -> str:
        return "collision"

    monkeypatch.setattr(io.secrets, "token_hex", collision)
    temp = views / ".forge-design-write-collision"
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("untouched")
    temp.symlink_to(sentinel)
    with pytest.raises(DesignWriteConflictError):
        write_design(root, "new.design.json", model(), expected_revision=None)
    assert temp.is_symlink() and sentinel.read_text() == "untouched"
    assert not (views / "new.design.json").exists()
    assert first.created


def test_mutation_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, views = make_views(tmp_path)
    write_design(root, "a.design.json", model(), expected_revision=None)
    path = views / "a.design.json"
    original = source.os.fstat
    calls = 0

    def mutate(fd: int) -> os.stat_result:
        nonlocal calls
        metadata = original(fd)
        if metadata.st_ino == path.stat().st_ino:
            calls += 1
            if calls == 2:
                path.write_text("changed during read")
                return original(fd)
        return metadata

    monkeypatch.setattr(source.os, "fstat", mutate)
    result = read_design(root, path.name)
    assert result.issues[0].code == "design.unreadable" and result.revision is None


def test_late_revision_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, views = make_views(tmp_path)
    written = write_design(root, "a.design.json", model(), expected_revision=None)
    path = views / "a.design.json"
    original = io.os.fsync

    def alter(fd: int) -> None:
        original(fd)
        path.write_text("external after preparation")

    monkeypatch.setattr(io.os, "fsync", alter)
    with pytest.raises(DesignWriteConflictError):
        write_design(root, path.name, model(), expected_revision=written.revision)
    assert path.read_text() == "external after preparation"
    assert not list(views.glob(".forge-design-write-*"))


def test_unavailable_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, views = make_views(tmp_path)
    monkeypatch.setattr(io, "_secure_write_available", lambda: False)
    with pytest.raises(DesignWriteError):
        write_design(root, "a.design.json", model(), expected_revision=None)
    assert list(views.iterdir()) == []


def test_no_descriptor_leaks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not Path("/proc/self/fd").exists():
        pytest.skip("/proc/self/fd unavailable")
    root, views = make_views(tmp_path)
    before = len(list(Path("/proc/self/fd").iterdir()))
    for _ in range(3):
        created = write_design(root, "a.design.json", model(), expected_revision=None)
        read_design(root, "a.design.json")
        write_design(root, "a.design.json", model(), expected_revision=created.revision)
        with pytest.raises(DesignWriteConflictError):
            write_design(root, "a.design.json", model(), expected_revision=None)
        (views / "a.design.json").unlink()

    def fail(*args: Any) -> Any:
        raise OSError("fsync failure")

    monkeypatch.setattr(io.os, "fsync", fail)
    with pytest.raises(DesignWriteError):
        write_design(root, "a.design.json", model(), expected_revision=None)
    assert len(list(Path("/proc/self/fd").iterdir())) == before
    assert list(views.iterdir()) == []


def test_exclusive_publication_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    original = io.os.link

    def raced(src: str, dst: str, **kwargs: Any) -> None:
        (views / dst).write_text("concurrent creator")
        original(src, dst, **kwargs)

    # Le wrapper instrumenté garde les capacités du vrai syscall.
    monkeypatch.setattr(io, "_secure_write_available", lambda: True)
    monkeypatch.setattr(io.os, "link", raced)
    with pytest.raises(DesignWriteConflictError):
        write_design(root, "a.design.json", model(), expected_revision=None)
    assert (views / "a.design.json").read_text() == "concurrent creator"
    assert not list(views.glob(".forge-design-write-*"))


def test_partial_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _ = make_views(tmp_path)
    original = io.os.write

    def partial(fd: int, data: Any) -> int:
        return original(fd, data[:7])

    monkeypatch.setattr(io.os, "write", partial)
    written = write_design(root, "a.design.json", model(), expected_revision=None)
    result = read_design(root, "a.design.json")
    assert result.design == model() and result.revision == written.revision


def test_zero_write_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, views = make_views(tmp_path)

    def zero(fd: int, data: Any) -> int:
        return 0

    monkeypatch.setattr(io.os, "write", zero)
    with pytest.raises(DesignWriteError):
        write_design(root, "a.design.json", model(), expected_revision=None)
    assert list(views.iterdir()) == []


def test_directory_fsync_failure_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, views = make_views(tmp_path)
    original = io.os.fsync
    calls = 0

    def fail_second(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory sync failed")
        original(fd)

    monkeypatch.setattr(io.os, "fsync", fail_second)
    with pytest.raises(DesignWriteError):
        write_design(root, "a.design.json", model(), expected_revision=None)
    assert read_design(root, "a.design.json").design == model()
    assert not list(views.glob(".forge-design-write-*"))


def test_invalid_write_before_any_write_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid = DesignFile.model_validate(
        model().model_dump(exclude_unset=True)
        | {
            "root": {"type": "page", "children": [{"type": "button"}]},
        }
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("filesystem reached before validation")

    monkeypatch.setattr(io, "_root", forbidden)
    with pytest.raises(InvalidDesignForWriteError) as caught:
        write_design(tmp_path, "a.design.json", invalid, expected_revision=None)
    assert caught.value.issues[0].code == "design.nesting_error"


def test_validation_diagnostics_bounded(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    data = model().model_dump(exclude_unset=True)
    data["root"]["children"] = [{"type": "unknown"}] * 600
    (views / "a.design.json").write_text(json.dumps(data))
    result = read_design(root, "a.design.json")
    assert result.design is None and len(result.issues) == 512
    assert result.issues[-1].code == "design.analysis_truncated"
