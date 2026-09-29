"""Arbre HTTP, lectures uniques, HTML sémantique et contrats du détail commun."""

import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_templates import make_views
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, running

from forge_design.forge.template_structure import (
    HtmlElement,
    TemplateBlock,
    TemplateReference,
    TemplateStructure,
    TemplateSyntaxInfo,
)
from forge_design.forge.templates import TemplateSource
from forge_design.limits import MAX_SOURCE_BYTES
from forge_design.recent_projects import RecentProjects
from forge_design.tools.template_viewer import TemplateViewerTool
from forge_design.web import template_viewer


class TreeDocument(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.depths: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "ul":
            assert not self.stack or self.stack[-1] == "li"
            self.stack.append(tag)
        elif tag == "li":
            assert self.stack and self.stack[-1] == "ul"
            self.stack.append(tag)
            if "data-html-depth" in values:
                depth = int(values["data-html-depth"] or "0")
                assert self.stack.count("ul") == depth + 1
                self.depths.append(depth)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"ul", "li"}:
            assert self.stack.pop() == tag


@pytest.mark.parametrize(
    "source",
    [
        "",
        '{% extends "base" %}{% from "ui" import card %}{% include selected %}'
        "{% block title %}{% endblock %}{% block title %}{% endblock %}"
        "<html><head><meta></head><body><section></section></body></html><footer>",
        "<section>{% if",
        "<div>" * 4097,
    ],
)
def test_tree_single_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    root, views = make_views(tmp_path)
    name = 'é &+"page.html'
    file = views / name
    file.write_text(source)
    original_read = template_viewer.read_template_source
    original_analyze = template_viewer.analyze_template_structure
    calls: list[str] = []

    def read(root: Path, path: str) -> TemplateSource:
        calls.append("read")
        return original_read(root, path)

    def analyze(text: str) -> TemplateStructure:
        calls.append("analyze")
        return original_analyze(text)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No inventory on detail")

    monkeypatch.setattr(template_viewer, "read_template_source", read)
    monkeypatch.setattr(template_viewer, "analyze_template_structure", analyze)
    monkeypatch.setattr(TemplateViewerTool, "run", forbidden)
    history = tmp_path / "xdg/recent.json"
    with running(RecentProjects(history)) as app:
        call(app, "/inspector", method="POST", value=str(root))
        url = template_viewer.template_tree_url(name)
        raw_url = template_viewer.template_url(name)
        before = (
            file.read_bytes(),
            file.stat().st_mtime_ns,
            history.read_bytes(),
            history.stat().st_mtime_ns,
        )
        code, html, headers = call(app, url)
        assert code == 200 and headers["Cache-Control"] == "no-store"
        assert calls == ["read", "analyze"]
        doc = SvgDocument()
        doc.feed(html)
        tree_doc = TreeDocument()
        tree_doc.feed(html)
        assert not tree_doc.stack
        assert not any(tag in {"script", "svg", "img"} for tag, _ in doc.tags)
        assert raw_url in [a.get("href") for tag, a in doc.tags if tag == "a"]
        assert any(
            a.get("href") == "/templates" and a.get("aria-current") == "page"
            for _, a in doc.tags
        )
        assert [
            a.get("href")
            for tag, a in doc.tags
            if tag == "a" and (a.get("href") or "").startswith("/templates/view?")
        ] == [raw_url]
        assert f'data-size="{file.stat().st_size}"' in html
        if not source:
            for message in (
                "Aucune dépendance Jinja détectée.",
                "Aucun block Jinja détecté.",
                "Aucune structure HTML détectée.",
            ):
                assert message in html
        if "selected" in source:
            assert "Référence dynamique" in html and "from-import" in html
            assert html.count("title — ligne 1") == 2
        if "{% if" in source:
            assert "Syntaxe Jinja invalide" in html
            assert "Arbre construit à partir d’une analyse partielle." in html
        if len(source) > 10000:
            assert len(tree_doc.depths) == 4096 and tree_doc.depths[-1] == 4095
            assert "Structure tronquée par les limites d’analyse." in html
        code, raw, _ = call(app, raw_url)
        raw_doc = SvgDocument()
        raw_doc.feed(raw)
        assert code == 200 and "Structure détectée" in raw
        assert source in "".join(raw_doc.text)
        assert url in [a.get("href") for tag, a in raw_doc.tags if tag == "a"]
        assert before == (
            file.read_bytes(),
            file.stat().st_mtime_ns,
            history.read_bytes(),
            history.stat().st_mtime_ns,
        )
        assert call(app, "/templates/tree", method="POST")[0] == 405
        file.write_text('{% include "new" %}{% block changed %}<article>{% endblock %}')
        assert "changed — ligne 1" in call(app, url)[1]
        file.unlink()
        assert call(app, url)[0] == 404


@pytest.mark.parametrize(
    "query",
    [
        "",
        "path=",
        "path=a&path=b",
        "path=a&other=x",
        "path=..",
        "path=%2e%2e%2Fapp.py",
        "path=%2Fabsolute",
        "path=a%5Cb",
        "path=a%3Ab",
        "path=a%00b",
        "path=.env",
        "path=secret.key",
        "path=" + "x" * 4096,
    ],
)
def test_invalid_path(tmp_path: Path, query: str) -> None:
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        status, _, headers = call(app, "/templates/tree?" + query)
        assert status == 400 and headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("kind", ["missing", "linked", "large", "binary", "folder"])
def test_unreadable_source(tmp_path: Path, kind: str) -> None:
    root, views = make_views(tmp_path)
    file = views / "page"
    if kind == "linked":
        file.symlink_to(root / "app.py")
    elif kind == "large":
        file.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    elif kind == "binary":
        file.write_bytes(b"\xff")
    elif kind == "folder":
        file.mkdir()
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        assert call(app, "/templates/tree?path=page")[0] == 409
        call(app, "/inspector", method="POST", value=str(root))
        status, _, headers = call(app, "/templates/tree?path=page")
        assert status == (404 if kind == "missing" else 409)
        assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("kind", ["missing", "file", "non_forge", "loop"])
def test_invalid_project(tmp_path: Path, kind: str) -> None:
    root, _ = make_views(tmp_path)
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
        status, _, headers = call(app, "/templates/tree?path=page")
        assert status == 409 and headers["Cache-Control"] == "no-store"


def test_synthetic_xss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hostile = '<img src=x onerror="alert(1)">'

    def analyze(source: str) -> TemplateStructure:
        return TemplateStructure(
            TemplateSyntaxInfo("valid"),
            (TemplateReference("include", hostile, False, 1),),
            (TemplateBlock(hostile, 2),),
            (HtmlElement(hostile, 3, 0),),
        )

    monkeypatch.setattr(template_viewer, "analyze_template_structure", analyze)
    root, views = make_views(tmp_path)
    (views / "page").touch()
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        status, html, _ = call(app, "/templates/tree?path=page")
        doc = SvgDocument()
        doc.feed(html)
        assert status == 200 and "".join(doc.text).count(hostile) == 3
        assert not any(tag == "img" for tag, _ in doc.tags)
