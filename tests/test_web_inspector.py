"""HTTP réel : formulaire, contexte runtime, registre et rendu Forge."""

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
    target: str = "/inspector",
    fetch_site: str | None = None,
    origin: str | None = "local",
    content_type: str = "application/x-www-form-urlencoded",
) -> tuple[int, str, dict[str, str]]:
    headers = {"Content-Type": content_type}
    if origin is not None:
        headers["Origin"] = (
            f"http://127.0.0.1:{server.server_port}" if origin == "local" else origin
        )
    if fetch_site is not None:
        headers["Sec-Fetch-Site"] = fetch_site
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request(
            method,
            target,
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
    assert str(project) in fresh
    assert 'name="path" type="text" value=""' in fresh


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
            assert request(instance, "ignored", target="/project/refresh")[0] == 200
            assert calls == [Path(raw)] and ids == [
                "project-inspector",
                "project-inspector",
            ]
            calls.clear()
            assert request(instance, raw, origin="https://evil.example")[0] == 403
            assert calls == []
        finally:
            instance.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_current_project_lifecycle(server: WSGIServer, project: Path) -> None:
    assert "Aucun projet ouvert." in request(server, method="GET", target="/")[1]
    assert request(server, str(project / "mvc/.."))[0] == 200
    home = request(server, method="GET", target="/")[1]
    assert f"Projet : {project.resolve()}" in home and "Forge 1.0.0rc9" in home
    assert "Aucun projet ouvert." not in home
    assert "Fermer le projet" in home
    source = project / "requirements.txt"
    source.unlink()
    assert request(server, str(project))[0] == 200
    assert f"Projet : {project}" in request(server, method="GET", target="/")[1]
    assert "Forge 1.0.0rc9" not in request(server, method="GET", target="/")[1]
    assert request(server, target="/project/close")[0] == 200
    assert "Aucun projet ouvert." in request(server, method="GET", target="/")[1]


@pytest.mark.parametrize("bad_path", ["invalid", "missing", "file", "nul"])
def test_bad_inspection_preserves_current(
    server: WSGIServer, project: Path, bad_path: str
) -> None:
    assert request(server, str(project))[0] == 200
    invalid = project / "invalid"
    invalid.mkdir()
    paths = {
        "invalid": str(invalid),
        "missing": str(project / "missing"),
        "file": str(project / "app.py"),
        "nul": "bad\x00path",
    }
    assert request(server, paths[bad_path])[0] in (200, 400)
    home = request(server, method="GET", target="/")[1]
    assert f"Projet : {project}" in home and "Forge 1.0.0rc9" in home


@pytest.mark.parametrize("origin", [None, "null", "https://evil.example"])
@pytest.mark.parametrize("target", ["/inspector", "/project/close"])
def test_foreign_mutation_preserves_current(
    server: WSGIServer, project: Path, origin: str | None, target: str
) -> None:
    assert request(server, str(project))[0] == 200
    assert request(server, str(project), origin=origin, target=target)[0] == 403
    assert f"Projet : {project}" in request(server, method="GET", target="/")[1]


def test_close_security_and_no_writes(server: WSGIServer, project: Path) -> None:
    assert request(server, str(project))[0] == 200
    before = {
        p: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
        for p in project.rglob("*")
    }
    assert request(server, target="/project/close", fetch_site="cross-site")[0] == 403
    assert request(server, target="/project/close", method="GET")[0] != 200
    assert f"Projet : {project}" in request(server, method="GET", target="/")[1]
    assert request(server, target="/project/close")[0] == 200
    assert before == {
        p: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
        for p in project.rglob("*")
    }


def test_application_isolation_and_restart(server: WSGIServer, project: Path) -> None:
    assert request(server, str(project))[0] == 200
    for _ in range(2):
        with web.create_server(port=0) as other:
            thread = Thread(target=other.serve_forever, kwargs={"poll_interval": 0.01})
            thread.start()
            try:
                assert (
                    "Aucun projet ouvert."
                    in request(other, method="GET", target="/")[1]
                )
                assert request(other, target="/project/close")[0] == 200
                assert (
                    f"Projet : {project}"
                    in request(server, method="GET", target="/")[1]
                )
            finally:
                other.shutdown()
                thread.join(timeout=5)
                assert not thread.is_alive()


def test_refresh_empty(server: WSGIServer) -> None:
    status, html, headers = request(server, target="/project/refresh")
    assert status == 409 and "Aucun projet à actualiser." in html
    assert "no-store" in headers.get("Cache-Control", "")


def test_refresh_updates_diagnostic(server: WSGIServer, project: Path) -> None:
    assert request(server, str(project / "mvc/.."))[0] == 200
    (project / "requirements.txt").write_text("forge-mvc==2.0.0")
    (project / "mvc/views").mkdir()
    # Aucune lecture automatique : le GET conserve l'instantané précédent.
    assert "Forge 1.0.0rc9" in request(server, method="GET", target="/")[1]
    before = {
        p: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
        for p in project.rglob("*")
    }
    status, html, headers = request(server, "ignored", target="/project/refresh")
    assert status == 200 and "Projet actualisé." in html
    assert "2.0.0" in html and "1.0.0rc9" not in html
    assert "mvc/views" not in html and "mvc/models" in html
    assert f"Projet : {project.resolve()}" in html
    assert "no-store" in headers.get("Cache-Control", "")
    assert before == {
        p: (p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else None)
        for p in project.rglob("*")
    }
    assert request(server, target="/project/close")[0] == 200
    assert request(server, target="/project/refresh")[0] == 409


@pytest.mark.parametrize("change", ["structure", "missing", "file"])
def test_refresh_invalidates_current(
    server: WSGIServer, project: Path, change: str
) -> None:
    import shutil

    assert request(server, str(project))[0] == 200
    if change == "structure":
        (project / "app.py").unlink()
    else:
        shutil.rmtree(project)
        if change == "file":
            project.touch()
    status, html, _ = request(server, target="/project/refresh")
    assert status == (200 if change == "structure" else 400)
    assert "fermé" in html and "Traceback" not in html
    assert "Aucun projet ouvert." in request(server, method="GET", target="/")[1]


@pytest.mark.parametrize(
    "origin,site",
    [(None, None), ("https://evil.example", None), ("local", "cross-site")],
)
def test_refresh_security(
    server: WSGIServer, project: Path, origin: str | None, site: str | None
) -> None:
    assert request(server, str(project))[0] == 200
    (project / "app.py").unlink()
    assert (
        request(server, target="/project/refresh", origin=origin, fetch_site=site)[0]
        == 403
    )
    assert request(server, target="/project/refresh", method="GET")[0] != 200
    assert f"Projet : {project}" in request(server, method="GET", target="/")[1]


def test_route_explorer_page(server: WSGIServer, project: Path) -> None:
    status, html, headers = request(server, method="GET", target="/routes")
    assert status == 200 and "Aucun projet ouvert." in html
    assert 'href="/routes" aria-current="page"' in html
    assert "no-store" in headers.get("Cache-Control", "")
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/contact.py").write_text("invalid Python!")
    (project / "mvc/routes/__init__.py").write_text("""
from mvc.controllers.contact import ContactController
router = Router()
router.add("GET", "/<script>", ContactController.list, name="home", public=True)
router.add("POST", "/submit", handler)
""")
    assert request(server, str(project))[0] == 200
    status, html, headers = request(server, method="GET", target="/routes")
    assert status == 200 and "<table>" in html
    assert "GET" in html and "POST" in html and "home" in html
    assert "Handler</th>" in html and "ContactController.list" in html
    assert "Contrôleur</th>" in html and "mvc/controllers/contact.py" in html
    assert "Vérification</th>" in html and "Non vérifiable" in html
    assert "Oui" in html and "Non" in html and "—" in html
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "no-store" in headers.get("Cache-Control", "")
    (project / "mvc/routes/__init__.py").unlink()
    assert "absente" in request(server, method="GET", target="/routes")[1]


@pytest.mark.parametrize(
    "body,expected",
    [
        (
            'return BaseController.render("contacts/<script>.html")',
            "contacts/&lt;script&gt;.html",
        ),
        ("return BaseController.render(template)", "Dynamique"),
        (
            'if condition: return BaseController.render("one.html")\n'
            '        return BaseController.render("two.html")',
            "Plusieurs",
        ),
    ],
)
def test_route_templates(
    server: WSGIServer, project: Path, body: str, expected: str
) -> None:
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/contact.py").write_text(
        "class ContactController:\n    def list(self):\n        " + body + "\n"
    )
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.contact import ContactController\nrouter = Router()\n"
        'router.add("GET", "/", ContactController.list)\n'
    )
    assert request(server, str(project))[0] == 200
    status, html, headers = request(server, method="GET", target="/routes")
    assert status == 200 and "Template</th>" in html and expected in html
    assert "<script>" not in html
    assert headers.get("Cache-Control") == "no-store"


