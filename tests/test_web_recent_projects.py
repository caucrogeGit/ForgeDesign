"""Historique persistant, contexte runtime séparé et actions HTTP locales."""

import json
import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from html.parser import HTMLParser
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode
from wsgiref.simple_server import WSGIServer

import pytest

from forge_design.recent_projects import RecentProjects
from forge_design.web.server import create_server


def project(root: Path) -> Path:
    root.mkdir()
    for name in ("app.py", "config.py", "bootstrap.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "mvc/routes").mkdir(parents=True)
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    return root


@contextmanager
def running(store: RecentProjects) -> Generator[WSGIServer, None, None]:
    with create_server(port=0, recent_projects=store) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)
            assert not thread.is_alive()


def call(
    server: WSGIServer,
    url: str = "/",
    *,
    method: str = "GET",
    value: str | None = None,
    origin: str = "local",
    site: str = "same-origin",
    content_type: str = "application/x-www-form-urlencoded",
) -> tuple[int, str, dict[str, str]]:
    field = "path" if url == "/inspector" else "recent"
    headers = {
        "Origin": f"http://127.0.0.1:{server.server_port}"
        if origin == "local"
        else origin,
        "Sec-Fetch-Site": site,
        "Content-Type": content_type,
    }
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        conn.request(method, url, urlencode({field: value}) if value else "", headers)
        response = conn.getresponse()
        return response.status, response.read().decode(), dict(response.getheaders())
    finally:
        conn.close()


def test_restart_canonical_order_remove_and_isolation(tmp_path: Path) -> None:
    first, second = project(tmp_path / "first"), project(tmp_path / "second")
    file = tmp_path / "user/recent.json"
    store = RecentProjects(file)
    with running(store) as app:
        assert "Aucun projet récent." in call(app)[1]
        assert (
            call(app, "/inspector", method="POST", value=str(first / "mvc/.."))[0]
            == 200
        )
        assert store.list()[0].path == str(first)
        assert call(app, "/inspector", method="POST", value=str(second))[0] == 200
        html = call(app)[1]
        assert "— Ouvert" in html
        assert html.index(str(second), html.index("Projets récents")) < html.index(
            str(first), html.index("Projets récents")
        )
    with (
        running(RecentProjects(file)) as restarted,
        running(RecentProjects(tmp_path / "other/recent.json")) as isolated,
    ):
        status, html, headers = call(restarted)
        assert status == 200 and "Aucun projet ouvert." in html
        assert str(first) in html and headers["Cache-Control"] == "no-store"
        assert "Aucun projet récent." in call(isolated)[1]
        status, html, _ = call(
            restarted, "/project/open-recent", method="POST", value=str(first)
        )
        assert status == 200 and "Projet Forge reconnu" in html
        assert store.list()[0].path == str(first)
        status, html, _ = call(
            restarted, "/project/recent/remove", method="POST", value=str(first)
        )
        assert status == 200 and "Aucun projet ouvert." not in html
        assert all(p.path != str(first) for p in store.list())
        assert first.exists() and str(first) in html  # Le bandeau reste ouvert.
        assert "Aucun projet ouvert." in call(isolated)[1]


@pytest.mark.parametrize("failure", ["missing", "invalid"])
def test_reopen_failure_keeps_current_and_history(tmp_path: Path, failure: str) -> None:
    old, current = project(tmp_path / "old"), project(tmp_path / "current")
    store = RecentProjects(tmp_path / "config/recent.json")
    with running(store) as app:
        call(app, "/inspector", method="POST", value=str(old))
        call(app, "/inspector", method="POST", value=str(current))
        if failure == "missing":
            shutil.rmtree(old)
        else:
            (old / "app.py").unlink()
        before = store.path.read_bytes()
        status, html, _ = call(
            app, "/project/open-recent", method="POST", value=str(old)
        )
        assert status == (400 if failure == "missing" else 200)
        assert "Traceback" not in html
        assert str(current) in html and "Aucun projet ouvert." not in html
        if failure == "invalid":
            assert "Projet Forge non reconnu" in html
        assert store.path.read_bytes() == before
        assert str(old) in call(app)[1]


