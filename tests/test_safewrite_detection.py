"""Snapshots réels, matrice pure de changement et refus des cibles non sûres."""

import errno
import hashlib
import os
import socket
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from test_templates import make_views

from forge_design.app import create_tool_registry
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.source import SourceReadError
from forge_design.limits import MAX_SOURCE_BYTES
from forge_design.safewrite import (
    TemplateChangeResult,
    TemplateRevision,
    TemplateSnapshot,
    TemplateSnapshotError,
    compare_template_snapshots,
    detect_template_change,
    detection,
    snapshot_template,
)

PATH = "mvc/views/example/index.html"
REVISION = TemplateRevision(3, 10, "a" * 64, 1, 2, 20)


def present(revision: TemplateRevision = REVISION) -> TemplateSnapshot:
    return TemplateSnapshot(PATH, True, revision)


ABSENT = TemplateSnapshot(PATH, False, None)


def make_template(tmp_path: Path, data: bytes = b"<p>{{ x }}</p>\n") -> Path:
    root, views = make_views(tmp_path)
    target = views / "example/index.html"
    target.parent.mkdir()
    target.write_bytes(data)
    return root


def replace_file(target: Path, data: bytes) -> None:
    """Nouveau fichier (nouvel inode) publié sous le même nom."""
    temporary = target.with_name(".replacement")
    temporary.write_bytes(data)
    os.replace(temporary, target)


# Matrice pure, sans filesystem.


@pytest.mark.parametrize(
    ("expected", "current", "status"),
    [
        (ABSENT, ABSENT, "unchanged"),
        (ABSENT, present(), "created"),
        (present(), ABSENT, "deleted"),
        (present(), present(), "unchanged"),
        (present(), present(TemplateRevision(3, 10, "b" * 64, 1, 2, 20)), "modified"),
        (present(), present(TemplateRevision(3, 10, "a" * 64, 1, 3, 20)), "modified"),
        (present(), present(TemplateRevision(3, 10, "a" * 64, 9, 2, 20)), "modified"),
        (present(), present(TemplateRevision(3, 10, "a" * 64, 1, 2, 21)), "modified"),
        (present(), present(TemplateRevision(3, 11, "a" * 64, 1, 2, 20)), "modified"),
    ],
)
def test_pure_matrix(
    expected: TemplateSnapshot, current: TemplateSnapshot, status: str
) -> None:
    assert compare_template_snapshots(expected, current) == status
    assert compare_template_snapshots(expected, current) == status


def test_pure_different_paths() -> None:
    other = TemplateSnapshot("mvc/views/other.html", False, None)
    with pytest.raises(ValueError):
        compare_template_snapshots(ABSENT, other)


@pytest.mark.parametrize(("exists", "revision"), [(True, None), (False, REVISION)])
def test_inconsistent_snapshot_refused(
    exists: bool, revision: TemplateRevision | None
) -> None:
    with pytest.raises(ValueError):
        TemplateSnapshot(PATH, exists, revision)


def test_frozen() -> None:
    snapshot = present()
    with pytest.raises(FrozenInstanceError):
        snapshot.exists = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        REVISION.digest = "x"  # type: ignore[misc]
    result = TemplateChangeResult(PATH, "unchanged", snapshot, snapshot)
    with pytest.raises(FrozenInstanceError):
        result.status = "modified"  # type: ignore[misc]


# Snapshots réels.


def test_nominal_snapshot(tmp_path: Path) -> None:
    data = b"<p>{{ x }}</p>\n"
    root = make_template(tmp_path, data)
    target = root / PATH
    before = target.stat()
    snapshot = snapshot_template(root, PATH)
    assert snapshot.path == PATH and snapshot.exists
    assert snapshot.revision == TemplateRevision(
        len(data),
        before.st_mtime_ns,
        hashlib.sha256(data).hexdigest(),
        before.st_dev,
        before.st_ino,
        before.st_ctime_ns,
    )
    assert target.read_bytes() == data
    assert target.stat().st_mtime_ns == before.st_mtime_ns
    assert not (root / ".forge-design").exists()


@pytest.mark.parametrize(
    "path", [PATH, "mvc/views/missing/index.html", "mvc/views/index.html"]
)
def test_absent_snapshot(tmp_path: Path, path: str) -> None:
    root, _ = make_views(tmp_path)
    assert snapshot_template(root, path) == TemplateSnapshot(path, False, None)


