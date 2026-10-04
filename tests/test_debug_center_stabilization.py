"""Invariants transversaux de la verticale runtime stabilisée."""

import inspect
import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode

import pytest
from test_debug_errors import encoded, event, journal
from test_debug_filters import sample
from test_web_debug_detail import request
from test_web_debug_flow import foreign_scripts
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.app import create_tool_registry
from forge_design.forge import debug_errors as bridge
from forge_design.forge.debug_contract import (
    DEBUG_CATEGORIES,
    DEBUG_LEVELS,
    DEBUG_SCHEMA_VERSION,
)
from forge_design.forge.debug_redaction import redact_debug_text
from forge_design.forge.project_root import (
    ProjectRootNotDirectoryError,
    ProjectRootNotFoundError,
    ProjectRootResolutionError,
)
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import MAX_DEBUG_EVENT_ID_LENGTH
from forge_design.recent_projects import RecentProjects
from forge_design.tools.debug_center import DebugCenterTool
from forge_design.tools.debug_detail import find_debug_event
from forge_design.tools.debug_filters import (
    CATEGORIES,
    LEVELS,
    DebugFilter,
    filter_debug_events,
)
from forge_design.tools.debug_flow import build_debug_flow
from forge_design.web.debug_detail import debug_event_url, parse_debug_detail
from forge_design.web.debug_flow_layout import layout_debug_flow


