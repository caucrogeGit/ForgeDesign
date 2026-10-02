"""Proxy local de la preview réelle (FD-REALPREVIEW-003).

Le proxy tourne réellement (listener 127.0.0.1, thread de test) devant un
serveur amont synthétique ; le contrôleur est un double dont seul status()
répond. L'intégration finale utilise le vrai runner sur un projet synthétique.
"""

import ast
import http.client
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from real_preview_support import make_project, processes_mentioning, wait_until_dead

import forge_design.real_preview.proxy as proxy_module
from forge_design.real_preview import (
    RealPreviewController,
    RealPreviewProxyConfig,
    RealPreviewProxyServer,
    RealPreviewStatus,
    create_real_preview_proxy,
)
from forge_design.real_preview.proxy import (
    rewrite_frame_ancestors,
    rewrite_location,
    validate_frame_ancestor_origin,
)

ORIGIN = "http://127.0.0.1:8765"
Headers = list[tuple[str, str]]


# ── Fonctions pures ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("origin", ["http://127.0.0.1:8765", "http://127.0.0.1:1"])
def test_origin_accepted(origin: str) -> None:
    assert validate_frame_ancestor_origin(origin) == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://127.0.0.1:8765",
        "http://localhost:8765",
        "http://127.0.0.1",
        "http://127.0.0.1:",
        "http://127.0.0.1:0",
        "http://127.0.0.1:65536",
        "http://127.0.0.1:08765",
        "http://127.0.0.1:8765/",
        "http://127.0.0.1:8765/path",
        "http://127.0.0.1:8765?x=1",
        "http://127.0.0.1:8765#f",
        "http://user@127.0.0.1:8765",
        "http://[::1]:8765",
        "http://127.0.0.2:8765",
        "HTTP://127.0.0.1:8765",
        " http://127.0.0.1:8765",
        "http://127.0.0.1:8765\n",
        "*",
        "'self'",
        "",
        None,
        8765,
    ],
)
def test_origin_refused(origin: object) -> None:
    with pytest.raises(ValueError):
        validate_frame_ancestor_origin(origin)


@pytest.mark.parametrize(
    ("policies", "expected"),
    [
        ([], [f"frame-ancestors {ORIGIN}"]),
        (
            ["default-src 'self'; frame-ancestors 'none'; script-src 'self'"],
            [f"default-src 'self'; frame-ancestors {ORIGIN}; script-src 'self'"],
        ),
        (
            ["default-src 'self'", "frame-ancestors 'none'"],
            ["default-src 'self'", f"frame-ancestors {ORIGIN}"],
        ),
        (
            ["default-src 'self'", "script-src 'none'"],
            ["default-src 'self'", "script-src 'none'", f"frame-ancestors {ORIGIN}"],
        ),
        (
            ["default-src 'self', FRAME-ANCESTORS *"],
            [f"default-src 'self', frame-ancestors {ORIGIN}"],
        ),
        (
            ["frame-ancestors 'self'; frame-ancestors *; img-src data:"],
            [f"frame-ancestors {ORIGIN}; frame-ancestors {ORIGIN}; img-src data:"],
        ),
        (
            ["default-src 'self';; frame-ancestors-x a ;"],
            ["default-src 'self'; frame-ancestors-x a", f"frame-ancestors {ORIGIN}"],
        ),
    ],
)
def test_rewrite_frame_ancestors(policies: list[str], expected: list[str]) -> None:
    assert rewrite_frame_ancestors(policies, ORIGIN) == expected


def test_rewrite_frame_ancestors_validates_origin() -> None:
    with pytest.raises(ValueError):
        rewrite_frame_ancestors([], "*")


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("/login", "/login"),
        ("login?next=/", "login?next=/"),
        ("http://127.0.0.1:4000/a/b?x=1#f", "/a/b?x=1#f"),
        ("http://127.0.0.1:4000", "/"),
        ("HTTP://127.0.0.1:4000/x", "/x"),
        ("//127.0.0.1:4000/x", "/x"),
        ("http://127.0.0.1:4001/x", "http://127.0.0.1:4001/x"),
        ("https://127.0.0.1:4000/x", "https://127.0.0.1:4000/x"),
        ("http://user@127.0.0.1:4000/x", "http://user@127.0.0.1:4000/x"),
        ("http://localhost:4000/x", "http://localhost:4000/x"),
        ("https://example.org/", "https://example.org/"),
        ("http://[::1", "http://[::1"),
    ],
)
def test_rewrite_location(location: str, expected: str) -> None:
    assert rewrite_location(location, 4000) == expected


