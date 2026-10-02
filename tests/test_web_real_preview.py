"""Preview réelle intégrée à l'application Web (FD-REALPREVIEW-004).

Trois couches : le runtime seul (contrôleur et proxy doubles), l'application
Web réelle sur un port éphémère avec un runtime double injecté, puis le vrai
runner et le vrai proxy sur des projets Forge synthétiques (squelette rc9).
"""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from html import unescape
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import pytest
from core.security.csp import build_csp_header
from real_preview_support import make_project as make_forge_project
from real_preview_support import processes_mentioning, wait_until_dead
from test_web_editor import DESIGN, make_root

import forge_design.current_project as current_project
from forge_design.real_preview import (
    RealPreviewController,
    RealPreviewError,
    RealPreviewStatus,
)
from forge_design.recent_projects import RecentProjects
from forge_design.web import server as web
from forge_design.web.real_preview import (
    REAL_PREVIEW_WARNING,
    RealPreviewRuntime,
    real_preview_frame_url,
)

FORM = "application/x-www-form-urlencoded"
PROXY_PORT = 45678
RUNNER_PORT = 40001
Event = tuple[Any, ...]


# ── Doubles ──────────────────────────────────────────────────────────────────


def _status(state: Any, root: Path | None, **extra: Any) -> RealPreviewStatus:
    values: dict[str, Any] = {
        "pid": None,
        "port": None,
        "exit_code": None,
        "error": None,
        "logs": (),
    }
    values.update(extra)
    return RealPreviewStatus(state, root, **values)


class FakeController(RealPreviewController):
    """Runner double : aucune exécution, transitions enregistrées."""

    def __init__(self, events: list[Event]) -> None:
        super().__init__()
        self.events = events
        self.current = _status("stopped", None)
        self.start_state: Any = "running"
        self.stop_ok = True
        self.on_start: Callable[[], None] | None = None

    def status(self) -> RealPreviewStatus:
        return self.current

    def start(self, project_root: Any) -> RealPreviewStatus:
        root = Path(project_root)
        self.events.append(("runner-start", root))
        if self.on_start is not None:
            self.on_start()
        if self.start_state == "running":
            self.current = _status("running", root, pid=4242, port=RUNNER_PORT)
        else:
            self.current = _status(
                "failed",
                root,
                exit_code=5,
                error="import du projet impossible",
                logs=("Traceback (most recent call last):", "RuntimeError: boom"),
            )
        return self.current

    def stop(self) -> RealPreviewStatus:
        self.events.append(("runner-stop",))
        root = self.current.project_root
        if not self.stop_ok:
            self.current = _status(
                "failed",
                root,
                pid=4242,
                error="Processus de preview impossible à arrêter.",
            )
        else:
            self.current = _status("stopped", root, exit_code=-15)
        return self.current


class FakeProxy:
    def __init__(self, events: list[Event], *, die: bool = False) -> None:
        self.events = events
        self.server_port = PROXY_PORT
        self.die = die
        self._stop = threading.Event()
        self.closed = False

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        if not self.die:
            self._stop.wait()

    def shutdown(self) -> None:
        self.events.append(("proxy-shutdown",))
        self._stop.set()

    def server_close(self) -> None:
        self.events.append(("proxy-close",))
        self.closed = True


class Harness:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self.controller = FakeController(self.events)
        self.proxies: list[FakeProxy] = []
        self.proxy_error: Exception | None = None
        self.proxy_dies = False
        self.runtime = RealPreviewRuntime(self.controller, proxy_factory=self.factory)

    def factory(self, controller: RealPreviewController, origin: str) -> FakeProxy:
        assert controller is self.controller
        self.events.append(("proxy-create", origin))
        if self.proxy_error is not None:
            raise self.proxy_error
        proxy = FakeProxy(self.events, die=self.proxy_dies)
        self.proxies.append(proxy)
        return proxy

    def names(self) -> list[str]:
        return [event[0] for event in self.events]

    @property
    def starts(self) -> list[Event]:
        return [event for event in self.events if event[0] == "runner-start"]


@pytest.fixture
def harness() -> Harness:
    return Harness()


# ── Runtime seul ─────────────────────────────────────────────────────────────

ORIGIN = "http://127.0.0.1:8765"


def test_runtime_disabled_without_origin(harness: Harness, tmp_path: Path) -> None:
    assert not harness.runtime.enabled
    with pytest.raises(RealPreviewError, match="indisponible"):
        harness.runtime.start(tmp_path)
    assert harness.events == []


@pytest.mark.parametrize("origin", ["http://localhost:8765", "*", "http://127.0.0.1"])
def test_runtime_origin_validated(harness: Harness, origin: str) -> None:
    with pytest.raises(ValueError):
        harness.runtime.bind_editor_origin(origin)


