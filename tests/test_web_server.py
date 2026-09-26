"""HTTP réel sur un port éphémère et cycle de vie sans thread résiduel."""

import errno
import inspect
from collections.abc import Iterator
from http.client import HTTPConnection
from http.server import HTTPServer
from importlib.resources import files
from pathlib import Path
from threading import Thread

import pytest

from forge_design.forge import project_detection, project_root, project_version
from forge_design.tools import project_inspector
from forge_design.web import server as web


@pytest.fixture
def running_server() -> Iterator[HTTPServer]:
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


def test_local_binding_and_response(running_server: HTTPServer) -> None:
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
        assert "<h1>Forge Design</h1>" in html
        assert "Aucun projet ouvert." in html
    finally:
        connection.close()


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/.env",
        "/../../etc/passwd",
        "/?project=x",
        "/%2e%2e/%2e%2e/etc/passwd",
        "/..%2f..%2fetc/passwd",
        "/%252e%252e/etc/passwd",
        "/templates/index.html",
    ],
)
def test_no_other_route(running_server: HTTPServer, path: str) -> None:
    connection = HTTPConnection("127.0.0.1", running_server.server_port, timeout=3)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        assert response.status == 404
        response.read()
    finally:
        connection.close()


def test_no_project_access(
    running_server: HTTPServer, monkeypatch: pytest.MonkeyPatch
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
        assert self == resource and mode == "rb"
        return original_open(self, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", guarded_open)
    test_local_binding_and_response(running_server)


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

    def create(host: str, port: int) -> HTTPServer:
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
    running_server: HTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "index.html").write_text("must not be served")
    monkeypatch.chdir(tmp_path)
    test_local_binding_and_response(running_server)


def test_arbitrary_file_not_served(
    running_server: HTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
