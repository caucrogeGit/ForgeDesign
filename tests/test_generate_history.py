"""Append JSONL : format minimal, validation préalable et fichiers ancrés."""

import errno
import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from forge_design.generate import (
    GenerationHistoryEvent,
    append_generation_history,
    history,
)

STAMP = datetime(2026, 9, 30, 11, 15, tzinfo=timezone(timedelta(hours=2)))
FILE = "mvc/views/élèves/liste.html"


def append(root: Path, **extra: Any) -> GenerationHistoryEvent:
    return append_generation_history(
        root, action="generate_template", file=FILE, timestamp=STAMP, **extra
    )


def journal(root: Path) -> Path:
    return root / ".forge-design/history.jsonl"


def test_nominal_and_permissions(tmp_path: Path) -> None:
    target = tmp_path / FILE
    target.parent.mkdir(parents=True)
    target.write_bytes(b"sentinel template")
    before = target.read_bytes(), target.stat().st_mtime_ns
    event = append(tmp_path)
    expected = (
        '{"timestamp":"2026-09-30T09:15:00Z","action":"generate_template",'
        '"file":"mvc/views/élèves/liste.html"}\n'
    ).encode()
    assert journal(tmp_path).read_bytes() == expected
    assert event == GenerationHistoryEvent(
        "2026-09-30T09:15:00Z", "generate_template", FILE
    )
    assert before == (target.read_bytes(), target.stat().st_mtime_ns)
    assert stat.S_IMODE(journal(tmp_path).stat().st_mode) == 0o600
    assert stat.S_IMODE(journal(tmp_path).parent.stat().st_mode) == 0o700
    assert set(journal(tmp_path).parent.iterdir()) == {journal(tmp_path)}
    with pytest.raises(FrozenInstanceError):
        event.file = "changed"  # type: ignore[misc]


def test_existing_append_and_mode(tmp_path: Path) -> None:
    first = append(tmp_path)
    original = journal(tmp_path).read_bytes()
    journal(tmp_path).chmod(0o640)
    second = append_generation_history(
        tmp_path,
        action="generate_template",
        file="next.html",
        timestamp=STAMP + timedelta(seconds=1),
    )
    data = journal(tmp_path).read_bytes()
    assert data.startswith(original) and data.count(b"\n") == 2
    assert [json.loads(line)["timestamp"] for line in data.splitlines()] == [
        first.timestamp,
        second.timestamp,
    ]
    assert stat.S_IMODE(journal(tmp_path).stat().st_mode) == 0o640


