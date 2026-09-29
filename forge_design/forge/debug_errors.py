"""Lecture bornée du seul journal runtime canonique, sans exécution du projet."""

import json
import os
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR, S_ISREG
from typing import BinaryIO, cast

from forge_design.forge.debug_contract import (
    DEBUG_CATEGORIES,
    DEBUG_LEVELS,
    DEBUG_SCHEMA_VERSION,
)
from forge_design.forge.debug_redaction import redact_debug_text
from forge_design.forge.filesystem import open_directory
from forge_design.forge.project_detection import detect_forge_project
from forge_design.forge.project_root import resolve_project_root
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import (
    MAX_DEBUG_EVENTS,
    MAX_DEBUG_HEADERS,
    MAX_DEBUG_ISSUES,
    MAX_DEBUG_LINE_BYTES,
    MAX_DEBUG_POST_KEYS,
    MAX_DEBUG_SCAN_BYTES,
    MAX_DEBUG_TRACEBACK_FRAMES,
)


@dataclass(frozen=True)
class DebugRequest:
    method: str | None = None
    path: str | None = None
    query: str | None = None
    post_keys: tuple[str, ...] = ()
    headers: tuple[str, ...] = ()


@dataclass(frozen=True)
class DebugFrame:
    file: str
    line: int
    function: str


@dataclass(frozen=True)
class DebugLocation(DebugFrame):
    pass


@dataclass(frozen=True)
class DebugError:
    schema_version: str
    id: str
    timestamp: str
    environment: str
    level: str
    category: str
    exception_type: str
    message: str
    safe_for_display: bool
    line_number: int
    request: DebugRequest | None = None
    location: DebugLocation | None = None
    traceback: tuple[DebugFrame, ...] = ()
    hint: str | None = None
    route: str | None = None
    controller: str | None = None
    template: str | None = None
    sql: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class DebugIssue:
    code: str
    message: str
    line_number: int | None = None