def test_runtime_start_and_stop_order(harness: Harness, tmp_path: Path) -> None:
    runtime = harness.runtime
    runtime.bind_editor_origin(ORIGIN)
    status = runtime.start(tmp_path)
    assert (status.state, status.proxy_origin) == (
        "running",
        f"http://127.0.0.1:{PROXY_PORT}",
    )
    assert harness.events == [
        ("runner-stop",),
        ("runner-start", tmp_path),
        ("proxy-create", ORIGIN),
    ]
    harness.events.clear()
    assert runtime.stop() is True
    # Proxy d'abord (plus aucune requête relayée), runner ensuite.
    assert harness.names() == ["proxy-shutdown", "proxy-close", "runner-stop"]
    assert runtime.status().proxy_origin is None
    assert all(
        not thread.name.startswith("forge-design-real-preview")
        for thread in threading.enumerate()
    )


def test_runtime_same_project_not_restarted(harness: Harness, tmp_path: Path) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.runtime.start(tmp_path)
    harness.events.clear()
    assert harness.runtime.start(tmp_path).state == "running"
    assert harness.events == []
    harness.runtime.close()


def test_runtime_other_project_stops_previous(harness: Harness, tmp_path: Path) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.runtime.start(tmp_path / "a")
    harness.events.clear()
    harness.runtime.start(tmp_path / "b")
    assert harness.names() == [
        "proxy-shutdown",
        "proxy-close",
        "runner-stop",
        "runner-start",
        "proxy-create",
    ]
    harness.runtime.close()


def test_runtime_runner_failure_creates_no_proxy(
    harness: Harness, tmp_path: Path
) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.controller.start_state = "failed"
    status = harness.runtime.start(tmp_path)
    assert (status.state, status.proxy_origin) == ("failed", None)
    assert "proxy-create" not in harness.names()
    assert status.logs[-1] == "RuntimeError: boom"


@pytest.mark.parametrize("error", [OSError("port"), ValueError("origine")])
def test_runtime_proxy_failure_stops_runner(
    harness: Harness, tmp_path: Path, error: Exception
) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.proxy_error = error
    status = harness.runtime.start(tmp_path)
    assert harness.names()[-2:] == ["proxy-create", "runner-stop"]
    assert (status.state, status.error) == (
        "failed",
        "Le proxy de preview n'a pas pu être créé.",
    )
    assert status.proxy_origin is None


def test_runtime_detects_dead_runner(harness: Harness, tmp_path: Path) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.runtime.start(tmp_path)
    harness.controller.current = _status(
        "failed", tmp_path, exit_code=-9, error="arrêt inattendu (signal 9)"
    )
    harness.events.clear()
    status = harness.runtime.status()
    assert (status.state, status.proxy_origin) == ("failed", None)
    assert harness.names() == ["proxy-shutdown", "proxy-close"]
    assert harness.proxies[0].closed


def test_runtime_detects_dead_proxy(harness: Harness, tmp_path: Path) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.proxy_dies = True
    harness.runtime.start(tmp_path)
    # Le thread du proxy se termine seul (serve_forever retourne).
    for thread in threading.enumerate():
        if thread.name == "forge-design-real-preview-proxy":
            thread.join(2)
    harness.events.clear()
    status = harness.runtime.status()
    assert harness.names() == ["proxy-close", "runner-stop"]
    assert status.state == "failed"
    assert status.error is not None and "proxy" in status.error


def test_runtime_concurrent_start_refused(harness: Harness, tmp_path: Path) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    errors: list[Exception] = []

    def again() -> None:
        try:
            harness.runtime.start(tmp_path)
        except RealPreviewError as error:
            errors.append(error)

    harness.controller.on_start = again
    harness.runtime.start(tmp_path)
    assert len(errors) == 1 and "en cours" in str(errors[0])
    assert len(harness.starts) == 1
    harness.runtime.close()


def test_runtime_stop_failure_reported(harness: Harness, tmp_path: Path) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.runtime.start(tmp_path)
    harness.controller.stop_ok = False
    assert harness.runtime.stop() is False
    assert harness.runtime.status().state == "failed"


def test_runtime_close_idempotent(harness: Harness, tmp_path: Path) -> None:
    harness.runtime.bind_editor_origin(ORIGIN)
    harness.runtime.start(tmp_path)
    harness.runtime.close()
    harness.runtime.close()
    assert harness.names().count("proxy-close") == 1
    assert not harness.runtime.enabled
    with pytest.raises(RealPreviewError):
        harness.runtime.start(tmp_path)


