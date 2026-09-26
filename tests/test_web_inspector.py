"""Tranche HTTP réelle : formulaire stateless, registre, Bridge et Jinja Forge."""

from collections.abc import Iterator
from dataclasses import dataclass
from html import escape
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode
from wsgiref.simple_server import WSGIServer

import pytest

from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.project_inspector import ProjectInspection
from forge_design.web import server as web


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ("app.py", "bootstrap.py", "config.py"):
        (tmp_path / name).write_text("raise AssertionError('must not execute')")
    (tmp_path / "mvc/routes").mkdir(parents=True)
    (tmp_path / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    return tmp_path


@pytest.fixture
def server() -> Iterator[WSGIServer]:
    with web.create_server(port=0) as instance:
        thread = Thread(target=instance.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def request(
    server: WSGIServer,
    path: str | None = None,
    *,
    method: str = "POST",
    origin: str | None = "local",
    content_type: str = "application/x-www-form-urlencoded",
) -> tuple[int, str, dict[str, str]]:
    headers = {"Content-Type": content_type}
    if origin is not None:
        headers["Origin"] = (
            f"http://127.0.0.1:{server.server_port}" if origin == "local" else origin
        )
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(
            method,
            "/inspector",
            urlencode({"path": path}) if path is not None else "",
            headers,
        )
        response = connection.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        connection.close()


def test_get_form(server: WSGIServer) -> None:
    status, html, headers = request(server, method="GET")
    assert status == 200
    assert '<form action="/inspector" method="post">' in html
    assert 'name="path"' in html and "Inspecter" in html
    assert "Set-Cookie" not in headers
    assert "no-store" in headers.get("Cache-Control", "")


def test_valid_project(server: WSGIServer, project: Path) -> None:
    status, html, headers = request(server, str(project / "mvc/.."))
    assert status == 200 and "Projet Forge reconnu" in html
    assert str(project.resolve()) in html
    assert "1.0.0rc9" in html and "requirements.txt" in html
    assert "Avertissements" in html and "mvc/views" in html
    assert "Set-Cookie" not in headers
    assert "no-store" in headers.get("Cache-Control", "")
    _, fresh, _ = request(server, method="GET")
    assert str(project) not in fresh


def test_invalid_structure(server: WSGIServer, tmp_path: Path) -> None:
    status, html, _ = request(server, str(tmp_path))
    assert status == 200 and "Projet Forge non reconnu" in html
    assert "app.py" in html and "Traceback" not in html


@pytest.mark.parametrize("kind", ["missing", "file", "nul"])
def test_root_error(server: WSGIServer, tmp_path: Path, kind: str) -> None:
    target = tmp_path / "target"
    if kind == "file":
        target.touch()
    path = "bad\x00path" if kind == "nul" else str(target)
    status, html, _ = request(server, path)
    assert status == 400 and 'role="alert"' in html
    assert "Traceback" not in html


@pytest.mark.parametrize(
    "content",
    [None, "forge-mvc>=1.0", "forge-mvc==bad", "forge-mvc==1.0\nforge-mvc==2.0"],
)
def test_version_problem(
    server: WSGIServer, project: Path, content: str | None
) -> None:
    source = project / "requirements.txt"
    if content is None:
        source.unlink()
    else:
        source.write_text(content)
    status, html, _ = request(server, str(project))
    assert status == 200 and "Projet Forge reconnu" in html
    assert "indéterminée" in html and "Avertissements" in html


@pytest.mark.parametrize("path", [None, "", "   ", "x" * 4097])
def test_invalid_field(server: WSGIServer, path: str | None) -> None:
    status, html, _ = request(server, path)
    assert status == 400 and 'role="alert"' in html


@pytest.mark.parametrize(
    "origin", [None, "null", "https://evil.example", "http://127.0.0.1:1"]
)
def test_origin_required(server: WSGIServer, project: Path, origin: str | None) -> None:
    status, html, _ = request(server, str(project), origin=origin)
    assert status == 403 and "Origine" in html
    assert "Projet Forge reconnu" not in html


def test_wrong_content_type(server: WSGIServer) -> None:
    assert request(server, "x", content_type="application/json")[0] == 415


def test_no_project_changes(server: WSGIServer, project: Path) -> None:
    def snapshot() -> dict[str, tuple[int, bytes | None]]:
        return {
            str(p): (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
            for p in project.rglob("*")
        }

    before = snapshot()
    assert request(server, str(project))[0] == 200
    assert snapshot() == before


def test_registry_delegation_and_escaping(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Path] = []
    ids: list[str] = []
    compositions: list[bool] = []

    @dataclass(frozen=True)
    class FakeInspector:
        id: str = "project-inspector"
        name: str = "Test"
        description: str = "Test"

        def run(self, project_root: Path) -> ProjectInspection:
            calls.append(project_root)
            return ProjectInspection(
                project_root, True, None, None, (), ("<script>bad</script>",)
            )

    class Registry(ToolRegistry):
        def get(self, tool_id: str):
            ids.append(tool_id)
            return super().get(tool_id)

    def compose() -> ToolRegistry:
        compositions.append(True)
        registry = Registry()
        registry.register(FakeInspector())
        return registry

    monkeypatch.setattr(web, "create_tool_registry", compose)
    with web.create_server(port=0) as instance:
        thread = Thread(target=instance.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            raw = '  not-existing-<script>"&  '
            status, html, _ = request(instance, raw)
            assert status == 200
            assert calls == [Path(raw)] and ids == ["project-inspector"]
            assert compositions == [True]
            assert "<script>" not in html and "&lt;script&gt;" in html
            assert escape(raw, quote=True).replace("&quot;", "&#34;") in html
            calls.clear()
            assert request(instance, raw, origin="https://evil.example")[0] == 403
            assert calls == []
        finally:
            instance.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()