@pytest.mark.parametrize(
    "reference,present,label",
    [
        ("contacts/list.html", True, "Présent"),
        ("contacts/list.html", False, "Absent"),
        ("../<script>.html", False, "Chemin refusé"),
    ],
)
def test_web_template_presence(
    server: WSGIServer,
    project: Path,
    reference: str,
    present: bool,
    label: str,
) -> None:
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/home.py").write_text(
        "class HomeController:\n    def index(self):\n"
        f"        return BaseController.render({reference!r})\n"
    )
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
    )
    if present:
        (project / "mvc/views/contacts").mkdir(parents=True)
        (project / "mvc/views/contacts/list.html").write_text("anything")
    assert request(server, str(project))[0] == 200
    status, html, headers = request(server, method="GET", target="/routes")
    assert status == 200 and "Présence</th>" in html and f"<td>{label}</td>" in html
    assert "<script>" not in html
    if "<script>" in reference:
        assert "&lt;script&gt;" in html
    assert headers.get("Cache-Control") == "no-store"


@pytest.mark.parametrize(
    "content,label",
    [
        ('{% extends "absent.html" %}{{ unknown }}', "Valide"),
        ("{% <script> %}", "Invalide"),
        ("{% if title %}", "Invalide"),
    ],
)
def test_web_jinja_syntax(
    server: WSGIServer,
    project: Path,
    content: str,
    label: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jinja2 import Environment, TemplateSyntaxError

    original_parse = Environment.parse

    def parsed(environment: Environment, source: str, *args: object, **kwargs: object):
        if source == content and "<script>" in source:
            raise TemplateSyntaxError("diagnostic <script> non fiable", 1)
        return original_parse(environment, source)

    monkeypatch.setattr(Environment, "parse", parsed)
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/home.py").write_text(
        "class HomeController:\n    def index(self):\n"
        '        return BaseController.render("home.html")\n'
    )
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
    )
    (project / "mvc/views").mkdir()
    (project / "mvc/views/home.html").write_text(content)
    assert request(server, str(project))[0] == 200
    status, html, headers = request(server, method="GET", target="/routes")
    assert status == 200 and "Jinja</th>" in html
    assert f"<td>{label}</td>" in html and "<td>Présent</td>" in html
    assert "<script>" not in html and "Traceback" not in html
    if "<script>" in content:
        assert "&lt;" in html
    if label == "Invalide":
        assert "home.html:1" in html
    assert headers.get("Cache-Control") == "no-store"


