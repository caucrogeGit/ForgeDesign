"""Contrat JSONL, masquage et confinement du lecteur runtime."""

import ast
import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_web_recent_projects import project

from forge_design.forge import debug_errors as bridge
from forge_design.forge.debug_redaction import redact_debug_text
from forge_design.forge.project_version import NotForgeProjectError


def event(**values: object) -> dict[str, object]:
    return (
        dict(
            schema_version="1.0",
            id="same",
            timestamp="2026-09-29",
            environment="dev",
            level="ERROR",
            category="runtime",
            exception_type="RuntimeError",
            message="boom",
            safe_for_display=False,
        )
        | values
    )


def journal(root: Path, content: bytes) -> Path:
    path = root / "storage/logs/errors.dev.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def encoded(**values: object) -> bytes:
    return json.dumps(event(**values)).encode() + b"\n"


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "set-cookie",
    ],
)
@pytest.mark.parametrize("value", ["sensitive", '"sensitive word"', "'sensitive word'"])
def test_redaction(key: str, value: str) -> None:
    for separator in ("=", ": "):
        assert "sensitive" not in redact_debug_text(key.upper() + separator + value)


def test_headers_url_and_false_positive() -> None:
    for header in ("Authorization: Bearer", "Cookie: session=", "Set-Cookie: session="):
        assert "secret-value" not in redact_debug_text(header + "secret-value; Other=x")
    assert redact_debug_text("?token=secret-value&foo=bar") == "?token=[masqué]&foo=bar"
    assert redact_debug_text("tokenizer failed") == "tokenizer failed"


@pytest.mark.parametrize("depth", range(4))
def test_absent_empty(tmp_path: Path, depth: int) -> None:
    root = project(tmp_path / "project")
    for path in ("storage", "storage/logs")[:depth]:
        (root / path).mkdir(exist_ok=True)
    if depth == 3:
        journal(root, b"")
    result = bridge.read_debug_errors(root)
    assert result == bridge.DebugErrorsResult(source_present=depth == 3)


def test_non_forge(tmp_path: Path) -> None:
    with pytest.raises(NotForgeProjectError):
        bridge.read_debug_errors(tmp_path)