def test_runtime_stop_idempotent(harness: Harness) -> None:
    assert harness.runtime.stop() and harness.runtime.stop()
    assert "proxy-close" not in harness.names()


@pytest.mark.parametrize(
    ("origin", "path", "expected"),
    [
        ("http://127.0.0.1:45678", "/", "http://127.0.0.1:45678/"),
        ("http://127.0.0.1:45678", "/contacts", "http://127.0.0.1:45678/contacts"),
    ],
)
def test_frame_url(origin: str, path: str, expected: str) -> None:
    assert real_preview_frame_url(origin, path) == expected


@pytest.mark.parametrize(
    ("origin", "path"),
    [
        ("http://127.0.0.1:45678", "http://evil.example/"),
        ("http://127.0.0.1:45678", "//evil.example/"),
        ("http://127.0.0.1:45678", "/users/{id}"),
        ("http://127.0.0.1:45678", "contacts"),
        ("http://127.0.0.1:45678", "/a?b=1"),
        ("http://localhost:45678", "/"),
        ("http://127.0.0.1:45678/x", "/"),
    ],
)
def test_frame_url_refused(origin: str, path: str) -> None:
    with pytest.raises(ValueError):
        real_preview_frame_url(origin, path)


# ── Application Web avec runtime double ──────────────────────────────────────


ROUTES = """from core.http.router import Router
from mvc.controllers.contacts_controller import ContactsController

router = Router()
router.add("GET", "/contacts", ContactsController.index, public={public})
"""
CONTROLLER = """from core.mvc.controller import BaseController


class ContactsController:
    @staticmethod
    def index(request):
        return BaseController.render("contacts/list.html", {{}})
"""


def add_routes(root: Path, *, public: bool = True) -> Path:
    (root / "mvc/routes/__init__.py").write_text(ROUTES.format(public=public))
    (root / "mvc/controllers").mkdir(exist_ok=True)
    (root / "mvc/controllers/contacts_controller.py").write_text(CONTROLLER.format())
    return root


def designed_project(path: Path, *, public: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return add_routes(make_root(path), public=public)


@contextmanager
def serving(
    runtime: RealPreviewRuntime | None = None,
) -> Generator[web.ForgeDesignServer, None, None]:
    with web.create_server(
        port=0, recent_projects=RecentProjects(), real_preview=runtime
    ) as server:
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}
        )
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)
            assert not thread.is_alive()


Reply = tuple[int, str, dict[str, str]]


def http(
    server: web.ForgeDesignServer,
    method: str,
    url: str,
    fields: list[tuple[str, str]] | None = None,
    *,
    origin: str | None = "local",
    site: str | None = "same-origin",
    content_type: str = FORM,
) -> Reply:
    headers: dict[str, str] = {}
    if method == "POST":
        if origin is not None:
            headers["Origin"] = (
                f"http://127.0.0.1:{server.server_port}"
                if origin == "local"
                else origin
            )
        if site is not None:
            headers["Sec-Fetch-Site"] = site
        headers["Content-Type"] = content_type
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=30)
    try:
        connection.request(method, url, urlencode(fields or []), headers)
        response = connection.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        connection.close()


def open_project(server: web.ForgeDesignServer, root: Path) -> Reply:
    return http(server, "POST", "/inspector", [("path", str(root))])


def editor(server: web.ForgeDesignServer, design: str = DESIGN) -> Reply:
    return http(server, "GET", "/editor?" + urlencode({"design": design}))


def start(
    server: web.ForgeDesignServer, *extra: tuple[str, str], **options: Any
) -> Reply:
    return http(
        server,
        "POST",
        "/editor/real-preview/start",
        [("design", DESIGN), *extra],
        **options,
    )


def stop(
    server: web.ForgeDesignServer, *extra: tuple[str, str], **options: Any
) -> Reply:
    return http(
        server,
        "POST",
        "/editor/real-preview/stop",
        [("design", DESIGN), *extra],
        **options,
    )


@pytest.fixture
def context_events(monkeypatch: pytest.MonkeyPatch, harness: Harness) -> list[Event]:
    """Enregistre set_project/clear du contexte dans le même journal que le runtime."""
    original_set = current_project.CurrentProjectContext.set_project
    original_clear = current_project.CurrentProjectContext.clear

    def set_project(self: Any, inspection: Any) -> None:
        harness.events.append(("context-set", inspection.root))
        original_set(self, inspection)

    def clear(self: Any) -> None:
        harness.events.append(("context-clear",))
        original_clear(self)

    monkeypatch.setattr(
        current_project.CurrentProjectContext, "set_project", set_project
    )
    monkeypatch.setattr(current_project.CurrentProjectContext, "clear", clear)
    return harness.events


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return designed_project(tmp_path / "a").resolve()


