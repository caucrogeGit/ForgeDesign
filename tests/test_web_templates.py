"""Pages réellement servies : URL, source littérale, stateless et erreurs locales."""

import os
import shutil
from pathlib import Path
from urllib.parse import urlencode

import pytest
from test_templates import make_views
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.forge.templates import TemplatesResult
from forge_design.limits import MAX_SOURCE_BYTES
from forge_design.recent_projects import RecentProjects
from forge_design.tools.template_viewer import TemplateViewerTool
from forge_design.web.template_viewer import modified_date, template_url


def test_list_detail_reload_and_no_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    history = tmp_path / "config/recent.json"
    calls: list[Path] = []
    original = TemplateViewerTool.run

    def run(self: TemplateViewerTool, root: Path) -> TemplatesResult:
        calls.append(root)
        return original(self, root)

    monkeypatch.setattr(TemplateViewerTool, "run", run)
    with running(RecentProjects(history)) as app:
        status, html, headers = call(app, "/templates")
        assert status == 200 and "Aucun projet ouvert." in html and not calls
        assert headers["Cache-Control"] == "no-store"
        assert call(app, "/templates/view?path=page")[0] == 409
        call(app, "/inspector", method="POST", value=str(root))
        html = call(app, "/templates")[1]
        assert "Source mvc/views/ absente" in html and calls == [root]
        views = root / "mvc/views"
        views.mkdir()
        assert "Aucun template disponible." in call(app, "/templates")[1]
        name = 'é space &+?#"<tag>.jinja'
        file = views / name
        content = (
            '{{ cycler.__init__.__globals__ }}{% include "absent" %}'
            "{{ raise_exception() }}{% if\n<script>alert(1)</script>"
            "<img src=x onerror=alert(1)> été 😀"
        )
        file.write_text(content)
        os.utime(file, ns=(1_700_000_000_123_456_789, 1_700_000_000_123_456_789))
        (views / "empty").touch()
        (root / "mvc/controllers").mkdir()
        (root / "mvc/controllers/hostile.py").write_text("raise AssertionError()")
        before = {
            p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
            for p in root.rglob("*")
            if p.is_file()
        }
        history_before = (history.read_bytes(), history.stat().st_mtime_ns)
        previous = len(calls)
        status, html, headers = call(app, "/templates")
        assert status == 200 and len(calls) == previous + 1
        document = SvgDocument()
        document.feed(html)
        rows = [a for tag, a in document.tags if tag == "tr" and "data-size" in a]
        assert [a["data-template-path"] for a in rows] == sorted([name, "empty"])
        row = next(a for a in rows if a["data-template-path"] == name)
        assert row["data-size"] == str(len(content.encode()))
        assert row["data-modified-ns"] == str(file.stat().st_mtime_ns)
        assert modified_date(file.stat().st_mtime_ns) in html
        url = template_url(name)
        assert url in [a.get("href") for tag, a in document.tags if tag == "a"]
        for page in ("/templates", url):
            status, html, headers = call(app, page)
            assert status == 200 and headers["Cache-Control"] == "no-store"
            doc = SvgDocument()
            doc.feed(html)
            assert any(
                a.get("href") == "/templates" and a.get("aria-current") == "page"
                for _, a in doc.tags
            )
            assert not any(tag in {"script", "img"} for tag, _ in doc.tags)
            assert call(app, page.split("?")[0], method="POST")[0] == 405
            if page == url:
                assert content in doc.text
                assert '<pre class="source-code"><code>' in html
                assert str(row["data-modified-ns"]) in html
        assert before == {
            p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
            for p in root.rglob("*")
            if p.is_file()
        }
        assert history_before == (history.read_bytes(), history.stat().st_mtime_ns)
        file.write_text("new raw {% extends 'nothing' %}")
        os.utime(file, ns=(1_800_000_000_000_000_001, 1_800_000_000_000_000_001))
        status, html, _ = call(app, url)
        assert status == 200 and f'data-size="{file.stat().st_size}"' in html
        assert f'data-modified-ns="{file.stat().st_mtime_ns}"' in html
        (views / "new.xml").touch()
        assert "new.xml" in call(app, "/templates")[1]
        file.unlink()
        assert call(app, url)[0] == 404
        for page in ("/routes", "/entities", "/debug"):
            assert call(app, page)[0] == 200


@pytest.mark.parametrize(
    "query",
    [
        "",
        "path=",
        "path=a&path=b",
        "path=a&other=b",
        "path=..",
        "path=%2e%2e%2fsecret",
        "path=%2Fabsolute",
        "path=a%5Cb",
        "path=a%3Ab",
        "path=a%00b",
        "path=.hidden",
        "path=secret.KEY",
        "path=" + "a" * 4096,
    ],
)
def test_invalid_query_before_access(tmp_path: Path, query: str) -> None:
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        status, _, headers = call(app, "/templates/view?" + query)
        assert status == 400 and headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("kind", ["missing", "linked", "large", "binary", "folder"])
def test_source_errors(tmp_path: Path, kind: str) -> None:
    root, views = make_views(tmp_path)
    file = views / "page"
    if kind == "linked":
        target = tmp_path / "target"
        target.write_text("secret outside")
        file.symlink_to(target)
    elif kind == "large":
        file.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    elif kind == "binary":
        file.write_bytes(b"\xff")
    elif kind == "folder":
        file.mkdir()
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        status, html, headers = call(app, "/templates/view?path=page")
        assert status == (404 if kind == "missing" else 409)
        assert headers["Cache-Control"] == "no-store" and 'role="alert"' in html
        assert "secret outside" not in html


@pytest.mark.parametrize("kind", ["missing", "file", "non_forge", "loop"])
def test_project_becomes_invalid(tmp_path: Path, kind: str) -> None:
    root, views = make_views(tmp_path)
    (views / "page").touch()
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        if kind == "non_forge":
            (root / "app.py").unlink()
        else:
            shutil.rmtree(root)
            if kind == "file":
                root.touch()
            elif kind == "loop":
                root.symlink_to(root)
        for page in ("/templates", "/templates/view?" + urlencode({"path": "page"})):
            status, _, headers = call(app, page)
            assert status == 409 and headers["Cache-Control"] == "no-store"


def test_date_out_of_range() -> None:
    assert modified_date(10**40) == "Date hors plage"
