"""HTTP réel sur un port éphémère et cycle de vie sans thread résiduel."""

import errno
import inspect
import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator
from http.client import HTTPConnection
from importlib.resources import files
from pathlib import Path
from threading import Thread
from wsgiref.simple_server import WSGIServer

import pytest
from core.app.application import Application

from forge_design.forge import project_detection, project_root, project_version
from forge_design.tools import project_inspector
from forge_design.web import server as web


@pytest.fixture
def running_server() -> Iterator[WSGIServer]:
    with web.create_server(port=0) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_defaults() -> None:
    for function in (web.create_server, web.run_server):
        parameters = inspect.signature(function).parameters
        assert parameters["host"].default == "127.0.0.1"
        assert parameters["port"].default == 8765


def test_local_binding_and_response(running_server: WSGIServer) -> None:
    assert running_server.server_address[0] == "127.0.0.1"
    assert running_server.socket.getsockname()[0] == "127.0.0.1"
    assert running_server.server_port > 0
    connection = HTTPConnection("127.0.0.1", running_server.server_port, timeout=3)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type") == "text/html; charset=utf-8"
        body = response.read()
        assert response.getheader("Content-Length") == str(len(body))
        html = body.decode("utf-8")
        assert html.startswith("<!doctype html>")
        assert '<html lang="fr">' in html
        assert "<title>Forge Design</title>" in html
        assert '<h1 class="visually-hidden">Forge Design</h1>' in html
        assert 'data-current-project=""' in html
    finally:
        connection.close()