def test_public_contract() -> None:
    assert LEVELS == ("all",) + DEBUG_LEVELS
    assert CATEGORIES == ("all",) + DEBUG_CATEGORIES
    assert DEBUG_SCHEMA_VERSION == "1.0"
    assert [t.id for t in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
    for function, params in (
        (bridge.read_debug_errors, ("root",)),
        (redact_debug_text, ("value",)),
        (filter_debug_events, ("result", "filters")),
        (find_debug_event, ("result", "line_number", "event_id")),
        (build_debug_flow, ("event",)),
        (layout_debug_flow, ("flow",)),
    ):
        assert tuple(inspect.signature(function).parameters) == params
    assert (
        inspect.signature(find_debug_event).parameters["line_number"].kind
        == inspect.Parameter.KEYWORD_ONLY
    )
    for cls in (
        bridge.DebugError,
        bridge.DebugRequest,
        bridge.DebugFrame,
        bridge.DebugLocation,
        bridge.DebugIssue,
        bridge.DebugErrorsResult,
        DebugFilter,
    ):
        assert getattr(getattr(cls, "__dataclass_params__"), "frozen")


@pytest.mark.parametrize("extra", [0, 1, 10000])
def test_issues_bound(tmp_path: Path, extra: int) -> None:
    root = project(tmp_path / "project")
    journal(root, b"x\n" * (bridge.MAX_DEBUG_ISSUES + extra) + encoded())
    result = bridge.read_debug_errors(root)
    assert result.truncated and not result.events
    assert len(result.issues) == bridge.MAX_DEBUG_ISSUES
    assert sum(i.code == "debug.analysis_truncated" for i in result.issues) == 1
    assert result.issues[-2].line_number == bridge.MAX_DEBUG_ISSUES - 1


@pytest.mark.parametrize(
    "field,limit",
    [
        ("traceback", bridge.MAX_DEBUG_TRACEBACK_FRAMES),
        ("post_keys", bridge.MAX_DEBUG_POST_KEYS),
        ("headers", bridge.MAX_DEBUG_HEADERS),
    ],
)
@pytest.mark.parametrize("extra", [0, 1])
def test_collection_bounds(tmp_path: Path, field: str, limit: int, extra: int) -> None:
    root = project(tmp_path / "project")
    item: object = (
        {"file": "x", "line": 1, "function": "f"} if field == "traceback" else ""
    )
    values: dict[str, object] = (
        {"traceback": [item] * (limit + extra)}
        if field == "traceback"
        else {"request": {field: [item] * (limit + extra)}}
    )
    journal(root, encoded(**values) + encoded())
    result = bridge.read_debug_errors(root)
    assert len(result.events) == 2 - extra
    assert not result.truncated
    assert [i.code for i in result.issues] == (
        ["debug.structure_invalid"] if extra else []
    )


@pytest.mark.parametrize("text", ["", "\x00\x01\x1f", "é😀", "é" * 10000])
def test_text_contract(tmp_path: Path, text: str) -> None:
    root = project(tmp_path / "project")
    data = json.dumps(event(message=text), ensure_ascii=False).encode()
    journal(root, data)
    result = bridge.read_debug_errors(root)
    assert result.events[0].message == text and not result.issues


@pytest.mark.parametrize(
    "value", [b"NaN", b"Infinity", b"-Infinity", b"[" * 10000 + b"]" * 10000]
)
def test_hostile_json(tmp_path: Path, value: bytes) -> None:
    root = project(tmp_path / "project")
    journal(root, value + b"\n" + encoded())
    result = bridge.read_debug_errors(root)
    assert result.events[0].line_number == 2
    assert result.issues[0].code == "debug.json_invalid"


def test_physical_lines_bom_and_drain(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    journal(
        root,
        b"\xef\xbb\xbf"
        + encoded()
        + b"\n"
        + b"x" * (bridge.MAX_DEBUG_LINE_BYTES + 1)
        + b"\n\xff\nx\n{}\n\xef\xbb\xbf"
        + encoded()
        + encoded(),
    )
    result = bridge.read_debug_errors(root)
    assert [e.line_number for e in result.events] == [1, 8]
    assert [i.line_number for i in result.issues] == [3, 4, 5, 6, 7]
    assert result.issues[-1].code == "debug.json_invalid"


@pytest.mark.parametrize("at_budget", [False, True])
def test_unterminated_drain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, at_budget: bool
) -> None:
    root = project(tmp_path / "project")
    monkeypatch.setattr(bridge, "MAX_DEBUG_SCAN_BYTES", 3 * bridge.MAX_DEBUG_LINE_BYTES)
    size = bridge.MAX_DEBUG_LINE_BYTES * (4 if at_budget else 2)
    journal(root, b"x" * size)
    result = bridge.read_debug_errors(root)
    assert result.truncated == at_budget
    assert [i.code for i in result.issues] == ["debug.line_too_long"] + (
        ["debug.analysis_truncated"] if at_budget else []
    )


@pytest.mark.parametrize(
    "value",
    [
        "Authorization=Bearer synthetic-secret",
        '"Authorization": "Bearer synthetic-secret"',
        'password="unfinished synthetic-secret',
        "password='unfinished synthetic-secret",
        "Cookie=session=synthetic-secret; other=synthetic-secret",
        "password=synthetic-secret token=synthetic-secret",
        "?token=synthetic-secret&api_key=synthetic-secret&foo=bar",
    ],
)
def test_redaction_regressions(value: str) -> None:
    masked = redact_debug_text(value)
    assert "synthetic-secret" not in masked
    assert redact_debug_text(masked) == masked
    assert redact_debug_text("tokenizer failed café 😀") == "tokenizer failed café 😀"


def test_structuring_redaction_choice(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    journal(root, encoded(id="token=secret-one") + encoded(id="token=secret-two"))
    result = bridge.read_debug_errors(root)
    assert result.events[0].id == result.events[1].id == "token=[masqué]"
    for item in result.events:
        url = debug_event_url(item)
        assert url
        line, event_id = parse_debug_detail(request(url.split("?", 1)[1]))
        assert find_debug_event(result, line_number=line, event_id=event_id) is item
    assert not filter_debug_events(result, DebugFilter(query="secret-one")).events
    assert result.events[0].timestamp == "2026-09-29"
    assert result.events[0].level == "ERROR" and result.events[0].category == "runtime"


@pytest.mark.parametrize("identifier", ["ASCII", "éà", "😀" * 256, ' /?&+=#" '])
def test_id_encoding(identifier: str) -> None:
    value = replace(sample(), id=identifier)
    url = debug_event_url(value)
    assert url and len(url) < 3200
    assert parse_debug_detail(request(url.split("?", 1)[1])) == (1, identifier)
    assert (
        debug_event_url(replace(value, id="x" * (MAX_DEBUG_EVENT_ID_LENGTH + 1)))
        is None
    )
    with pytest.raises(ValueError):
        parse_debug_detail(request(urlencode({"line": 1, "id": "😀" * 257})))


def test_extreme_dates_and_volume() -> None:
    dates = (
        "0001-01-01T00:00:00+23:59",
        "9999-12-31T23:59:59-23:59",
        "2026-09-29T10:00:00Z",
        "2026-09-29T12:00:00+02:00",
        "2026-09-29T09:00:00-01:00",
        "2026-09-29T10:00:00.000001+00:00",
        "10000-01-01T00:00:00Z",
        "2026-09-29T10:00:00",
        "invalid",
    )
    result = bridge.DebugErrorsResult(
        tuple(
            replace(sample(), timestamp=t, line_number=i) for i, t in enumerate(dates)
        )
    )
    ordered = filter_debug_events(result, DebugFilter()).events
    assert [e.line_number for e in ordered] == [1, 5, 2, 3, 4, 0, 6, 7, 8]
    volume = replace(
        result,
        events=tuple(
            replace(sample(), line_number=i, controller="😀e\u0301" * 10000)
            for i in range(1, 2001)
        ),
    )
    assert len(filter_debug_events(volume, DebugFilter(query="runtime")).events) == 2000
    selected = find_debug_event(volume, line_number=2000, event_id="id")
    assert selected
    flow = build_debug_flow(selected)
    layout = layout_debug_flow(flow)
    assert layout == layout_debug_flow(flow) and len(layout.nodes[0].detail) == 24
    assert layout.width == 260


@pytest.mark.parametrize(
    "error",
    [
        ProjectRootNotFoundError,
        ProjectRootNotDirectoryError,
        ProjectRootResolutionError,
        NotForgeProjectError,
    ],
)
def test_project_http_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    root = project(tmp_path / "project")

    def fail(self: DebugCenterTool, path: Path) -> bridge.DebugErrorsResult:
        raise error("project unavailable")

    monkeypatch.setattr(DebugCenterTool, "run", fail)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        for url in ("/debug", "/debug/event?line=1&id=x"):
            status, html, headers = call(app, url)
            assert status == 409 and headers["Cache-Control"] == "no-store"
            assert "project unavailable" in html and "<svg" not in html


def test_transverse_hostile_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    (root / "mvc/controllers").mkdir()
    (root / "mvc/controllers/user.py").write_text(
        "raise AssertionError('never import')"
    )
    hostile = '</text><script>url(javascript:x)</script>"><foreignObject>'
    path = journal(
        root,
        encoded(
            id="événement😀",
            route=hostile,
            controller=hostile,
            template=hostile,
            request={"path": hostile, "query": "token=hidden-secret"},
            sql="password=hidden-secret",
        )
        + b"broken\n",
    )
    calls: list[Path] = []
    original = DebugCenterTool.run

    def run(self: DebugCenterTool, path: Path) -> bridge.DebugErrorsResult:
        calls.append(path)
        return original(self, path)

    monkeypatch.setattr(DebugCenterTool, "run", run)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        for url, expected, tool_calls in (
            ("/debug", 200, 1),
            ("/debug?level=ERROR", 200, 1),
            ("/debug?level=FATAL", 400, 0),
            ("/debug/event?" + urlencode({"line": 1, "id": "événement😀"}), 200, 1),
            ("/debug/event?line=5&id=x", 404, 1),
        ):
            before = {
                p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
                for p in tmp_path.rglob("*")
                if p.is_file()
            }
            count = len(calls)
            status, html, headers = call(app, url)
            assert status == expected and headers["Cache-Control"] == "no-store"
            assert len(calls) == count + tool_calls
            assert (
                "hidden-secret" not in html
                and not foreign_scripts(html)
                and "<foreignObject" not in html
            )
            assert "script-src 'self'" in headers["Content-Security-Policy"]
            doc = SvgDocument()
            doc.feed(html)
            ids = [a["id"] for _, a in doc.tags if "id" in a]
            assert len(ids) == len(set(ids))
            assert not any(
                "style" in a or any(k.startswith("on") for k in a) for _, a in doc.tags
            )
            assert before == {
                p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
                for p in tmp_path.rglob("*")
                if p.is_file()
            }
        path.write_bytes(encoded(id="x" * 257))
        assert "/debug/event?" not in call(app, "/debug")[1]