def test_lines_and_immutable_full_model(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    frame = dict(file="password=x.py", line=2, function="token=x")
    content = encoded(
        request=dict(
            method="POST",
            path="/login",
            query="token=secret",
            post_keys=["password"],
            headers=["Authorization: Bearer secret"],
        ),
        location=frame,
        traceback=[frame, frame],
        hint="pwd=secret",
        sql="password=secret",
        route="route",
        controller="controller",
        template="template",
        correlation_id="correlation",
        extra=True,
    )
    path = journal(
        root, b"\xef\xbb\xbf" + content + b"\n{broken\n{}\n\xff\n" + encoded().rstrip()
    )
    before = (path.read_bytes(), path.stat().st_size, path.stat().st_mtime_ns)
    result = bridge.read_debug_errors(root)
    assert [v.line_number for v in result.events] == [1, 6]
    assert [v.id for v in result.events] == ["same", "same"]
    assert [v.code for v in result.issues] == [
        "debug.json_invalid",
        "debug.structure_invalid",
        "debug.unreadable",
    ]
    assert [v.line_number for v in result.issues] == [3, 4, 5]
    first = result.events[0]
    assert first.request and first.location
    assert first.request.post_keys == ("password",)
    assert first.request.query == "token=[masqué]"
    assert "secret" not in repr(first)
    assert first.location.file == "password=x.py"
    assert first.traceback[0].function == "token=x"
    assert first.safe_for_display is False
    for value in (
        result,
        first,
        first.request,
        first.location,
        first.traceback[0],
        result.issues[0],
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, next(iter(value.__dataclass_fields__)), None)
    assert before == (path.read_bytes(), path.stat().st_size, path.stat().st_mtime_ns)


@pytest.mark.parametrize("key", list(event()))
@pytest.mark.parametrize("missing", [True, False])
def test_required(tmp_path: Path, key: str, missing: bool) -> None:
    root = project(tmp_path / "project")
    value = event()
    if missing:
        del value[key]
    else:
        value[key] = 12
    journal(root, json.dumps(value).encode())
    assert bridge.read_debug_errors(root).issues[0].code == "debug.structure_invalid"


INVALID_FIELDS: list[tuple[str, object]] = [
    ("schema_version", "2.0"),
    ("level", "error"),
    ("category", "other"),
    ("request", None),
    ("request", {"headers": {"Authorization": "secret"}}),
    ("request", {"post_keys": {"password": "secret"}}),
    ("request", {"method": 42}),
    ("request", {"query": False}),
    ("location", {}),
    ("location", {"file": "x", "line": True, "function": "f"}),
    ("traceback", "text"),
    ("traceback", [{}]),
    ("hint", False),
    ("sql", []),
    ("route", None),
    ("controller", 1),
    ("template", {}),
    ("correlation_id", []),
]


@pytest.mark.parametrize("key,value", INVALID_FIELDS)
def test_invalid_structure(tmp_path: Path, key: str, value: object) -> None:
    root = project(tmp_path / "project")
    journal(root, encoded(**{key: value}) + encoded())
    result = bridge.read_debug_errors(root)
    assert len(result.events) == 1 and result.events[0].line_number == 2
    expected = (
        "schema_version_unsupported" if key == "schema_version" else "structure_invalid"
    )
    assert result.issues[0].code == "debug." + expected


@pytest.mark.parametrize("level", ["ERROR", "WARNING", "INFO", "CRITICAL"])
@pytest.mark.parametrize(
    "category",
    [
        "runtime",
        "controller",
        "routing",
        "template",
        "database",
        "configuration",
        "http",
        "unknown",
    ],
)
def test_enumerations(tmp_path: Path, level: str, category: str) -> None:
    root = project(tmp_path / "project")
    journal(root, encoded(level=level, category=category))
    result = bridge.read_debug_errors(root)
    assert (result.events[0].level, result.events[0].category) == (level, category)


@pytest.mark.parametrize("surplus", [0, 1])
def test_event_bound(tmp_path: Path, surplus: int) -> None:
    root = project(tmp_path / "project")
    journal(root, encoded() * (bridge.MAX_DEBUG_EVENTS + surplus))
    result = bridge.read_debug_errors(root)
    assert len(result.events) == bridge.MAX_DEBUG_EVENTS
    assert result.truncated and result.issues[-1].code == "debug.analysis_truncated"


def test_line_bound_and_recovery(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    line = encoded()
    exact = line[:-1] + b" " * (bridge.MAX_DEBUG_LINE_BYTES - len(line)) + b"\n"
    journal(root, exact + b"x" * (bridge.MAX_DEBUG_LINE_BYTES * 3) + b"\n" + line)
    result = bridge.read_debug_errors(root)
    assert [e.line_number for e in result.events] == [1, 3]
    assert result.issues[0].code == "debug.line_too_long"


def test_scan_bound(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    journal(root, b"\n" * (bridge.MAX_DEBUG_SCAN_BYTES + 1) + encoded())
    result = bridge.read_debug_errors(root)
    assert result.truncated and not result.events
    assert result.issues[-1].code == "debug.analysis_truncated"


@pytest.mark.parametrize(
    "part", ["storage", "storage/logs", "storage/logs/errors.dev.jsonl"]
)
def test_symlinks(tmp_path: Path, part: str) -> None:
    root = project(tmp_path / "project")
    journal(root, encoded())
    path = root / part
    moved = tmp_path / "outside"
    path.rename(moved)
    path.symlink_to(moved)
    assert bridge.read_debug_errors(root).issues[0].code == "debug.unreadable"


@pytest.mark.parametrize("kind", ["fifo", "directory"])
def test_nonregular(tmp_path: Path, kind: str) -> None:
    root = project(tmp_path / "project")
    path = journal(root, b"")
    path.unlink()
    if kind == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    assert bridge.read_debug_errors(root).issues[0].code == "debug.unreadable"


def test_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = project(tmp_path / "project")
    path = journal(root, encoded())
    original = os.open

    def replaced(
        name: str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if name == "errors.dev.jsonl":
            path.rename(path.with_suffix(".old"))
            path.write_bytes(encoded(message="replaced"))
        return original(name, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", replaced)
    assert bridge.read_debug_errors(root).issues[0].code == "debug.unreadable"


def test_no_execution() -> None:
    tree = ast.parse(Path(bridge.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"exec", "eval", "__import__"}
        if isinstance(node, ast.Import):
            assert all(n.name not in {"subprocess", "importlib"} for n in node.names)


@pytest.mark.parametrize("part", ["storage", "logs"])
def test_directory_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, part: str
) -> None:
    root = project(tmp_path / "project")
    journal(root, encoded())
    path = root / ("storage" if part == "storage" else "storage/logs")
    original = os.open

    def replaced(
        name: str, flags: int, mode: int = 0o777, *, dir_fd: int | None = None
    ) -> int:
        if name == part:
            path.rename(path.with_name(part + "-old"))
            path.mkdir()
        return original(name, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", replaced)
    assert bridge.read_debug_errors(root).issues[0].code == "debug.unreadable"


@pytest.mark.parametrize("surplus", [0, 1])
def test_scan_exact_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surplus: int
) -> None:
    root = project(tmp_path / "project")
    line = encoded()
    monkeypatch.setattr(bridge, "MAX_DEBUG_SCAN_BYTES", len(line))
    journal(root, line + b" " * surplus)
    result = bridge.read_debug_errors(root)
    assert len(result.events) == 1 and result.truncated


def test_interrupted_stream_preserves_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    journal(root, encoded())
    original = bridge._scan  # pyright: ignore[reportPrivateUsage]
    from io import BytesIO

    class Interrupted(BytesIO):
        def readline(self, size: int | None = -1) -> bytes:
            if self.tell():
                raise OSError("synthetic failure")
            return super().readline(size)

    def scan(stream: object) -> bridge.DebugErrorsResult:
        return original(Interrupted(encoded()))

    monkeypatch.setattr(bridge, "_scan", scan)
    result = bridge.read_debug_errors(root)
    assert len(result.events) == 1 and result.issues[0].code == "debug.unreadable"
