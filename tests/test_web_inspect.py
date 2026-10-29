"""Mode analyse dans l'application Web (FD-INSPECT-001, étape 2).

Même découpage que la preview réelle : runtime et proxy doubles derrière la
vraie application Web, puis le vrai runner et le vrai proxy sur le squelette
Forge rc9.
"""

import json
import re
import threading
from collections.abc import Iterator
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from real_preview_support import make_project as make_forge_project
from real_preview_support import processes_mentioning
from test_web_real_preview import (
    PROXY_PORT,
    RUNNER_PORT,
    Harness,
    Reply,
    _status,  # pyright: ignore[reportPrivateUsage]
    designed_project,
    http,
    open_project,
    serving,
)

from forge_design.web import server as web
from forge_design.web.inspect import trace_links

PROXY = f"http://127.0.0.1:{PROXY_PORT}"
IFRAME = re.compile(r'<iframe class="inspect-frame" src="([^"]+)"')


def start(
    server: web.ForgeDesignServer, *fields: tuple[str, str], **options: Any
) -> Reply:
    return http(server, "POST", "/inspect/start", list(fields), **options)


def stop(
    server: web.ForgeDesignServer, *fields: tuple[str, str], **options: Any
) -> Reply:
    return http(server, "POST", "/inspect/stop", list(fields), **options)


# ── Page et actions, runtime double ──────────────────────────────────────────


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.fixture
def server(harness: Harness) -> Iterator[web.ForgeDesignServer]:
    with serving(harness.runtime) as running:
        yield running


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return designed_project(tmp_path / "a").resolve()


def test_page_without_project(harness: Harness, server: web.ForgeDesignServer) -> None:
    status, body, _ = http(server, "GET", "/inspect")
    assert status == 200 and "Aucun projet ouvert." in body
    assert 'action="/inspect/start"' not in body
    assert start(server)[0] == 409
    assert harness.starts == []


def test_navigation_links_to_the_page(server: web.ForgeDesignServer) -> None:
    assert 'href="/inspect"' in http(server, "GET", "/")[1]
    status, script, headers = http(server, "GET", "/inspect-panel.js")
    assert status == 200 and "forge-design-inspect" in script
    assert headers["Content-Type"] == "text/javascript; charset=utf-8"