@pytest.mark.parametrize("action", ["/project/open-recent", "/project/recent/remove"])
@pytest.mark.parametrize(
    "origin,site",
    [
        ("https://evil.example", "same-origin"),
        ("local", "cross-site"),
    ],
)
def test_origin_rejected_without_mutation(
    tmp_path: Path,
    action: str,
    origin: str,
    site: str,
) -> None:
    root = project(tmp_path / "project")
    store = RecentProjects(tmp_path / "config/recent.json")
    store.add(root)
    before = store.path.read_bytes(), store.path.stat().st_mtime_ns
    with running(store) as app:
        assert (
            call(app, action, method="POST", value=str(root), origin=origin, site=site)[
                0
            ]
            == 403
        )
        assert "Aucun projet ouvert." in call(app)[1]
    assert before == (store.path.read_bytes(), store.path.stat().st_mtime_ns)


@pytest.mark.parametrize("action", ["/project/open-recent", "/project/recent/remove"])
def test_fabricated_entry_get_and_format_rejected(tmp_path: Path, action: str) -> None:
    store = RecentProjects(tmp_path / "config/recent.json")
    root = project(tmp_path / "unregistered")
    with running(store) as app:
        assert call(app, action, method="POST", value=str(root))[0] == 400
        assert (
            call(
                app, action, method="POST", value=str(root), content_type="text/plain"
            )[0]
            == 415
        )
        assert call(app, action)[0] == 405
        assert "Aucun projet ouvert." in call(app)[1]
    assert not store.path.exists()


def test_write_failure_does_not_undo_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "valid")
    store = RecentProjects(tmp_path / "config/recent.json")

    def failure(*args: object, **kwargs: object) -> None:
        raise PermissionError("simulated")

    monkeypatch.setattr(os, "replace", failure)
    with running(store) as app:
        status, html, _ = call(app, "/inspector", method="POST", value=str(root))
        assert status == 200 and "Projet Forge reconnu" in html
        assert "avertissement" in html and "Enregistrement" in html
        assert "Aucun projet ouvert." not in call(app)[1]
    assert not store.path.exists() and not list(store.path.parent.glob("*.tmp"))


def test_bad_history_preserved_and_paths_escaped(tmp_path: Path) -> None:
    root = project(tmp_path / 'é-<script>"')
    store = RecentProjects(tmp_path / "config/recent.json")
    store.add(root)
    with running(store) as app:
        before = store.path.read_bytes(), store.path.stat().st_mtime_ns
        status, html, headers = call(app)
        assert status == 200 and headers["Cache-Control"] == "no-store"

        class Inputs(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.values: list[str | None] = []

            def handle_starttag(
                self, tag: str, attrs: list[tuple[str, str | None]]
            ) -> None:
                assert tag != "script"
                if tag == "input":
                    self.values.append(dict(attrs).get("value"))

        inputs = Inputs()
        inputs.feed(html)
        assert inputs.values == [str(root), str(root)]
        assert "&lt;script&gt;" in html and str(root) not in html
        assert before == (store.path.read_bytes(), store.path.stat().st_mtime_ns)
        store.path.write_text('{"version":99,"projects":[]}')
        assert "Version des projets récents" in call(app)[1]
        status, html, _ = call(app, "/inspector", method="POST", value=str(root))
        assert status == 200 and "Projet Forge reconnu" in html
        assert "avertissement" in html
        assert json.loads(store.path.read_text())["version"] == 99


def test_invalid_inspection_does_not_add_recent(tmp_path: Path) -> None:
    root = tmp_path / "invalid"
    root.mkdir()
    store = RecentProjects(tmp_path / "config/recent.json")
    with running(store) as app:
        status, html, _ = call(app, "/inspector", method="POST", value=str(root))
        assert status == 200 and "Projet Forge non reconnu" in html
        assert "Aucun projet ouvert." in call(app)[1]
        assert store.list() == () and not store.path.exists()