def test_web_template_dependencies(server: WSGIServer, project: Path) -> None:
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/home.py").write_text(
        "class HomeController:\n"
        '    def index(self): return BaseController.render("home.html")\n'
    )
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
        'router.add("POST", "/", HomeController.index)\n'
    )
    (project / "mvc/views").mkdir()
    (project / "mvc/views/home.html").write_text(
        '{% extends "base.html" %}\n'
        '{% include "contacts/<script>.html" %}\n'
        "{% include dynamic_name %}\n"
        '{% include "../secret.html" %}'
    )
    (project / "mvc/views/base.html").write_bytes(b"invalid Jinja \xff")
    assert request(server, str(project))[0] == 200
    status, html, headers = request(server, method="GET", target="/routes")
    assert status == 200 and "extends: base.html" in html
    assert "include: contacts/&lt;script&gt;.html" in html
    assert "include: dynamique — —" in html and "<script>" not in html
    assert "extends: base.html — Présent" in html
    assert "include: contacts/&lt;script&gt;.html — Absent" in html
    assert "include: ../secret.html — Chemin refusé" in html
    graph_html = html.split('class="route-graph"', 1)[1]
    assert "Vue des relations" in graph_html and "GET /" in graph_html
    assert "HomeController.index" in graph_html
    assert "mvc/controllers/home.py" in graph_html and "home.html" in graph_html
    assert "extends</strong> → base.html" in graph_html
    assert "includes</strong> → contacts/&lt;script&gt;.html" in graph_html
    assert "contacts/&lt;script&gt;.html" in graph_html
    assert ">Absent</text>" in graph_html
    assert graph_html.count("<title>HomeController.index</title>") == 1
    assert graph_html.count(">handles</text>") == 2
    assert "<svg " in graph_html and graph_html.count("<marker ") == 1
    assert 'role="img"' in graph_html and "viewBox=" in graph_html
    assert "dynamic_name" not in graph_html and "dynamique" not in graph_html
    assert "<script>" not in graph_html and "<table>" in html
    assert "<td>Présent</td><td>Valide</td>" in html
    assert headers.get("Cache-Control") == "no-store"


@pytest.mark.parametrize(
    "content,label",
    [
        ('{% extends "never.html" %}{{ unknown }}', "Valide"),
        ("{% if user %}", "Invalide"),
        ("injected-error", "Invalide"),
    ],
)
def test_web_dependency_syntax(
    server: WSGIServer,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: str,
    label: str,
) -> None:
    from jinja2 import Environment, TemplateSyntaxError

    original_parse = Environment.parse

    def parsed(environment: Environment, source: str, *args: object, **kwargs: object):
        if source == "injected-error":
            raise TemplateSyntaxError("diagnostic <script> non fiable", 1)
        return original_parse(environment, source)

    monkeypatch.setattr(Environment, "parse", parsed)
    (project / "mvc/controllers").mkdir()
    (project / "mvc/controllers/home.py").write_text(
        "class HomeController:\n"
        '    def index(self): return BaseController.render("home.html")\n'
    )
    (project / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import HomeController\nrouter = Router()\n"
        'router.add("GET", "/", HomeController.index)\n'
    )
    (project / "mvc/views").mkdir()
    (project / "mvc/views/home.html").write_text(
        '{% include "part.html" %}{% include "absent.html" %}{% include dynamic %}'
    )
    (project / "mvc/views/part.html").write_text(content)
    assert request(server, str(project))[0] == 200
    status, html, headers = request(server, method="GET", target="/routes")
    assert status == 200 and f"include: part.html — Présent — {label}" in html
    assert "include: absent.html — Absent</li>" in html
    assert "include: dynamique — —</li>" in html
    assert "<script>" not in html and "Traceback" not in html
    if content == "injected-error":
        assert "&lt;script&gt;" in html
    if label == "Invalide":
        assert "part.html:1" in html
    assert headers.get("Cache-Control") == "no-store"