@pytest.mark.parametrize(
    "file",
    [
        "",
        "/etc/passwd",
        "C:\\windows\\x",
        "C:relative",
        "../x",
        "mvc/views/../secrets",
        "./mvc/views/x",
        "a//b",
        "a/",
        ".",
        "..",
        "..\\x",
        "a\\..\\b",
        "x\0",
        "x\r",
        "x\n",
        "x\t",
        "x\x7f",
        None,
        42,
    ],
)
def test_bad_paths_before_io(file: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("I/O before validation")

    monkeypatch.setattr(history, "open_directory", forbidden)
    with pytest.raises(ValueError):
        append_generation_history(
            Path("/unused"), action="generate_template", file=file, timestamp=STAMP
        )


@pytest.mark.parametrize("action", ["delete", "", None, 12])
def test_bad_action_before_io(action: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("I/O before validation")

    monkeypatch.setattr(history, "open_directory", forbidden)
    with pytest.raises(ValueError):
        append_generation_history(
            Path("/unused"), action=action, file=FILE, timestamp=STAMP
        )


def test_naive_timestamp_before_io(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_generation_history(
            tmp_path,
            action="generate_template",
            file=FILE,
            timestamp=datetime(2026, 1, 1),
        )
    assert list(tmp_path.iterdir()) == []


def test_default_clock_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            assert tz is UTC
            return STAMP.astimezone(UTC)

    monkeypatch.setattr(history, "datetime", Clock)
    event = append_generation_history(tmp_path, action="generate_template", file=FILE)
    assert event.timestamp == "2026-09-30T09:15:00Z"


def test_microseconds_and_json_escaping(tmp_path: Path) -> None:
    event = append_generation_history(
        tmp_path,
        action="generate_template",
        file='mvc/views/a"b.html',
        timestamp=STAMP.replace(microsecond=123456),
    )
    data = journal(tmp_path).read_bytes()
    assert data.count(b"\n") == 1 and not data.startswith(b"\xef\xbb\xbf")
    assert json.loads(data)["file"] == event.file
    assert event.timestamp == "2026-09-30T09:15:00.123456Z"


@pytest.mark.parametrize("kind", ["root", "ancestor", "directory", "file"])
def test_symlinks(tmp_path: Path, kind: str) -> None:
    real = tmp_path / "real"
    real.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    root = real
    if kind == "root":
        root = tmp_path / "link"
        root.symlink_to(real, target_is_directory=True)
    elif kind == "ancestor":
        (real / "project").mkdir()
        link = tmp_path / "link"
        link.symlink_to(real, target_is_directory=True)
        root = link / "project"
    elif kind == "directory":
        (real / ".forge-design").symlink_to(outside, target_is_directory=True)
    else:
        (real / ".forge-design").mkdir()
        target = outside / "sentinel"
        target.write_bytes(b"unchanged")
        journal(real).symlink_to(target)
    before = {p: p.read_bytes() for p in outside.iterdir() if p.is_file()}
    with pytest.raises(OSError):
        append(root)
    assert before == {p: p.read_bytes() for p in outside.iterdir() if p.is_file()}


@pytest.mark.parametrize("kind", ["fifo", "directory", "hardlink"])
def test_nonregular_or_linked_journal(tmp_path: Path, kind: str) -> None:
    journal(tmp_path).parent.mkdir()
    if kind == "fifo":
        os.mkfifo(journal(tmp_path))
    elif kind == "directory":
        journal(tmp_path).mkdir()
    else:
        target = tmp_path / "other"
        target.write_bytes(b"sentinel")
        os.link(target, journal(tmp_path))
    with pytest.raises(OSError):
        append(tmp_path)
    if kind == "hardlink":
        assert (tmp_path / "other").read_bytes() == b"sentinel"


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_root(tmp_path: Path, kind: str) -> None:
    root = tmp_path / kind
    if kind == "file":
        root.write_bytes(b"sentinel")
    with pytest.raises(OSError):
        append(root)


def test_event_byte_limit(tmp_path: Path) -> None:
    # ASCII permet d'ajuster le nombre d'octets sans heuristique de codepoints.
    event = GenerationHistoryEvent("2026-09-30T09:15:00Z", "generate_template", "x")
    overhead = len(history._serialize_history_event(event)) - 1  # pyright: ignore[reportPrivateUsage]
    path = "x" * (history.MAX_HISTORY_EVENT_BYTES - overhead)
    append_generation_history(
        tmp_path, action="generate_template", file=path, timestamp=STAMP
    )
    before = journal(tmp_path).read_bytes()
    assert len(before) == history.MAX_HISTORY_EVENT_BYTES
    with pytest.raises(ValueError):
        append_generation_history(
            tmp_path, action="generate_template", file=path + "x", timestamp=STAMP
        )
    assert journal(tmp_path).read_bytes() == before


def test_oversize_before_creation(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_generation_history(
            tmp_path,
            action="generate_template",
            file="é" * history.MAX_HISTORY_EVENT_BYTES,
            timestamp=STAMP,
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", ["write", "short", "fsync"])
def test_write_and_sync_failures(
    tmp_path: Path, failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    append(tmp_path)
    original = journal(tmp_path).read_bytes()
    write = os.write

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError(errno.ENOSPC, "simulated")

    def short(fd: int, data: bytes) -> int:
        return write(fd, data[:3])

    if failure == "write":
        monkeypatch.setattr(history.os, "write", fail)
    elif failure == "short":
        monkeypatch.setattr(history.os, "write", short)
    else:
        monkeypatch.setattr(history.os, "fsync", fail)
    with pytest.raises(OSError):
        append(tmp_path)
    data = journal(tmp_path).read_bytes()
    assert data.startswith(original)
    if failure == "write":
        assert data == original
    elif failure == "short":
        assert len(data) == len(original) + 3
    else:
        assert data == original * 2


def test_single_write_sync_and_closed_fd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write, sync = os.write, os.fsync
    calls: list[tuple[str, int]] = []

    def tracked_write(fd: int, data: bytes) -> int:
        calls.append(("write", fd))
        return write(fd, data)

    def tracked_sync(fd: int) -> None:
        calls.append(("sync", fd))
        sync(fd)

    monkeypatch.setattr(history.os, "write", tracked_write)
    monkeypatch.setattr(history.os, "fsync", tracked_sync)
    append(tmp_path)
    assert [kind for kind, _ in calls] == ["write", "sync", "sync", "sync"]
    assert calls[0][1] == calls[1][1]
    with pytest.raises(OSError):
        os.fstat(calls[0][1])


def test_concurrent_append(tmp_path: Path) -> None:
    def record(index: int) -> GenerationHistoryEvent:
        return append_generation_history(
            tmp_path,
            action="generate_template",
            file=f"view-{index}.html",
            timestamp=STAMP,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        events = list(pool.map(record, range(20)))
    lines = journal(tmp_path).read_bytes().splitlines()
    assert len(lines) == 20
    assert {json.loads(line)["file"] for line in lines} == {
        event.file for event in events
    }


def test_file_replacement_during_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    append(tmp_path)
    original_open = os.open

    def replaced(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if path == "history.jsonl" and not flags & os.O_CREAT:
            journal(tmp_path).rename(journal(tmp_path).with_suffix(".old"))
            journal(tmp_path).write_bytes(b"replacement")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(history.os, "open", replaced)
    with pytest.raises(OSError, match="remplacé"):
        append(tmp_path)
    assert journal(tmp_path).read_bytes() == b"replacement"


def test_directory_replacement_during_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    append(tmp_path)
    original_open = os.open
    folder = journal(tmp_path).parent

    def replaced(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if path == ".forge-design":
            folder.rename(tmp_path / "old-history")
            folder.mkdir()
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(history.os, "open", replaced)
    with pytest.raises(OSError, match="remplacé"):
        append(tmp_path)
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize("mode", [stat.S_IFSOCK, stat.S_IFCHR])
def test_nonregular_descriptor_rejected(
    tmp_path: Path,
    mode: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    append(tmp_path)
    before = journal(tmp_path).read_bytes()
    original_fstat = os.fstat

    def metadata(fd: int) -> os.stat_result:
        value = original_fstat(fd)
        if stat.S_ISREG(value.st_mode):
            fields = list(value)
            fields[0] = mode | 0o600
            return os.stat_result(fields)
        return value

    monkeypatch.setattr(history.os, "fstat", metadata)
    with pytest.raises(OSError):
        append(tmp_path)
    assert journal(tmp_path).read_bytes() == before