def test_reading_the_page_never_starts(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    status, body, _ = http(server, "GET", "/inspect")
    assert status == 200
    assert 'action="/inspect/start"' in body and "Lancer l" in body
    assert "real-preview-warning help-text" in body
    assert IFRAME.search(body) is None
    assert http(server, "GET", "/inspect?x=1")[0] == 400
    assert harness.starts == []


def test_start_runs_the_probes_and_frames_the_root(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    status, _, headers = start(server)
    assert (status, headers["Location"]) == (303, "/inspect")
    assert harness.starts == [("runner-start", project_root, True)]
    status, body, headers = http(server, "GET", "/inspect")
    match = IFRAME.search(body)
    assert match is not None and match.group(1) == f"{PROXY}/"
    assert f'data-proxy-origin="{PROXY}"' in body
    assert '<script type="module" src="/inspect-panel.js"></script>' in body
    assert headers["Content-Security-Policy"].endswith(f"; frame-src 'self' {PROXY}")
    assert 'action="/inspect/stop"' in body
    # Déjà en mode analyse sur ce projet : aucun redémarrage.
    assert start(server)[0] == 303
    assert len(harness.starts) == 1


def test_switching_mode_restarts_the_runner(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    harness.runtime.start(project_root)  # preview réelle ordinaire
    body = http(server, "GET", "/inspect")[1]
    assert 'action="/inspect/start"' in body and IFRAME.search(body) is None
    assert start(server)[0] == 303
    assert harness.starts == [
        ("runner-start", project_root),
        ("runner-start", project_root, True),
    ]
    # Runner ordinaire fermé (proxy puis runner) avant le runner du mode analyse.
    names = harness.names()
    assert names[names.index("proxy-create") + 1 :] == [
        "proxy-shutdown",
        "proxy-close",
        "runner-stop",
        "runner-start",
        "proxy-create",
    ]


@pytest.mark.parametrize(
    ("fields", "options", "expected"),
    [
        ((), {"origin": "http://evil.example"}, 403),
        ((), {"site": "cross-site"}, 403),
        ((), {"content_type": "text/plain"}, 415),
        ((("route", "/"),), {}, 400),
    ],
)
def test_start_refusals(
    harness: Harness,
    server: web.ForgeDesignServer,
    project_root: Path,
    fields: tuple[tuple[str, str], ...],
    options: dict[str, Any],
    expected: int,
) -> None:
    open_project(server, project_root)
    assert start(server, *fields, **options)[0] == expected
    assert stop(server, *fields, **options)[0] == expected
    assert harness.starts == []


def test_stop(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    status, _, headers = stop(server)
    assert (status, headers["Location"]) == (303, "/inspect")
    assert harness.names()[-3:] == ["proxy-shutdown", "proxy-close", "runner-stop"]
    body = http(server, "GET", "/inspect")[1]
    assert IFRAME.search(body) is None and 'action="/inspect/start"' in body


def test_failed_start_shows_the_logs(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    harness.controller.start_state = "failed"
    start(server)
    harness.controller.current = _status(
        "failed", project_root, error="boom", logs=("ligne",), inspect=True
    )
    body = http(server, "GET", "/inspect")[1]
    assert "boom" in body and "Relancer l" in body


# ── Traces ───────────────────────────────────────────────────────────────────

TRACE = {
    "id": "3",
    "route": {"pattern": "/"},
    "handler": {"qualname": "Home.index", "file": "mvc/c.py", "line": 9},
    "templates": [
        {"id": 1, "name": "home/index.html", "file": "mvc/views/home/index.html"},
        {"id": 2, "name": "x.html", "file": "optins/x.html"},
        {"id": 3, "name": "abs.html", "file": "/etc/passwd"},
        {"id": 4, "name": "up.html", "file": "mvc/../../secret"},
        {"id": "5", "name": "str.html", "file": "mvc/views/s.html"},
        {"id": 6, "name": "none.html", "file": None},
    ],
}


def test_trace_links_are_built_and_sanitized() -> None:
    assert trace_links(TRACE) == {
        "handler": "/source?path=mvc%2Fc.py&line=9",
        "templates": {
            "1": "/templates/view?path=home%2Findex.html",
            "2": "/source?path=optins%2Fx.html",
        },
    }
    assert trace_links({"handler": {"file": "a.py", "line": True}})["handler"] == (
        "/source?path=a.py"
    )
    hostile_values: tuple[object, ...] = (
        None,
        [],
        "x",
        {"handler": "x", "templates": "y"},
    )
    for hostile in hostile_values:
        assert trace_links(hostile) == {"handler": None, "templates": {}}


def test_trace_endpoint(
    harness: Harness,
    server: web.ForgeDesignServer,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[str] = []

    def fetch(trace_id: str) -> object | None:
        asked.append(trace_id)
        return TRACE if trace_id == "3" else None

    monkeypatch.setattr(harness.runtime, "fetch_trace", fetch)
    assert http(server, "GET", "/inspect/trace?id=3")[0] == 409  # aucun projet
    open_project(server, project_root)
    assert http(server, "GET", "/inspect/trace?id=3")[0] == 409  # aucun runner
    start(server)
    status, body, headers = http(server, "GET", "/inspect/trace?id=3")
    assert status == 200 and headers["Cache-Control"] == "no-store"
    payload = json.loads(body)
    assert payload["trace"] == TRACE and payload["links"] == trace_links(TRACE)
    assert http(server, "GET", "/inspect/trace?id=4")[0] == 404
    for query in ("", "?id=1&id=2", "?trace=1"):
        assert http(server, "GET", f"/inspect/trace{query}")[0] == 400
    assert asked == ["3", "4"]


class _Child(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server: Any = self.server
        server.paths.append((self.path, self.headers["Host"]))
        status, body = server.reply
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def child() -> Iterator[Any]:
    httpd: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Child)
    httpd.paths = []
    httpd.reply = (200, b'{"id": "7"}')
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def test_fetch_trace_reads_the_child(
    harness: Harness, child: Any, tmp_path: Path
) -> None:
    runtime, controller = harness.runtime, harness.controller
    port = child.server_address[1]
    controller.current = _status("running", tmp_path, port=port, inspect=True)
    assert runtime.fetch_trace("7") == {"id": "7"}
    assert child.paths == [("/__forge_design/trace/7", f"127.0.0.1:{port}")]
    for trace_id in ("", "7a", "../1", "1" * 19):
        assert runtime.fetch_trace(trace_id) is None
    for reply in ((404, b"{}"), (200, b"{"), (200, b'{"a": 1, "a": 2}'), (200, b"NaN")):
        child.reply = reply
        assert runtime.fetch_trace("7") is None
    child.reply = (200, b'{"id": "7"}')
    controller.current = _status("running", tmp_path, port=port)
    assert runtime.fetch_trace("7") is None  # pas en mode analyse
    controller.current = _status("stopped", tmp_path, port=port, inspect=True)
    assert runtime.fetch_trace("7") is None
    assert len(child.paths) == 5


def test_fetch_trace_unreachable_child(harness: Harness, tmp_path: Path) -> None:
    harness.controller.current = _status(
        "running", tmp_path, port=RUNNER_PORT, inspect=True
    )
    assert harness.runtime.fetch_trace("1") is None


# ── Bout en bout : vrai runner, vrai proxy, squelette rc9 ────────────────────


def _proxy_get(origin: str, path: str) -> tuple[int, dict[str, str], str]:
    parts = urlsplit(origin)
    assert parts.hostname == "127.0.0.1" and parts.port is not None
    connection = HTTPConnection("127.0.0.1", parts.port, timeout=15)
    try:
        connection.putrequest("GET", path, skip_host=True)
        connection.putheader("Host", parts.netloc)
        connection.endheaders()
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read().decode()
    finally:
        connection.close()


def test_real_inspect_session(tmp_path: Path) -> None:
    root = make_forge_project(tmp_path / "projet").resolve()
    with serving() as running:
        open_project(running, root)
        assert start(running)[0] == 303
        body = http(running, "GET", "/inspect")[1]
        match = re.search(r'data-proxy-origin="([^"]+)"', body)
        assert match is not None, body
        origin = match.group(1)
        status, headers, page = _proxy_get(origin, "/")
        assert status == 200
        trace_id = headers["X-Forge-Design-Trace"]
        assert (
            f'<script src="/__forge_design/inspect.js" data-trace="{trace_id}" '
            f'data-origin="http://127.0.0.1:{running.server_port}" defer></script>'
            "</body>"
        ) in page
        assert "<!--fd:b:" in page
        assert _proxy_get(origin, f"/__forge_design/trace/{trace_id}")[0] == 404
        assert _proxy_get(origin, "/__forge_design/inspect.js")[0] == 200
        status, body, _ = http(running, "GET", f"/inspect/trace?id={trace_id}")
        payload = json.loads(body)
        assert status == 200
        assert payload["trace"]["route"]["name"] == "home-index"
        assert payload["trace"]["handler"]["qualname"] == "HomeController.index"
        assert payload["links"]["handler"].startswith(
            "/source?path=mvc%2Fcontrollers%2Fhome_controller.py&line="
        )
        assert stop(running)[0] == 303
    assert processes_mentioning(str(root)) == []