@pytest.mark.parametrize(
    "path",
    [
        "/.env",
        "/../../etc/passwd",
        "/%2e%2e/%2e%2e/etc/passwd",
        "/..%2f..%2fetc/passwd",
        "/%252e%252e/etc/passwd",
        "/templates/index.html",
    ],
)
def test_no_other_route(running_server: WSGIServer, path: str) -> None:
    connection = HTTPConnection("127.0.0.1", running_server.server_port, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        assert response.status == 404
        response.read()
    finally:
        connection.close()


def test_no_project_access(
    running_server: WSGIServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Web must not access a project")

    monkeypatch.setattr(project_inspector, "inspect_project", forbidden)
    monkeypatch.setattr(project_inspector.ProjectInspectorTool, "run", forbidden)
    monkeypatch.setattr(project_root, "resolve_project_root", forbidden)
    monkeypatch.setattr(project_detection, "detect_forge_project", forbidden)
    monkeypatch.setattr(project_version, "read_forge_version", forbidden)
    resource = Path(str(files("forge_design.web").joinpath("templates/index.html")))
    original_open = Path.open

    def guarded_open(
        self: Path,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ):
        assert self == resource and mode == "r"
        return original_open(self, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", guarded_open)
    test_local_binding_and_response(running_server)


def _idle(server: WSGIServer) -> socket.socket:
    """Connexion ouverte sans requête, acceptée par le serveur avant la suite."""
    idle = socket.create_connection(("127.0.0.1", server.server_port), timeout=3)
    time.sleep(0.1)
    return idle


def _get_status(server: WSGIServer, path: str = "/") -> int:
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def test_idle_connection_does_not_block_requests(running_server: WSGIServer) -> None:
    """Une connexion muette (transfert de port d'un éditeur, préconnexion) ne fige
    plus l'interface : elle n'occupe que son propre thread."""
    idle = _idle(running_server)
    try:
        start = time.monotonic()
        test_local_binding_and_response(running_server)
        assert time.monotonic() - start < 2
    finally:
        idle.close()


def test_idle_connection_closed_after_timeout(
    monkeypatch: pytest.MonkeyPatch, running_server: WSGIServer
) -> None:
    monkeypatch.setattr(web.ForgeDesignRequestHandler, "timeout", 0.2)
    idle = _idle(running_server)
    try:
        start = time.monotonic()
        assert idle.recv(1) == b""
        assert time.monotonic() - start < 2
    finally:
        idle.close()
    assert _get_status(running_server) == 200


def test_application_runs_one_request_at_a_time(running_server: WSGIServer) -> None:
    lock = threading.Lock()
    active = peak = 0

    def slow(environ: object, start_response: Callable[..., object]) -> list[bytes]:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.1)
        with lock:
            active -= 1
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]

    original = running_server.get_app()
    assert original is not None
    running_server.set_app(slow)
    statuses: list[int] = []
    try:
        clients = [
            Thread(target=lambda: statuses.append(_get_status(running_server)))
            for _ in range(3)
        ]
        for client in clients:
            client.start()
        for client in clients:
            client.join(timeout=5)
    finally:
        running_server.set_app(original)
    assert statuses == [200, 200, 200]
    assert peak == 1


def test_requests_refused_once_closing(running_server: WSGIServer) -> None:
    assert isinstance(running_server, web.ForgeDesignServer)
    running_server.close_real_preview()
    assert _get_status(running_server) == 503


def test_close_does_not_wait_for_idle_connection() -> None:
    with web.create_server(port=0) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        idle = _idle(server)
        start = time.monotonic()
        server.shutdown()
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert time.monotonic() - start < 2
    idle.close()


def test_stop_releases_port() -> None:
    with web.create_server(port=0) as server:
        port = server.server_port
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        server.shutdown()
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert server.socket.fileno() == -1
    with web.create_server(port=port) as replacement:
        assert replacement.server_port == port


def test_port_in_use() -> None:
    with web.create_server(port=0) as server:
        with pytest.raises(OSError) as error:
            web.create_server(port=server.server_port)
    assert error.value.errno == errno.EADDRINUSE


@pytest.mark.parametrize("port", [-1, 65536, True])
def test_invalid_port(port: int) -> None:
    with pytest.raises(ValueError, match="port"):
        web.create_server(port=port)


@pytest.mark.parametrize("host", ["0.0.0.0", "", "localhost", "::1", "192.0.2.1"])
def test_other_host_rejected(host: str) -> None:
    with pytest.raises(ValueError, match="127.0.0.1"):
        web.create_server(host=host, port=0)


@pytest.mark.parametrize("failure", [KeyboardInterrupt, RuntimeError])
def test_run_server_closes_on_exit(
    monkeypatch: pytest.MonkeyPatch, failure: type[BaseException]
) -> None:
    server = web.create_server(port=0)

    def create(host: str, port: int, *, modules: object = None) -> WSGIServer:
        assert host == "127.0.0.1" and port == 0
        return server

    def serve(poll_interval: float = 0.5) -> None:
        raise failure

    monkeypatch.setattr(web, "create_server", create)
    monkeypatch.setattr(server, "serve_forever", serve)
    if failure is KeyboardInterrupt:
        web.run_server(port=0)
    else:
        with pytest.raises(RuntimeError):
            web.run_server(port=0)
    assert server.socket.fileno() == -1


def test_html_independent_of_cwd(
    running_server: WSGIServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "index.html").write_text("must not be served")
    monkeypatch.chdir(tmp_path)
    test_local_binding_and_response(running_server)


def test_arbitrary_file_not_served(
    running_server: WSGIServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "private.txt").write_text("private content sentinel")
    monkeypatch.chdir(tmp_path)
    connection = HTTPConnection("127.0.0.1", running_server.server_port, timeout=3)
    try:
        connection.request("GET", "/private.txt")
        response = connection.getresponse()
        assert response.status == 404
        assert b"private content sentinel" not in response.read()
    finally:
        connection.close()


def test_forge_application() -> None:
    assert isinstance(web.create_application(), Application)


def test_forge_headers_and_css(running_server: WSGIServer) -> None:
    connection = HTTPConnection("127.0.0.1", running_server.server_port, timeout=3)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("X-Content-Type-Options") == "nosniff"
        policy = response.getheader("Content-Security-Policy") or ""
        assert "style-src 'self'" in policy
        assert "unsafe-inline" not in policy
        html = response.read().decode("utf-8")
        assert '<link rel="stylesheet" href="/shell.css">' in html
        assert "<style>" not in html
        connection.request("GET", "/shell.css")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type") == "text/css; charset=utf-8"
        assert b"font-family" in response.read()
    finally:
        connection.close()


def _get(server: WSGIServer, path: str) -> tuple[int, str | None, bytes]:
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        connection.close()


def test_fonts_are_served_from_a_closed_list(running_server: WSGIServer) -> None:
    """Polices IBM Plex locales (FD-UX-001) : routes fixes, fichiers packagés tels
    quels, licence OFL jointe mais jamais servie, aucun autre nom."""
    static = files("forge_design.web").joinpath("static")
    css = static.joinpath("shell.css").read_text(encoding="utf-8")
    for name in web.FONT_FILES:
        assert f'url("/fonts/{name}.woff2")' in css
        status, content_type, body = _get(running_server, f"/fonts/{name}.woff2")
        assert status == 200 and content_type == "font/woff2"
        assert body == static.joinpath(f"fonts/{name}.woff2").read_bytes()
        assert body.startswith(b"wOF2")
    for path in ("/fonts/LICENSE-IBM-Plex.txt", "/fonts/Other.woff2", "/fonts/"):
        assert _get(running_server, path)[0] == 404, path
    license_text = static.joinpath("fonts/LICENSE-IBM-Plex.txt").read_text("utf-8")
    assert "SIL Open Font License, Version 1.1" in license_text


def test_shell_sidebar_and_no_inline_style(running_server: WSGIServer) -> None:
    import forge_design

    status, _, body = _get(running_server, "/inspector")
    html = body.decode("utf-8")
    assert status == 200
    shell, content = html.split("<main>", 1)
    assert '<aside class="app-sidebar">' in shell
    assert f'<span class="app-version">{forge_design.__version__}</span>' in shell
    assert "Aucun projet ouvert." in shell
    # Barre du haut : actions du projet ouvert seulement, sans fil d'Ariane.
    assert '<header class="app-topbar">' not in shell and "app-crumb" not in html
    assert "<h1>Vue d’ensemble</h1>" in content
    # L'accueil garde le menu de l'atelier ; son contenu est le lanceur (FD-UX-010).
    home = _get(running_server, "/")[2].decode("utf-8")
    assert '<aside class="app-sidebar">' in home and "app-topbar" not in home
    assert '<main class="launcher" data-current-project="">' in home
    assert "style=" not in home and "<style" not in home
    # CSP style-src 'self' : aucun attribut style, aucune balise style.
    assert "style=" not in html and "<style" not in html


def test_forge_native_health(running_server: WSGIServer) -> None:
    connection = HTTPConnection("127.0.0.1", running_server.server_port, timeout=3)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        assert response.status == 200
        assert b'"ok"' in response.read()
    finally:
        connection.close()


def test_cwd_code_not_imported(
    running_server: WSGIServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("config.py", "bootstrap.py", "app.py"):
        (tmp_path / name).write_text("raise AssertionError('must not import')")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    assert isinstance(web.create_application(), Application)
    test_local_binding_and_response(running_server)


def test_target_version_independent_of_runtime(tmp_path: Path) -> None:
    from importlib.metadata import version

    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).touch()
    (tmp_path / "mvc/routes").mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("forge-mvc==99.0.0")
    assert version("forge-mvc") == "1.0.0rc9"
    assert project_version.read_forge_version(tmp_path).version == "99.0.0"


@pytest.mark.parametrize("path", ["/inspector", "/debug"])
def test_shared_navigation(
    running_server: WSGIServer, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.platform.tool_registry import ToolRegistry

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("La navigation ne doit pas consulter le registre")

    monkeypatch.setattr(ToolRegistry, "get", forbidden)
    monkeypatch.setattr(ToolRegistry, "list", forbidden)
    connection = HTTPConnection("127.0.0.1", running_server.server_port, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        html = response.read().decode()
        assert response.status == 200
        assert '<nav aria-label="Navigation principale">' in html
        assert f'href="{path}" aria-current="page"' in html
        assert html.count('aria-current="page"') == 1
        assert ">Accueil</a>" in html and ">Vue d’ensemble</a>" in html
        assert 'href="/"' in html and 'href="/inspector"' in html
        assert html.count("<main>") == html.count("<head>") == 1
        assert 'href="/shell.css"' in html
    finally:
        connection.close()


def test_pages_extend_same_layout() -> None:
    templates = files("forge_design.web").joinpath("templates")
    for name in ("index.html", "inspector.html"):
        source = templates.joinpath(name).read_text()
        assert '{% extends "layout.html" %}' in source
        assert "<head>" not in source and "<nav" not in source


def _status_with_host(server: WSGIServer, path: str, host: str | None) -> int:
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.putrequest("GET", path, skip_host=True)
        if host is not None:
            connection.putheader("Host", host)
        connection.endheaders()
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


@pytest.mark.parametrize(
    "path",
    ["/", "/shell.css", "/health", "/debug", "/source?path=mvc/routes/web.py"],
)
@pytest.mark.parametrize(
    "host",
    [
        "attacker.example:{port}",
        "attacker.example",
        "localhost:{port}",
        "127.0.0.1",
        "127.0.0.1:1",
        "127.0.0.1:{port}.attacker.example",
        "[::1]:{port}",
        "",
        None,
    ],
)
def test_foreign_host_rejected(
    running_server: WSGIServer, path: str, host: str | None
) -> None:
    port = running_server.server_port
    value = None if host is None else host.format(port=port)
    assert _status_with_host(running_server, path, value) == 400


def test_exact_local_host_accepted(running_server: WSGIServer) -> None:
    host = f"127.0.0.1:{running_server.server_port}"
    assert _status_with_host(running_server, "/", host) == 200
    assert _status_with_host(running_server, "/health", host) == 200