@pytest.mark.parametrize(
    "options",
    [
        {"request_timeout": 0},
        {"request_timeout": float("nan")},
        {"request_timeout": True},
        {"request_timeout": 3601},
        {"max_response_bytes": 0},
        {"max_response_bytes": 1.5},
        {"max_static_bytes": 64 * 1024 * 1024 + 1},
        {"max_static_bytes": True},
    ],
)
def test_config_validation(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        RealPreviewProxyConfig(**options)


def test_config_defaults() -> None:
    config = RealPreviewProxyConfig()
    assert (config.request_timeout, config.max_response_bytes) == (
        10.0,
        8 * 1024 * 1024,
    )
    assert config.max_static_bytes == 8 * 1024 * 1024


# ── Doubles : contrôleur et serveur amont ────────────────────────────────────


class FakeController(RealPreviewController):
    """Seul status() est utilisé ; start et stop sont interdits au proxy."""

    def __init__(self) -> None:
        super().__init__()
        self.current = RealPreviewStatus("stopped", None, None, None, None, None, ())
        self.calls = 0

    def running(self, port: int, root: Path) -> None:
        self.current = RealPreviewStatus("running", root, 4242, port, None, None, ())

    def status(self) -> RealPreviewStatus:
        self.calls += 1
        return self.current

    def start(self, project_root: Any) -> RealPreviewStatus:
        raise AssertionError("le proxy ne démarre jamais le runner")

    def stop(self) -> RealPreviewStatus:
        raise AssertionError("le proxy n'arrête jamais le runner")


Reply = tuple[int, Headers, bytes]


class _Upstream(BaseHTTPRequestHandler):
    def _answer(self) -> None:
        server: Any = self.server
        server.requests.append((self.command, self.path, list(self.headers.items())))
        if server.delay:
            time.sleep(server.delay)
        if server.raw is not None:
            self.wfile.write(server.raw)
            return
        status, headers, body = server.reply
        self.send_response_only(status)
        for name, value in headers:
            self.send_header(name, value)
        if not any(name.lower() == "content-length" for name, _ in headers):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_HEAD = do_POST = _answer

    def log_message(self, format: str, *args: Any) -> None:
        pass


class Upstream:
    def __init__(self) -> None:
        self.server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
        self.server.daemon_threads = True
        self.server.requests = []
        self.server.reply = (200, [("Content-Type", "text/html")], b"<p>cible</p>")
        self.server.delay = 0.0
        self.server.raw = None
        self.thread = threading.Thread(
            target=self.server.serve_forever, args=(0.05,), daemon=True
        )
        self.thread.start()

    @property
    def port(self) -> int:
        return self.server.server_address[1]

    @property
    def requests(self) -> list[tuple[str, str, Headers]]:
        return self.server.requests

    def reply(self, status: int, headers: Headers, body: bytes = b"") -> None:
        self.server.reply = (status, headers, body)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


@pytest.fixture
def upstream() -> Iterator[Upstream]:
    server = Upstream()
    yield server
    server.close()


@pytest.fixture
def other_server() -> Iterator[Upstream]:
    """Serveur qu'aucune requête du proxy ne doit jamais atteindre."""
    server = Upstream()
    yield server
    server.close()


@pytest.fixture
def controller(tmp_path: Path) -> FakeController:
    (tmp_path / "projet" / "static").mkdir(parents=True)
    return FakeController()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return (tmp_path / "projet").resolve()


ProxyFactory = Callable[..., RealPreviewProxyServer]


@pytest.fixture
def start_proxy() -> Iterator[ProxyFactory]:
    started: list[tuple[RealPreviewProxyServer, threading.Thread]] = []

    def start(
        controller: RealPreviewController,
        config: RealPreviewProxyConfig | None = None,
    ) -> RealPreviewProxyServer:
        server = create_real_preview_proxy(
            controller, frame_ancestor_origin=ORIGIN, config=config
        )
        thread = threading.Thread(
            target=server.serve_forever, args=(0.05,), daemon=True
        )
        thread.start()
        started.append((server, thread))
        return server

    yield start
    for server, thread in started:
        server.shutdown()
        server.server_close()
        thread.join()


def request(
    port: int,
    method: str = "GET",
    target: str = "/",
    headers: Sequence[tuple[str, str]] = (),
    *,
    host: str | None = "default",
    body: bytes | None = None,
) -> tuple[int, Headers, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.putrequest(method, target, skip_host=True, skip_accept_encoding=True)
        if host == "default":
            connection.putheader("Host", f"127.0.0.1:{port}")
        elif host is not None:
            connection.putheader("Host", host)
        for name, value in headers:
            connection.putheader(name, value)
        if body is not None:
            connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        return response.status, response.getheaders(), response.read()
    finally:
        connection.close()


def raw_request(port: int, data: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=10) as client:
        client.sendall(data)
        chunks: list[bytes] = []
        while chunk := client.recv(65536):
            chunks.append(chunk)
    return b"".join(chunks)


def header(headers: Headers, name: str) -> list[str]:
    return [value for key, value in headers if key.lower() == name.lower()]


# ── Création du listener ─────────────────────────────────────────────────────


def test_create_proxy_without_thread(controller: FakeController) -> None:
    before = set(threading.enumerate())
    with create_real_preview_proxy(controller, frame_ancestor_origin=ORIGIN) as server:
        assert server.server_address[0] == "127.0.0.1"
        assert server.server_port > 0
        assert set(threading.enumerate()) == before
    assert controller.calls == 0


@pytest.mark.parametrize(
    ("options", "error"),
    [
        ({"host": "0.0.0.0"}, ValueError),
        ({"host": "localhost"}, ValueError),
        ({"port": -1}, ValueError),
        ({"port": 65536}, ValueError),
        ({"port": True}, ValueError),
        ({"frame_ancestor_origin": "*"}, ValueError),
    ],
)
def test_create_proxy_refuses(
    controller: FakeController, options: dict[str, Any], error: type[Exception]
) -> None:
    arguments: dict[str, Any] = {"frame_ancestor_origin": ORIGIN, **options}
    with pytest.raises(error):
        create_real_preview_proxy(controller, **arguments)


def test_bind_error_is_not_retried(controller: FakeController) -> None:
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        with pytest.raises(OSError):
            create_real_preview_proxy(
                controller, frame_ancestor_origin=ORIGIN, port=port
            )


def test_server_never_shares_ports() -> None:
    assert RealPreviewProxyServer.daemon_threads is True
    assert RealPreviewProxyServer.allow_reuse_address is False
    assert RealPreviewProxyServer.allow_reuse_port is False


# ── Host, méthodes, état du runner ───────────────────────────────────────────


@pytest.mark.parametrize(
    "host",
    [
        None,
        "",
        "localhost:%d",
        "evil.example:%d",
        "[::1]:%d",
        "127.0.0.1",
        "127.0.0.1:1",
    ],
)
def test_host_guard_before_anything(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    host: str | None,
) -> None:
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    value = host % port if host and "%d" in host else host
    for target in ("/", "/static/a.css"):
        status, headers, body = request(port, target=target, host=value)
        assert (status, body) == (400, "Hôte de requête non autorisé.\n".encode())
        assert header(headers, "Cache-Control") == ["no-store"]
    assert controller.calls == 0 and upstream.requests == []


def test_duplicate_host_refused(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    status, _, _ = request(port, headers=[("Host", f"127.0.0.1:{port}")])
    assert status == 400 and upstream.requests == []


@pytest.mark.parametrize(
    "method", ["POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT", "FOO"]
)
def test_other_methods_never_reach_runner(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    method: str,
) -> None:
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    target = f"127.0.0.1:{upstream.port}" if method == "CONNECT" else "/contacts"
    status, headers, _ = request(port, method, target, body=b"a=1")
    assert status == 405
    assert header(headers, "Allow") == ["GET, HEAD"]
    assert upstream.requests == [] and controller.calls == 0


@pytest.mark.parametrize("state", ["stopped", "starting", "failed", "stopping"])
def test_runner_not_running_gives_503(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    state: Any,
) -> None:
    controller.current = RealPreviewStatus(
        state, root, 1, upstream.port, None, None, ()
    )
    port = start_proxy(controller).server_port
    for target in ("/", "/static/a.css"):
        status, _, body = request(port, target=target)
        assert (status, body) == (503, "Preview réelle indisponible.\n".encode())
    assert upstream.requests == []


@pytest.mark.parametrize(("has_port", "has_root"), [(False, True), (True, False)])
def test_running_without_port_or_root_gives_503(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    has_port: bool,
    has_root: bool,
) -> None:
    controller.current = RealPreviewStatus(
        "running",
        root if has_root else None,
        1,
        upstream.port if has_port else None,
        None,
        None,
        (),
    )
    port = start_proxy(controller).server_port
    assert request(port)[0] == 503
    assert upstream.requests == []


# ── Relais ───────────────────────────────────────────────────────────────────


def test_forward_nominal(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.reply(
        201,
        [("Content-Type", "text/html; charset=utf-8"), ("X-Custom", "conservé")],
        b"<h1>OK</h1>",
    )
    port = start_proxy(controller).server_port
    target = "/a%20b/c?x=1&y=%2F&z=a+b"
    status, headers, body = request(port, target=target)
    assert (status, body) == (201, b"<h1>OK</h1>")
    assert header(headers, "Content-Type") == ["text/html; charset=utf-8"]
    assert header(headers, "X-Custom") == ["conservé"]
    assert header(headers, "Content-Length") == ["11"]
    method, path, sent = upstream.requests[0]
    assert (method, path) == ("GET", target)
    assert header(sent, "Host") == [f"127.0.0.1:{upstream.port}"]
    assert controller.calls == 1


def test_head_has_no_body(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.reply(200, [("Content-Type", "text/html")], b"0123456789")
    port = start_proxy(controller).server_port
    status, headers, body = request(port, "HEAD", "/page")
    assert (status, body) == (200, b"")
    assert header(headers, "Content-Length") == ["10"]
    assert upstream.requests[0][:2] == ("HEAD", "/page")


def test_request_header_policy(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    request(
        port,
        target="/",
        headers=[
            ("Accept", "text/html"),
            ("Accept-Language", "fr"),
            ("Accept-Encoding", "gzip"),
            ("User-Agent", "test"),
            ("Cookie", "session=abc"),
            ("Referer", f"http://127.0.0.1:{port}/"),
            ("Origin", f"http://127.0.0.1:{port}"),
            ("HX-Request", "true"),
            ("HX-Target", "#liste"),
            ("HX-Current-URL", f"http://127.0.0.1:{port}/"),
            ("Authorization", "Bearer secret"),
            ("Proxy-Authorization", "Basic x"),
            ("Connection", "X-Secret"),
            ("X-Secret", "1"),
            ("Keep-Alive", "timeout=5"),
            ("TE", "trailers"),
            ("Upgrade", "websocket"),
            ("X-Forwarded-For", "8.8.8.8"),
        ],
    )
    sent = {name.lower(): value for name, value in upstream.requests[0][2]}
    assert sent == {
        "host": f"127.0.0.1:{upstream.port}",
        "accept": "text/html",
        "accept-language": "fr",
        "user-agent": "test",
        "cookie": "session=abc",
        "referer": f"http://127.0.0.1:{port}/",
        "origin": f"http://127.0.0.1:{port}",
        "hx-request": "true",
        "hx-target": "#liste",
        "hx-current-url": f"http://127.0.0.1:{port}/",
    }


def test_get_with_body_refused(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    assert request(port, body=b"corps")[0] == 400
    chunked = (
        f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
        "Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n0\r\n\r\n"
    ).encode()
    assert raw_request(port, chunked).startswith(b"HTTP/1.0 400")
    assert upstream.requests == []


@pytest.mark.parametrize(
    "target",
    [
        b"http://evil.example/path",
        b"http://127.0.0.1:%d/x",
        b"127.0.0.1:%d",
        b"*",
        b"/caf\xc3\xa9",
        b"/a\x7fb",
        b"/" + b"a" * 4096,
        b"/?" + b"q" * 8193,
    ],
)
def test_invalid_targets_refused(
    controller: FakeController,
    upstream: Upstream,
    other_server: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    target: bytes,
) -> None:
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    if b"%d" in target:
        target = target % other_server.port
    answer = raw_request(
        port, b"GET " + target + b" HTTP/1.0\r\nHost: 127.0.0.1:%d\r\n\r\n" % port
    )
    assert answer.startswith(b"HTTP/1.0 400")
    assert upstream.requests == [] and other_server.requests == []


def test_destination_cannot_be_chosen(
    controller: FakeController,
    upstream: Upstream,
    other_server: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chemin, Host, X-Forwarded-Host ni proxy d'environnement ne changent la cible."""
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, f"http://127.0.0.1:{other_server.port}")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    for target in (
        f"//127.0.0.1:{other_server.port}/x",
        f"/@127.0.0.1:{other_server.port}/x",
        "/http://evil.example/",
    ):
        status, _, _ = request(
            port, target=target, headers=[("X-Forwarded-Host", "evil.example")]
        )
        assert status == 200
    assert len(upstream.requests) == 3
    assert other_server.requests == []


@pytest.mark.parametrize("status", [302, 401, 403, 404, 500])
def test_status_preserved(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    status: int,
) -> None:
    controller.running(upstream.port, root)
    upstream.reply(status, [("Content-Type", "text/plain")], b"cible")
    port = start_proxy(controller).server_port
    assert request(port)[0::2] == (status, b"cible")


def test_response_header_policy(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.reply(
        200,
        [
            ("Content-Type", "text/html"),
            ("X-Frame-Options", "DENY"),
            ("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'"),
            ("Content-Security-Policy", "script-src 'self'"),
            ("Content-Security-Policy-Report-Only", "frame-ancestors 'none'"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("Set-Cookie", "a=1; HttpOnly"),
            ("Set-Cookie", "b=2; SameSite=Lax"),
            ("HX-Trigger", "rafraichir"),
            ("Connection", "X-Interne"),
            ("X-Interne", "secret"),
            ("Keep-Alive", "timeout=5"),
            ("Proxy-Authenticate", "Basic"),
            ("Trailer", "X-T"),
            ("Upgrade", "h2c"),
        ],
        b"<p>x</p>",
    )
    port = start_proxy(controller).server_port
    _, headers, _ = request(port)
    names = {name.lower() for name, _ in headers}
    assert not names & {
        "x-frame-options",
        "x-interne",
        "keep-alive",
        "proxy-authenticate",
        "trailer",
        "upgrade",
        "transfer-encoding",
    }
    assert header(headers, "Content-Security-Policy") == [
        f"default-src 'self'; frame-ancestors {ORIGIN}",
        "script-src 'self'",
    ]
    assert header(headers, "Content-Security-Policy-Report-Only") == [
        "frame-ancestors 'none'"
    ]
    assert header(headers, "X-Content-Type-Options") == ["nosniff"]
    assert header(headers, "Referrer-Policy") == ["no-referrer"]
    assert header(headers, "Set-Cookie") == ["a=1; HttpOnly", "b=2; SameSite=Lax"]
    assert header(headers, "HX-Trigger") == ["rafraichir"]


def test_missing_csp_gets_frame_ancestors(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.reply(200, [("Content-Type", "text/html"), ("X-Frame-Options", "DENY")])
    port = start_proxy(controller).server_port
    _, headers, _ = request(port)
    assert header(headers, "Content-Security-Policy") == [f"frame-ancestors {ORIGIN}"]
    assert header(headers, "X-Frame-Options") == []


def test_body_is_never_rewritten(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    page = (
        f'<a href="http://127.0.0.1:{upstream.port}/x">lien</a>'
        '<link rel="stylesheet" href="/static/app.css"><script src="/a.js"></script>'
    ).encode()
    upstream.reply(200, [("Content-Type", "text/html")], page)
    port = start_proxy(controller).server_port
    assert request(port)[2] == page
    upstream.reply(
        200, [("Content-Type", "text/css"), ("Content-Encoding", "gzip")], b"\x1f\x8b"
    )
    _, headers, body = request(port)
    assert body == b"\x1f\x8b" and header(headers, "Content-Encoding") == ["gzip"]


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("/login", "/login"),
        ("http://127.0.0.1:{up}/contacts?page=2", "/contacts?page=2"),
        ("https://example.org/sortie", "https://example.org/sortie"),
        ("http://127.0.0.1:{other}/x", "http://127.0.0.1:{other}/x"),
    ],
)
def test_redirects_are_not_followed(
    controller: FakeController,
    upstream: Upstream,
    other_server: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    location: str,
    expected: str,
) -> None:
    controller.running(upstream.port, root)
    values = {"up": upstream.port, "other": other_server.port}
    upstream.reply(302, [("Location", location.format(**values))])
    port = start_proxy(controller).server_port
    status, headers, _ = request(port)
    assert status == 302
    assert header(headers, "Location") == [expected.format(**values)]
    assert len(upstream.requests) == 1 and other_server.requests == []


# ── Bornes, délais, erreurs amont ────────────────────────────────────────────


def test_response_exactly_at_limit(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.reply(200, [("Content-Type", "text/plain")], b"x" * 1000)
    port = start_proxy(
        controller, RealPreviewProxyConfig(max_response_bytes=1000)
    ).server_port
    assert request(port)[0::2] == (200, b"x" * 1000)


def test_response_over_limit(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.reply(200, [("Content-Type", "text/plain")], b"x" * 1001)
    port = start_proxy(
        controller, RealPreviewProxyConfig(max_response_bytes=1000)
    ).server_port
    status, _, body = request(port)
    assert (status, body) == (502, "Réponse de preview trop volumineuse.\n".encode())


@pytest.mark.parametrize(
    "raw",
    [
        # Sans Content-Length : corps délimité par la fermeture.
        b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n" + b"y" * 1001,
        # Content-Length mensonger, inférieur au corps réel : seule la borne compte.
        b"HTTP/1.0 200 OK\r\nContent-Length: 2000\r\n\r\n" + b"y" * 1001,
    ],
)
def test_response_bound_does_not_trust_content_length(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
    raw: bytes,
) -> None:
    controller.running(upstream.port, root)
    upstream.server.raw = raw
    port = start_proxy(
        controller, RealPreviewProxyConfig(max_response_bytes=1000)
    ).server_port
    assert request(port)[0] == 502


def test_truncated_upstream_body(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.server.raw = b"HTTP/1.0 200 OK\r\nContent-Length: 50\r\n\r\ncourt"
    port = start_proxy(controller).server_port
    assert request(port)[0] == 502


def test_upstream_timeout(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.server.delay = 2.0
    port = start_proxy(
        controller, RealPreviewProxyConfig(request_timeout=0.3)
    ).server_port
    started = time.monotonic()
    status, _, body = request(port)
    assert (status, body) == (504, "Preview réelle sans réponse.\n".encode())
    assert time.monotonic() - started < 1.5
    assert len(upstream.requests) == 1


def test_connection_refused(
    controller: FakeController, root: Path, start_proxy: ProxyFactory
) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed = probe.getsockname()[1]
    controller.running(closed, root)
    port = start_proxy(controller).server_port
    status, _, body = request(port)
    assert (status, body) == (502, "Preview réelle injoignable.\n".encode())


def test_errors_are_frameable_only_by_editor(
    controller: FakeController, start_proxy: ProxyFactory
) -> None:
    port = start_proxy(controller).server_port
    _, headers, _ = request(port)
    assert header(headers, "Content-Security-Policy") == [
        f"default-src 'none'; frame-ancestors {ORIGIN}"
    ]


# ── /static/ ─────────────────────────────────────────────────────────────────


@pytest.fixture
def static_root(controller: FakeController, root: Path) -> Path:
    static = root / "static"
    (static / "css").mkdir()
    (static / "css" / "app.css").write_text("body{color:red}")
    (static / "app.js").write_text("console.log(1)")
    (static / "logo.png").write_bytes(b"\x89PNG")
    (static / "data.inconnu").write_bytes(b"\x00\x01")
    (static / "mon fichier.txt").write_text("espace")
    (root / "secret.txt").write_text("secret")
    controller.running(9, root)
    return static


@pytest.mark.parametrize(
    ("target", "content_type", "body"),
    [
        ("/static/css/app.css", "text/css", b"body{color:red}"),
        ("/static/app.js?v=3", "text/javascript", b"console.log(1)"),
        ("/static/logo.png", "image/png", b"\x89PNG"),
        ("/static/data.inconnu", "application/octet-stream", b"\x00\x01"),
        ("/static/mon%20fichier.txt", "text/plain", b"espace"),
    ],
)
def test_static_get_and_head(
    controller: FakeController,
    static_root: Path,
    start_proxy: ProxyFactory,
    target: str,
    content_type: str,
    body: bytes,
) -> None:
    port = start_proxy(controller).server_port
    status, headers, received = request(port, target=target)
    assert (status, received) == (200, body)
    assert header(headers, "Content-Type") == [content_type]
    assert header(headers, "Content-Length") == [str(len(body))]
    assert header(headers, "Cache-Control") == ["no-store"]
    head_status, head_headers, head_body = request(port, "HEAD", target)
    assert (head_status, head_body) == (200, b"")
    assert header(head_headers, "Content-Length") == [str(len(body))]


@pytest.mark.parametrize(
    "target",
    [
        "/static",
        "/static/",
        "/static/../secret.txt",
        "/static/css/../app.js",
        "/static/./app.js",
        "/static/%2e%2e/secret.txt",
        "/static/css%2fapp.css",
        "/static/css%5capp.css",
        "/static/css//app.css",
        "/static/.cache",
        "/static/env/x.css",
        "/static/ENV/x.css",
        "/static/key.pem",
        "/static/id_rsa",
        "/static/a:b.css",
        "/static/a%00.css",
        "/static/%ff.css",
    ],
)
def test_static_invalid_paths(
    controller: FakeController,
    static_root: Path,
    start_proxy: ProxyFactory,
    target: str,
) -> None:
    port = start_proxy(controller).server_port
    status, _, body = request(port, target=target)
    assert (status, body) == (400, "Chemin statique refusé.\n".encode())


def test_static_missing(
    controller: FakeController, static_root: Path, start_proxy: ProxyFactory
) -> None:
    port = start_proxy(controller).server_port
    for target in ("/static/absent.css", "/static/absent/app.css"):
        assert request(port, target=target)[0] == 404


def _forbidden(port: int, target: str) -> None:
    status, _, body = request(port, target=target)
    assert (status, body) == (403, "Fichier statique refusé.\n".encode())


def test_static_symlinks_refused(
    controller: FakeController,
    static_root: Path,
    root: Path,
    start_proxy: ProxyFactory,
    tmp_path: Path,
) -> None:
    (static_root / "lien.css").symlink_to(root / "secret.txt")
    (static_root / "interne.css").symlink_to(static_root / "css" / "app.css")
    outside = tmp_path / "dehors"
    outside.mkdir()
    (outside / "x.css").write_text("dehors")
    (static_root / "dossier").symlink_to(outside)
    port = start_proxy(controller).server_port
    for target in ("/static/lien.css", "/static/interne.css", "/static/dossier/x.css"):
        _forbidden(port, target)


def test_static_directory_symlink_refused(
    controller: FakeController, root: Path, start_proxy: ProxyFactory, tmp_path: Path
) -> None:
    (root / "static").rmdir()
    elsewhere = tmp_path / "ailleurs"
    elsewhere.mkdir()
    (elsewhere / "a.css").write_text("a")
    (root / "static").symlink_to(elsewhere)
    controller.running(9, root)
    port = start_proxy(controller).server_port
    _forbidden(port, "/static/a.css")


def test_static_non_regular_refused_without_blocking(
    controller: FakeController, static_root: Path, start_proxy: ProxyFactory
) -> None:
    os.mkfifo(static_root / "tube.css")
    port = start_proxy(controller).server_port
    started = time.monotonic()
    _forbidden(port, "/static/tube.css")
    _forbidden(port, "/static/css")
    assert time.monotonic() - started < 2


def test_static_size_bound(
    controller: FakeController, static_root: Path, start_proxy: ProxyFactory
) -> None:
    (static_root / "dix.txt").write_bytes(b"0123456789")
    (static_root / "onze.txt").write_bytes(b"0123456789A")
    config = RealPreviewProxyConfig(max_static_bytes=10)
    port = start_proxy(controller, config).server_port
    assert request(port, target="/static/dix.txt")[0::2] == (200, b"0123456789")
    _forbidden(port, "/static/onze.txt")


def test_static_never_forwarded(
    controller: FakeController,
    upstream: Upstream,
    static_root: Path,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    request(port, target="/static/app.js")
    request(port, target="/static/absent.js")
    assert upstream.requests == []


# ── Hygiène ──────────────────────────────────────────────────────────────────


def test_proxy_module_imports() -> None:
    names: set[str] = set()
    for node in ast.walk(ast.parse(Path(proxy_module.__file__).read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module.split(".")[0])
    assert names <= sys.stdlib_module_names | {"forge_design"}
    assert not names & {"subprocess", "runpy", "signal", "urllib.request"}
    source = Path(proxy_module.__file__).read_text()
    for forbidden in (
        ".start(",
        ".stop(",
        "Popen",
        "killpg",
        "chdir",
        "sys.path",
        "read_bytes",
        "open(",
    ):
        assert forbidden not in source.replace("os.open(", "").replace("_open(", "")


def test_proxy_requests_launch_no_process(
    controller: FakeController,
    upstream: Upstream,
    static_root: Path,
    root: Path,
    start_proxy: ProxyFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("aucun processus ne doit être lancé")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "fork", forbidden)
    controller.running(upstream.port, root)
    port = start_proxy(controller).server_port
    assert request(port)[0] == 200
    assert request(port, target="/static/app.js")[0] == 200


def test_parallel_requests(
    controller: FakeController,
    upstream: Upstream,
    root: Path,
    start_proxy: ProxyFactory,
) -> None:
    controller.running(upstream.port, root)
    upstream.server.delay = 0.3
    port = start_proxy(controller).server_port
    results: list[int] = []

    def fetch() -> None:
        results.append(request(port)[0])

    threads = [threading.Thread(target=fetch) for _ in range(5)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [200] * 5
    assert time.monotonic() - started < 1.2


# ── Intégration avec le vrai runner ──────────────────────────────────────────


def test_real_runner_through_proxy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, other_server: Upstream
) -> None:
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, f"http://127.0.0.1:{other_server.port}")
    root = make_project(tmp_path / "projet").resolve()
    (root / "static" / "test.css").write_text(".preview{color:blue}")
    threads_before = set(threading.enumerate())
    controller = RealPreviewController()
    try:
        status = controller.start(root)
        assert status.state == "running", status
        with create_real_preview_proxy(
            controller, frame_ancestor_origin=ORIGIN
        ) as proxy:
            assert proxy.server_port not in (status.port, 0)
            thread = threading.Thread(
                target=proxy.serve_forever, args=(0.05,), daemon=True
            )
            thread.start()
            port = proxy.server_port
            try:
                code, headers, body = request(port, target="/health")
                assert (code, body) == (200, b'{"status": "ok"}')
                code, headers, body = request(port, target="/")
                assert code == 200 and b"<html" in body.lower()
                assert header(headers, "Content-Type")[0].startswith("text/html")
                assert header(headers, "X-Frame-Options") == []
                policies = header(headers, "Content-Security-Policy")
                assert any(f"frame-ancestors {ORIGIN}" in p for p in policies)
                assert all("frame-ancestors 'none'" not in p for p in policies)
                assert any("default-src 'self'" in p for p in policies)
                assert header(headers, "X-Content-Type-Options") == ["nosniff"]
                head_code, head_headers, head_body = request(port, "HEAD", "/health")
                assert (head_code, head_body) == (200, b"")
                assert header(head_headers, "Content-Type") == ["application/json"]
                # Forge rc9 ne route pas HEAD vers GET : réponse relayée telle quelle.
                head_code, _, head_body = request(port, "HEAD", "/")
                assert (head_code, head_body) == (405, b"")
                assert request(port, target="/static/test.css")[0::2] == (
                    200,
                    b".preview{color:blue}",
                )
                assert request(port, "HEAD", "/static/test.css")[0::2] == (200, b"")
                assert request(port, "POST", "/", body=b"x=1")[0] == 405
                assert controller.status().state == "running"
                controller.stop()
                assert request(port, target="/health")[0] == 503
            finally:
                proxy.shutdown()
                thread.join()
    finally:
        controller.stop()
    assert other_server.requests == []
    assert wait_until_dead(processes_mentioning(str(tmp_path))) == []
    deadline = time.monotonic() + 2
    while set(threading.enumerate()) - threads_before and time.monotonic() < deadline:
        time.sleep(0.05)
    assert set(threading.enumerate()) - threads_before == set()