def test_unchanged(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    expected = snapshot_template(root, PATH)
    result = detect_template_change(root, expected)
    assert result == TemplateChangeResult(PATH, "unchanged", expected, expected)


def test_modified_content(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    expected = snapshot_template(root, PATH)
    (root / PATH).write_bytes(b"<p>edited</p>\n")
    result = detect_template_change(root, expected)
    assert result.status == "modified"
    assert result.expected is expected
    assert result.current.revision is not None
    assert result.current.revision.digest != (expected.revision or REVISION).digest


def test_created(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    expected = snapshot_template(root, PATH)
    (views / "example").mkdir()
    (root / PATH).write_bytes(b"external")
    result = detect_template_change(root, expected)
    assert result.status == "created" and result.current.exists


def test_deleted(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    expected = snapshot_template(root, PATH)
    (root / PATH).unlink()
    result = detect_template_change(root, expected)
    assert result.status == "deleted"
    assert result.current == TemplateSnapshot(PATH, False, None)


def test_same_bytes_replacement_is_modified(tmp_path: Path) -> None:
    data = b"<p>same</p>\n"
    root = make_template(tmp_path, data)
    expected = snapshot_template(root, PATH)
    # Garder l'ancien inode vivant évite sa réutilisation immédiate.
    keep = tmp_path / "kept"
    os.link(root / PATH, keep)
    replace_file(root / PATH, data)
    result = detect_template_change(root, expected)
    assert result.status == "modified"
    assert expected.revision is not None and result.current.revision is not None
    assert result.current.revision.digest == expected.revision.digest
    assert result.current.revision.inode != expected.revision.inode


def test_restored_mtime_is_modified(tmp_path: Path) -> None:
    root = make_template(tmp_path, b"<p>aaaa</p>\n")
    target = root / PATH
    original = target.stat()
    expected = snapshot_template(root, PATH)
    with target.open("r+b") as stream:
        stream.write(b"<p>bbbb</p>\n")
    os.utime(target, ns=(original.st_atime_ns, original.st_mtime_ns))
    result = detect_template_change(root, expected)
    assert result.current.revision is not None and expected.revision is not None
    assert result.current.revision.modified_ns == expected.revision.modified_ns
    assert result.current.revision.size == expected.revision.size
    assert result.status == "modified"


def test_unicode_and_binary(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    data = bytes(range(256)) * 4
    (views / "élèves").mkdir()
    (views / "élèves/liste.html").write_bytes(data)
    snapshot = snapshot_template(root, "mvc/views/élèves/liste.html")
    assert snapshot.revision is not None
    assert snapshot.revision.digest == hashlib.sha256(data).hexdigest()
    assert snapshot.revision.size == len(data)


def test_size_limit(tmp_path: Path) -> None:
    root = make_template(tmp_path, b"x" * MAX_SOURCE_BYTES)
    assert snapshot_template(root, PATH).exists
    (root / PATH).write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


# Chemins et racines.


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "C:\\views\\index.html",
        "../index.html",
        "mvc/views/../index.html",
        "mvc/views/./index.html",
        "mvc/views//index.html",
        "mvc/views/.hidden/index.html",
        "mvc/views/.index.html",
        "mvc/views/env/index.html",
        "mvc/views/index.txt",
        "mvc/views/index.design.json",
        "mvc/views/index.view.json",
        "mvc/views/.html",
        "mvc/views/",
        "mvc/views",
        "mvc/controllers/index.html",
        "views/index.html",
        "mvc/views/a\x00.html",
        "",
    ],
)
def test_invalid_paths_before_io(tmp_path: Path, path: str) -> None:
    with pytest.raises(SourceReadError):
        snapshot_template(tmp_path / "does-not-exist", path)


def test_not_a_forge_project(tmp_path: Path) -> None:
    with pytest.raises(NotForgeProjectError):
        snapshot_template(tmp_path, PATH)


def test_project_code_not_imported(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    for filename in ("app.py", "config.py", "mvc/controllers/hostile.py"):
        path = root / filename
        path.parent.mkdir(exist_ok=True)
        path.write_text("raise RuntimeError('must not import')")
    assert snapshot_template(root, PATH).exists


# Cibles non sûres : jamais prises pour une absence.


def test_symlink_template(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    outside = tmp_path / "outside.html"
    outside.write_bytes(b"secret")
    (views / "example").mkdir()
    (root / PATH).symlink_to(outside)
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_dangling_symlink_template(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    (views / "example").mkdir()
    (root / PATH).symlink_to(tmp_path / "missing.html")
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_symlink_parent(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "index.html").write_bytes(b"secret")
    (views / "example").symlink_to(outside, target_is_directory=True)
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_dangling_symlink_parent(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    (views / "example").symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_parent_is_file(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    (views / "example").write_bytes(b"not a directory")
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_fifo_without_blocking(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    (views / "example").mkdir()
    os.mkfifo(root / PATH)
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_directory(tmp_path: Path) -> None:
    root, _ = make_views(tmp_path)
    (root / PATH).mkdir(parents=True)
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_socket(tmp_path: Path) -> None:
    root, views = make_views(tmp_path)
    (views / "example").mkdir()
    # Chemin AF_UNIX court : bind relatif depuis le dossier cible.
    previous = os.getcwd()
    os.chdir(views / "example")
    try:
        with socket.socket(socket.AF_UNIX) as server:
            server.bind("index.html")
            with pytest.raises(TemplateSnapshotError):
                snapshot_template(root, PATH)
    finally:
        os.chdir(previous)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignore les permissions")
def test_permission_denied_is_not_absent(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    (root / PATH).chmod(0)
    try:
        with pytest.raises(TemplateSnapshotError) as error:
            snapshot_template(root, PATH)
        assert isinstance(error.value.__cause__, PermissionError)
    finally:
        (root / PATH).chmod(0o644)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignore les permissions")
def test_unreadable_parent_is_not_absent(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    parent = (root / PATH).parent
    parent.chmod(0)
    try:
        with pytest.raises(TemplateSnapshotError):
            snapshot_template(root, PATH)
    finally:
        parent.chmod(0o755)


# Courses simulées.


def instrument_open(monkeypatch: pytest.MonkeyPatch, before_open: Any) -> None:
    """Remplacer os.open retire la fonction de supports_dir_fd : forcer le garde."""
    original = os.open

    def raced(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if path == "index.html":
            before_open()
        return original(path, flags, *args, **kwargs)

    monkeypatch.setattr(detection, "_secure_read_available", lambda: True)
    monkeypatch.setattr(detection.os, "open", raced)


def test_replaced_between_stat_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_template(tmp_path)
    instrument_open(monkeypatch, lambda: replace_file(root / PATH, b"replacement"))
    with pytest.raises(TemplateSnapshotError, match="ouverture"):
        snapshot_template(root, PATH)


def test_symlink_swapped_between_stat_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_template(tmp_path)
    outside = tmp_path / "outside.html"
    outside.write_bytes(b"secret")

    def swap() -> None:
        (root / PATH).unlink()
        (root / PATH).symlink_to(outside)

    instrument_open(monkeypatch, swap)
    with pytest.raises(TemplateSnapshotError, match="capturer") as error:
        snapshot_template(root, PATH)
    # O_NOFOLLOW refuse le lien apparu après le stat.
    assert isinstance(error.value.__cause__, OSError)
    assert error.value.__cause__.errno == errno.ELOOP


def test_fifo_swapped_between_stat_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_template(tmp_path)

    def swap() -> None:
        (root / PATH).unlink()
        os.mkfifo(root / PATH)

    instrument_open(monkeypatch, swap)
    with pytest.raises(TemplateSnapshotError, match="ouverture"):
        snapshot_template(root, PATH)


def test_replaced_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_template(tmp_path)
    original = detection.read_source_bytes

    def raced(descriptor: int, opened: os.stat_result) -> bytes:
        data = original(descriptor, opened)
        replace_file(root / PATH, data)
        return data

    monkeypatch.setattr(detection, "read_source_bytes", raced)
    with pytest.raises(TemplateSnapshotError, match="lecture"):
        snapshot_template(root, PATH)


def test_deleted_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_template(tmp_path)
    original = detection.read_source_bytes

    def raced(descriptor: int, opened: os.stat_result) -> bytes:
        data = original(descriptor, opened)
        (root / PATH).unlink()
        return data

    monkeypatch.setattr(detection, "read_source_bytes", raced)
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_modified_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_template(tmp_path)
    original = detection.read_source_bytes

    def raced(descriptor: int, opened: os.stat_result) -> bytes:
        (root / PATH).write_bytes(b"concurrent edit, longer content")
        return original(descriptor, opened)

    monkeypatch.setattr(detection, "read_source_bytes", raced)
    with pytest.raises(TemplateSnapshotError):
        snapshot_template(root, PATH)


def test_descriptors_closed(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    os.mkfifo(root / "mvc/views/fifo.html")
    before = len(os.listdir("/proc/self/fd"))
    for _ in range(20):
        snapshot_template(root, PATH)
        snapshot_template(root, "mvc/views/missing/index.html")
        with pytest.raises(TemplateSnapshotError):
            snapshot_template(root, "mvc/views/fifo.html")
    assert len(os.listdir("/proc/self/fd")) == before


# Non-mutation et périmètre.


def test_detect_does_not_mutate(tmp_path: Path) -> None:
    root = make_template(tmp_path)
    target = root / PATH
    expected = snapshot_template(root, PATH)
    copy = TemplateSnapshot(expected.path, expected.exists, expected.revision)
    root_before = Path(root)
    before = target.read_bytes(), target.stat().st_mtime_ns
    detect_template_change(root, expected)
    assert expected == copy and root == root_before
    assert before == (target.read_bytes(), target.stat().st_mtime_ns)
    assert not (root / ".forge-design").exists()
    assert sorted(p.name for p in target.parent.iterdir()) == ["index.html"]


def test_tool_registry_unchanged() -> None:
    assert len(create_tool_registry().list()) == 5