@dataclass(frozen=True)
class DebugErrorsResult:
    events: tuple[DebugError, ...] = ()
    issues: tuple[DebugIssue, ...] = ()
    source_present: bool = False
    truncated: bool = False


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError
    return cast(dict[str, object], value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError
    if len(value.encode("utf-8")) > MAX_DEBUG_LINE_BYTES:
        raise ValueError
    return value


def _optional(data: dict[str, object], key: str) -> str | None:
    return redact_debug_text(_text(data[key])) if key in data else None


def _list(value: object, limit: int) -> list[object]:
    if not isinstance(value, list):
        raise ValueError
    values = cast(list[object], value)
    if len(values) > limit:
        raise ValueError
    return values


def _frame(value: object) -> DebugFrame:
    data = _object(value)
    line = data.get("line")
    if type(line) is not int or line < 1:
        raise ValueError
    return DebugFrame(_text(data.get("file")), line, _text(data.get("function")))


def _event(data: dict[str, object], number: int) -> DebugError:
    required = (
        "schema_version",
        "id",
        "timestamp",
        "environment",
        "level",
        "category",
        "exception_type",
        "message",
    )
    texts = {key: redact_debug_text(_text(data.get(key))) for key in required}
    if texts["level"] not in DEBUG_LEVELS:
        raise ValueError
    if texts["category"] not in DEBUG_CATEGORIES:
        raise ValueError
    safe = data.get("safe_for_display")
    if not isinstance(safe, bool):
        raise ValueError
    request = None
    if "request" in data:
        req = _object(data["request"])
        request = DebugRequest(
            _optional(req, "method"),
            _optional(req, "path"),
            _optional(req, "query"),
            tuple(
                redact_debug_text(_text(v))
                for v in _list(req.get("post_keys", []), MAX_DEBUG_POST_KEYS)
            ),
            tuple(
                redact_debug_text(_text(v))
                for v in _list(req.get("headers", []), MAX_DEBUG_HEADERS)
            ),
        )
    location = None
    if "location" in data:
        frame = _frame(data["location"])
        location = DebugLocation(frame.file, frame.line, frame.function)
    return DebugError(
        **texts,
        safe_for_display=safe,
        line_number=number,
        request=request,
        location=location,
        traceback=tuple(
            _frame(v)
            for v in _list(data.get("traceback", []), MAX_DEBUG_TRACEBACK_FRAMES)
        ),
        hint=_optional(data, "hint"),
        route=_optional(data, "route"),
        controller=_optional(data, "controller"),
        template=_optional(data, "template"),
        sql=_optional(data, "sql"),
        correlation_id=_optional(data, "correlation_id"),
    )


def _reject_constant(value: str) -> object:
    raise ValueError


def _scan(stream: BinaryIO) -> DebugErrorsResult:
    events: list[DebugError] = []
    issues: list[DebugIssue] = []
    scanned = number = 0
    truncated = False
    try:
        # Réserver un emplacement pour l’unique diagnostic de troncature.
        while (
            scanned < MAX_DEBUG_SCAN_BYTES
            and len(events) < MAX_DEBUG_EVENTS
            and len(issues) < MAX_DEBUG_ISSUES - 1
        ):
            raw = stream.readline(
                min(MAX_DEBUG_LINE_BYTES + 1, MAX_DEBUG_SCAN_BYTES - scanned)
            )
            if not raw:
                break
            scanned += len(raw)
            number += 1
            if len(raw) > MAX_DEBUG_LINE_BYTES:
                issues.append(
                    DebugIssue("debug.line_too_long", "Ligne trop longue.", number)
                )
                while not raw.endswith(b"\n") and scanned < MAX_DEBUG_SCAN_BYTES:
                    raw = stream.readline(
                        min(MAX_DEBUG_LINE_BYTES + 1, MAX_DEBUG_SCAN_BYTES - scanned)
                    )
                    scanned += len(raw)
                    if not raw:
                        break
                continue
            if scanned == MAX_DEBUG_SCAN_BYTES and not raw.endswith(b"\n"):
                truncated = True
                break
            try:
                text = raw.decode("utf-8-sig" if number == 1 else "utf-8")
            except UnicodeError:
                issues.append(DebugIssue("debug.unreadable", "UTF-8 invalide.", number))
                continue
            if not text.strip():
                continue
            try:
                value: object = json.loads(text, parse_constant=_reject_constant)
            except (ValueError, RecursionError):
                issues.append(
                    DebugIssue("debug.json_invalid", "JSON invalide.", number)
                )
                continue
            try:
                data = _object(value)
                version = _text(data.get("schema_version"))
                if version != DEBUG_SCHEMA_VERSION:
                    issues.append(
                        DebugIssue(
                            "debug.schema_version_unsupported",
                            "Version de schéma non supportée.",
                            number,
                        )
                    )
                    continue
                events.append(_event(data, number))
            except (ValueError, UnicodeError, RecursionError):
                issues.append(
                    DebugIssue(
                        "debug.structure_invalid",
                        "Structure non conforme au schéma 1.0.",
                        number,
                    )
                )
        else:
            truncated = True
    except OSError:
        issues.append(
            DebugIssue(
                "debug.unreadable", "Lecture du journal interrompue.", number + 1
            )
        )
    if len(issues) >= MAX_DEBUG_ISSUES:
        issues = issues[: MAX_DEBUG_ISSUES - 1]
        truncated = True
    if truncated:
        issues.append(
            DebugIssue("debug.analysis_truncated", "Limite de lecture atteinte.")
        )
    return DebugErrorsResult(tuple(events), tuple(issues), True, truncated)


def read_debug_errors(root: Path) -> DebugErrorsResult:
    root = resolve_project_root(root)
    if not detect_forge_project(root).valid:
        raise NotForgeProjectError("La racine n’est pas un projet Forge reconnu.")
    present = False
    try:
        with ExitStack() as stack:
            parent = stack.enter_context(open_directory(str(root)))
            for name in ("storage", "logs"):
                metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if not S_ISDIR(metadata.st_mode):
                    raise OSError
                parent = stack.enter_context(open_directory(name, parent))
                if not os.path.samestat(metadata, os.fstat(parent)):
                    raise OSError
            metadata = os.stat("errors.dev.jsonl", dir_fd=parent, follow_symlinks=False)
            present = True
            if not S_ISREG(metadata.st_mode):
                raise OSError
            fd = os.open(
                "errors.dev.jsonl",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=parent,
            )
            stream = stack.enter_context(os.fdopen(fd, "rb"))
            opened = os.fstat(stream.fileno())
            if not S_ISREG(opened.st_mode) or not os.path.samestat(metadata, opened):
                raise OSError
            return _scan(stream)
    except FileNotFoundError:
        if not present:
            return DebugErrorsResult()
    except OSError:
        pass
    return DebugErrorsResult(
        issues=(DebugIssue("debug.unreadable", "Journal inaccessible ou remplacé."),),
        source_present=present,
    )