@pytest.fixture
def server(harness: Harness) -> Iterator[web.ForgeDesignServer]:
    with serving(harness.runtime) as running:
        yield running


IFRAME = re.compile(r"<iframe class=\"real-preview-frame\"[^>]*>")


def iframe(html: str) -> str | None:
    match = IFRAME.search(html)
    return match.group(0) if match else None


def test_origin_bound_to_effective_port(
    harness: Harness, server: web.ForgeDesignServer
) -> None:
    assert server.real_preview is harness.runtime
    assert harness.runtime.enabled
    assert server.server_port not in (0, 8765)


def test_reading_pages_never_starts(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    for url in (
        "/",
        "/inspector",
        "/routes",
        "/editor",
        "/editor?" + urlencode({"design": DESIGN}),
        "/editor/preview?" + urlencode({"design": DESIGN, "mode": "desktop"}),
    ):
        assert http(server, "GET", url)[0] == 200, url
    http(server, "POST", "/project/open-recent", [("recent", str(project_root))])
    http(server, "POST", "/project/refresh")
    assert harness.starts == []


def test_editor_offers_start_with_warning(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    status, html, headers = editor(server)
    assert status == 200
    page = unescape(html)
    assert '<h2 id="preview-title">Prévisualisation indicative</h2>' in html
    assert '<h2 id="real-preview-title">Preview réelle</h2>' in html
    assert "Route : <code>/contacts</code>" in page
    assert REAL_PREVIEW_WARNING in page
    assert 'action="/editor/real-preview/start"' in html
    assert iframe(html) is None
    assert headers["Content-Security-Policy"] == build_csp_header()
    assert harness.starts == []


@pytest.mark.parametrize(
    ("options", "status"),
    [
        ({"origin": None}, 403),
        ({"origin": "http://evil.example"}, 403),
        ({"origin": "http://127.0.0.1:1"}, 403),
        ({"site": "cross-site"}, 403),
        ({"content_type": "text/plain"}, 415),
        ({"content_type": "multipart/form-data"}, 415),
    ],
)
def test_start_requires_local_form(
    harness: Harness,
    server: web.ForgeDesignServer,
    project_root: Path,
    options: dict[str, Any],
    status: int,
) -> None:
    open_project(server, project_root)
    assert start(server, **options)[0] == status
    assert stop(server, **options)[0] == status
    assert harness.events == [] or "runner-start" not in harness.names()


@pytest.mark.parametrize(
    "extra",
    [
        ("route", "/admin"),
        ("port", "1234"),
        ("url", "http://127.0.0.1:1/admin"),
        ("path", "/admin"),
        ("action", "start"),
        ("design", DESIGN),
    ],
)
def test_start_refuses_unexpected_or_duplicate_fields(
    harness: Harness,
    server: web.ForgeDesignServer,
    project_root: Path,
    extra: tuple[str, str],
) -> None:
    open_project(server, project_root)
    assert start(server, extra)[0] == 400
    assert harness.starts == []


def test_start_requires_design_field(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    reply = http(server, "POST", "/editor/real-preview/start", [("node", "")])
    assert reply[0] == 400 and harness.starts == []


def test_start_without_project(harness: Harness, server: web.ForgeDesignServer) -> None:
    assert start(server)[0] == 409
    assert harness.starts == []


def _remove(relative: str) -> Callable[[Path], None]:
    def damage(root: Path) -> None:
        (root / relative).unlink()

    return damage


def _protect(root: Path) -> None:
    add_routes(root, public=False)


@pytest.mark.parametrize(
    ("damage", "status", "message"),
    [
        (_remove("mvc/views/" + DESIGN), 404, "Design introuvable."),
        (_remove("mvc/views/contacts/list.view.json"), 409, "Contrat indisponible"),
        (_protect, 409, "Route protégée"),
        (_remove("mvc/routes/__init__.py"), 409, "Routes du projet illisibles"),
        (_remove("mvc/views/contacts/list.html"), 409, "absent"),
    ],
)
def test_start_unavailable_never_starts(
    harness: Harness,
    server: web.ForgeDesignServer,
    project_root: Path,
    damage: Callable[[Path], Any],
    status: int,
    message: str,
) -> None:
    open_project(server, project_root)
    damage(project_root)
    reply = start(server)
    assert reply[0] == status
    assert message in unescape(reply[1])
    assert harness.starts == []


def test_start_running_iframe_and_csp(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    status, _, headers = start(server, ("node", ""), ("preview", "desktop"))
    assert status == 303
    assert headers["Location"] == "/editor?" + urlencode(
        {"design": DESIGN, "notice": "real-started"}
    )
    assert harness.starts == [("runner-start", project_root)]
    # Origine d'encadrement = port réellement lié par Forge Design.
    assert ("proxy-create", f"http://127.0.0.1:{server.server_port}") in harness.events
    status, html, headers = editor(server)
    frame = iframe(html)
    assert frame is not None
    assert f'src="http://127.0.0.1:{PROXY_PORT}/contacts"' in frame
    assert 'sandbox="allow-scripts allow-same-origin"' in frame
    assert 'referrerpolicy="no-referrer"' in frame
    assert 'title="Preview réelle"' in frame
    for forbidden in (
        "allow-forms",
        "allow-popups",
        "allow-top-navigation",
        "allow-downloads",
        "allow-modals",
    ):
        assert forbidden not in html
    assert str(RUNNER_PORT) not in html
    assert (
        "Preview réelle démarrée."
        in http(
            server,
            "GET",
            "/editor?" + urlencode({"design": DESIGN, "notice": "real-started"}),
        )[1]
    )
    assert 'action="/editor/real-preview/stop"' in html
    assert headers["Content-Security-Policy"] == (
        build_csp_header() + f"; frame-src 'self' http://127.0.0.1:{PROXY_PORT}"
    )
    assert headers["X-Frame-Options"] == "DENY"
    # Autres pages : CSP Forge inchangée ; preview statique : sa propre politique.
    assert http(server, "GET", "/")[2]["Content-Security-Policy"] == build_csp_header()
    preview = http(
        server,
        "GET",
        "/editor/preview?" + urlencode({"design": DESIGN, "mode": "desktop"}),
    )
    assert preview[0] == 200
    assert "frame-ancestors 'self'" in preview[2]["Content-Security-Policy"]
    assert preview[2]["X-Frame-Options"] == "SAMEORIGIN"
    assert '<iframe class="preview-frame preview-frame--desktop"' in html


def test_start_twice_same_project(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    assert start(server)[0] == 303
    assert len(harness.starts) == 1 and len(harness.proxies) == 1


def test_start_runner_failure(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    harness.controller.start_state = "failed"
    status, _, headers = start(server)
    assert status == 303 and "notice=real-failed" in headers["Location"]
    assert harness.proxies == []
    _, html, headers = editor(server)
    page = unescape(html)
    assert "import du projet impossible" in page
    assert "RuntimeError: boom" in page
    assert "Démarrer à nouveau" in page
    assert iframe(html) is None
    assert headers["Content-Security-Policy"] == build_csp_header()


def test_start_proxy_failure(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    harness.proxy_error = OSError("bind")
    assert "notice=real-failed" in start(server)[2]["Location"]
    assert harness.names()[-2:] == ["proxy-create", "runner-stop"]
    _, html, _ = editor(server)
    assert "Le proxy de preview n&#39;a pas pu être créé." in html or (
        "Le proxy de preview n'a pas pu être créé." in unescape(html)
    )
    assert iframe(html) is None


def test_stop_closes_proxy_then_runner(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    harness.events.clear()
    status, _, headers = stop(server, ("node", ""), ("preview", "mobile"))
    assert status == 303
    assert headers["Location"] == "/editor?" + urlencode(
        {"design": DESIGN, "preview": "mobile", "notice": "real-stopped"}
    )
    assert harness.names() == ["proxy-shutdown", "proxy-close", "runner-stop"]
    _, html, headers = editor(server)
    assert iframe(html) is None
    assert headers["Content-Security-Policy"] == build_csp_header()
    assert f"127.0.0.1:{PROXY_PORT}" not in html


def test_stop_is_idempotent(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    assert stop(server)[0] == 303
    harness.controller.start_state = "failed"
    start(server)
    assert stop(server)[0] == 303
    assert stop(server)[0] == 303


def test_stop_does_not_need_readable_design(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    (project_root / "mvc/views" / DESIGN).unlink()
    assert stop(server)[0] == 303
    assert harness.names()[-1] == "runner-stop"


def test_stop_failure_is_reported(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    harness.controller.stop_ok = False
    status, html, _ = stop(server)
    assert status == 500
    assert "Preview réelle impossible à arrêter." in unescape(html)


# ── Cycle de vie du projet ───────────────────────────────────────────────────


def test_close_stops_before_clear(
    harness: Harness,
    context_events: list[Event],
    server: web.ForgeDesignServer,
    project_root: Path,
) -> None:
    open_project(server, project_root)
    start(server)
    context_events.clear()
    assert http(server, "POST", "/project/close")[0] == 200
    names = harness.names()
    assert names.index("runner-stop") < names.index("context-clear")
    assert names[:2] == ["proxy-shutdown", "proxy-close"]
    assert "Aucun projet ouvert." in http(server, "GET", "/")[1]


def test_close_keeps_project_if_stop_fails(
    harness: Harness,
    context_events: list[Event],
    server: web.ForgeDesignServer,
    project_root: Path,
) -> None:
    open_project(server, project_root)
    start(server)
    harness.controller.stop_ok = False
    assert http(server, "POST", "/project/close")[0] == 409
    assert "context-clear" not in harness.names()
    assert str(project_root) in http(server, "GET", "/")[1]


def test_switch_project_stops_before_activation(
    harness: Harness,
    context_events: list[Event],
    server: web.ForgeDesignServer,
    project_root: Path,
    tmp_path: Path,
) -> None:
    other = designed_project(tmp_path / "b").resolve()
    open_project(server, project_root)
    start(server)
    context_events.clear()
    assert open_project(server, other)[0] == 200
    names = harness.names()
    assert names.index("runner-stop") < names.index("context-set")
    assert ("context-set", other) in harness.events
    assert str(other) in http(server, "GET", "/")[1]


def test_switch_by_recent_stops_before_activation(
    harness: Harness,
    context_events: list[Event],
    server: web.ForgeDesignServer,
    project_root: Path,
    tmp_path: Path,
) -> None:
    other = designed_project(tmp_path / "b").resolve()
    open_project(server, other)
    open_project(server, project_root)
    start(server)
    context_events.clear()
    http(server, "POST", "/project/open-recent", [("recent", str(other))])
    names = harness.names()
    assert names.index("runner-stop") < names.index("context-set")


@pytest.mark.parametrize("target", ["absent", "not-forge"])
def test_invalid_switch_keeps_running_project(
    harness: Harness,
    server: web.ForgeDesignServer,
    project_root: Path,
    tmp_path: Path,
    target: str,
) -> None:
    candidate = tmp_path / target
    if target == "not-forge":
        candidate.mkdir()
    open_project(server, project_root)
    start(server)
    harness.events.clear()
    open_project(server, candidate)
    assert "runner-stop" not in harness.names()
    assert harness.runtime.status().state == "running"
    assert str(project_root) in http(server, "GET", "/")[1]


def test_reopen_same_project_keeps_preview(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    harness.events.clear()
    open_project(server, project_root)
    http(server, "POST", "/project/open-recent", [("recent", str(project_root))])
    assert harness.events == []


def test_switch_refused_if_stop_fails(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path, tmp_path: Path
) -> None:
    other = designed_project(tmp_path / "b").resolve()
    open_project(server, project_root)
    start(server)
    harness.controller.stop_ok = False
    status, html, _ = open_project(server, other)
    assert status == 409
    assert "n'a pas pu être arrêtée" in unescape(html)
    assert str(project_root) in http(server, "GET", "/")[1]


def test_refresh_valid_keeps_preview(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    harness.events.clear()
    assert http(server, "POST", "/project/refresh")[0] == 200
    assert harness.events == []


def test_refresh_invalid_stops_before_clear(
    harness: Harness,
    context_events: list[Event],
    server: web.ForgeDesignServer,
    project_root: Path,
) -> None:
    open_project(server, project_root)
    start(server)
    context_events.clear()
    (project_root / "config.py").unlink()
    http(server, "POST", "/project/refresh")
    names = harness.names()
    assert names.index("runner-stop") < names.index("context-clear")


def test_recent_remove_keeps_preview(
    harness: Harness, server: web.ForgeDesignServer, project_root: Path
) -> None:
    open_project(server, project_root)
    start(server)
    harness.events.clear()
    http(server, "POST", "/project/recent/remove", [("recent", str(project_root))])
    assert harness.events == []


# ── Fermeture du serveur ─────────────────────────────────────────────────────


def test_server_close_stops_runtime(harness: Harness, project_root: Path) -> None:
    with serving(harness.runtime) as server:
        open_project(server, project_root)
        start(server)
        harness.events.clear()
    assert harness.names() == ["proxy-shutdown", "proxy-close", "runner-stop"]
    assert not harness.runtime.enabled


@pytest.mark.parametrize("failure", [KeyboardInterrupt, RuntimeError, None])
def test_run_server_finally_closes_runtime(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: type[BaseException] | None,
) -> None:
    server = web.create_server(port=0, real_preview=harness.runtime)
    harness.runtime.start(tmp_path)
    order: list[str] = []

    def create(host: str, port: int) -> web.ForgeDesignServer:
        return server

    def serve(poll_interval: float = 0.5) -> None:
        if failure is not None:
            raise failure

    original_close = harness.runtime.close
    original_server_close = server.server_close

    def close() -> None:
        order.append("runtime-close")
        original_close()

    def server_close() -> None:
        order.append("server-close")
        original_server_close()

    monkeypatch.setattr(web, "create_server", create)
    monkeypatch.setattr(server, "serve_forever", serve)
    monkeypatch.setattr(harness.runtime, "close", close)
    monkeypatch.setattr(server, "server_close", server_close)
    if failure is RuntimeError:
        with pytest.raises(RuntimeError):
            web.run_server(port=0)
    else:
        web.run_server(port=0)
    # Fermé par le finally de run_server, avant même la fermeture de l'écoute.
    assert order[:2] == ["runtime-close", "server-close"]
    assert "runner-stop" in harness.names()[1:]
    assert server.socket.fileno() == -1


# ── Intégration réelle : runner et proxy, projets synthétiques rc9 ──────────


def real_project(path: Path) -> Path:
    root = make_forge_project(path)
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9\n")
    (root / "static" / "preview.css").write_text(".preview{color:blue}")
    views = root / "mvc/views/home"
    (views / "index.view.json").write_text(
        json.dumps(
            {
                "name": "home/index",
                "template": "mvc/views/home/index.html",
                "context": {},
            }
        )
    )
    (views / "index.design.json").write_text(
        json.dumps(
            {
                "version": "0.1",
                "view": "home/index",
                "source_contract": "home/index.view.json",
                "root": {"type": "page", "children": []},
            }
        )
    )
    return root.resolve()


REAL_DESIGN = "home/index.design.json"


def runner_ports(marker: str) -> list[str]:
    ports: list[str] = []
    for pid in processes_mentioning(marker):
        try:
            arguments = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"--port" in arguments:
            ports.append(arguments[arguments.index(b"--port") + 1].decode())
    return ports


def proxy_get(url: str, method: str = "GET") -> tuple[int, str, bytes]:
    parts = urlsplit(url)
    assert parts.hostname == "127.0.0.1" and parts.port is not None
    connection = HTTPConnection("127.0.0.1", parts.port, timeout=15)
    try:
        connection.request(method, parts.path or "/", headers={"Host": parts.netloc})
        response = connection.getresponse()
        return (
            response.status,
            response.getheader("Content-Type") or "",
            response.read(),
        )
    finally:
        connection.close()


def proxy_threads() -> list[threading.Thread]:
    return [
        t for t in threading.enumerate() if t.name == "forge-design-real-preview-proxy"
    ]


@pytest.fixture
def no_survivors(tmp_path: Path) -> Iterator[None]:
    yield
    assert wait_until_dead(processes_mentioning(str(tmp_path))) == []
    deadline_threads = proxy_threads()
    for thread in deadline_threads:
        thread.join(2)
    assert proxy_threads() == []


def real_editor(server: web.ForgeDesignServer) -> Reply:
    return http(server, "GET", "/editor?" + urlencode({"design": REAL_DESIGN}))


def real_start(server: web.ForgeDesignServer) -> Reply:
    return http(server, "POST", "/editor/real-preview/start", [("design", REAL_DESIGN)])


def test_real_end_to_end(tmp_path: Path, no_survivors: None) -> None:
    root = real_project(tmp_path / "a")
    with serving() as server:
        assert open_project(server, root)[0] == 200
        assert "Route : <code>/</code>" in real_editor(server)[1]
        assert real_start(server)[0] == 303
        _, html, headers = real_editor(server)
        frame = iframe(html)
        assert frame is not None
        src = unescape(re.search(r'src="([^"]+)"', frame).group(1))  # type: ignore[union-attr]
        origin = src.removesuffix("/")
        assert re.fullmatch(r"http://127\.0\.0\.1:[0-9]+", origin)
        assert headers["Content-Security-Policy"].endswith(
            f"; frame-src 'self' {origin}"
        )
        # Le port du runner n'apparaît jamais dans l'éditeur.
        (runner_port,) = runner_ports(str(root))
        assert (
            f":{runner_port}" not in html
            and origin != f"http://127.0.0.1:{runner_port}"
        )
        code, content_type, body = proxy_get(src)
        assert (
            code == 200
            and content_type.startswith("text/html")
            and b"<html" in body.lower()
        )
        assert proxy_get(origin + "/static/preview.css")[0::2] == (
            200,
            b".preview{color:blue}",
        )
        assert proxy_get(src, "POST")[0] == 405
        assert (
            http(
                server, "POST", "/editor/real-preview/stop", [("design", REAL_DESIGN)]
            )[0]
            == 303
        )
        with pytest.raises(OSError):
            proxy_get(src)
        assert processes_mentioning(str(root)) == []
        assert iframe(real_editor(server)[1]) is None


def test_real_switch_project_stops_previous(tmp_path: Path, no_survivors: None) -> None:
    first, second = real_project(tmp_path / "a"), real_project(tmp_path / "b")
    with serving() as server:
        open_project(server, first)
        real_start(server)
        assert runner_ports(str(first))
        assert open_project(server, second)[0] == 200
        assert wait_until_dead(processes_mentioning(str(first))) == []
        assert proxy_threads() == []
        assert str(second) in http(server, "GET", "/")[1]


def test_real_close_project(tmp_path: Path, no_survivors: None) -> None:
    root = real_project(tmp_path / "a")
    with serving() as server:
        open_project(server, root)
        real_start(server)
        assert http(server, "POST", "/project/close")[0] == 200
        assert wait_until_dead(processes_mentioning(str(root))) == []
        assert proxy_threads() == []


def test_real_server_shutdown_while_running(tmp_path: Path, no_survivors: None) -> None:
    root = real_project(tmp_path / "a")
    with serving() as server:
        open_project(server, root)
        real_start(server)
        _, html, _ = real_editor(server)
        frame = iframe(html)
        assert frame is not None and runner_ports(str(root))
        src = unescape(re.search(r'src="([^"]+)"', frame).group(1))  # type: ignore[union-attr]
    # Sortie du bloc : serveur fermé, runtime fermé (proxy puis runner).
    with pytest.raises(OSError):
        proxy_get(src)


def _returning(
    server: web.ForgeDesignServer,
) -> Callable[[str, int], web.ForgeDesignServer]:
    def create(host: str, port: int) -> web.ForgeDesignServer:
        return server

    return create


# ── Arrêt par signal (FD-REALPREVIEW-005) ────────────────────────────────────
# Défaut observé en session navigateur : SIGTERM ou SIGHUP tuaient Forge Design
# sans finally ; la preview, dans sa propre session, survivait orpheline.


@pytest.mark.parametrize("name", ["SIGTERM", "SIGHUP"])
def test_run_server_stops_on_signal(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    number = getattr(signal, name)
    server = web.create_server(port=0, real_preview=harness.runtime)
    harness.runtime.start(tmp_path)
    outside: list[int] = []
    interrupted: list[bool] = []

    def outer_handler(signum: int, frame: object) -> None:
        outside.append(signum)

    def serve(poll_interval: float = 0.5) -> None:
        os.kill(os.getpid(), number)
        time.sleep(1)
        interrupted.append(False)  # atteint seulement si le signal n'a rien arrêté

    previous = signal.signal(number, outer_handler)
    try:
        monkeypatch.setattr(web, "create_server", _returning(server))
        monkeypatch.setattr(server, "serve_forever", serve)
        web.run_server(port=0)
        assert outside == [] and interrupted == []
        assert signal.getsignal(number) is outer_handler
    finally:
        signal.signal(number, previous)
    assert harness.names()[-1] == "runner-stop"
    assert "proxy-close" in harness.names()
    assert server.socket.fileno() == -1


def test_run_server_outside_main_thread_installs_no_handler(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = web.create_server(port=0, real_preview=harness.runtime)
    monkeypatch.setattr(web, "create_server", _returning(server))
    monkeypatch.setattr(server, "serve_forever", lambda poll_interval=0.5: None)
    before = signal.getsignal(signal.SIGTERM)
    errors: list[BaseException] = []

    def target() -> None:
        try:
            web.run_server(port=0)
        except BaseException as error:  # noqa: BLE001 - restituer au test
            errors.append(error)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(10)
    assert errors == [] and signal.getsignal(signal.SIGTERM) is before


SERVE = (
    "import sys\n"
    "from forge_design.web.server import run_server\n"
    "run_server(port=int(sys.argv[1]), on_ready=lambda: print('PRET', flush=True))\n"
)


@pytest.mark.parametrize("name", ["SIGINT", "SIGTERM", "SIGHUP"])
def test_real_signal_stops_preview(
    tmp_path: Path, no_survivors: None, name: str
) -> None:
    root = real_project(tmp_path / "a")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg"),
    }
    process = subprocess.Popen(
        [sys.executable, "-c", SERVE, str(port)],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "PRET"

        class Target:
            server_port = port

        target: Any = Target()
        assert open_project(target, root)[0] == 200
        assert real_start(target)[0] == 303
        html = real_editor(target)[1]
        proxy = int(html.split('src="http://127.0.0.1:')[1].split("/")[0])
        assert processes_mentioning(str(root))
        process.send_signal(getattr(signal, name))
        process.wait(20)
        output = process.stdout.read()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    assert "Traceback" not in output
    assert wait_until_dead(processes_mentioning(str(root))) == []
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", proxy), timeout=1).close()
