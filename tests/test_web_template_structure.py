"""Une lecture, projection en mémoire, sortie échappée et source conservée."""

from pathlib import Path

import pytest
from test_templates import make_views
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, running

from forge_design.app import create_tool_registry
from forge_design.forge.templates import TemplateSource
from forge_design.recent_projects import RecentProjects
from forge_design.web import template_viewer


@pytest.mark.parametrize(
    "source,status",
    [
        (
            '{% extends "base" %}{% from "ui" import card %}'
            "{% include selected %}{% block content %}<SECTION><h1>x</h1></SECTION>"
            "{% endblock %}",
            "Syntaxe Jinja analysable.",
        ),
        (
            '{% include "<img src=x onerror=alert(1)>" %}<div>',
            "Syntaxe Jinja analysable.",
        ),
        ("<div>\n{% if\n<fake>", "Syntaxe Jinja invalide à la ligne"),
        ("<div>{% unknown %}", "Syntaxe Jinja invalide à la ligne"),
        ("<div>" * 4097, "Syntaxe Jinja analysable."),
    ],
)
def test_http_structure_one_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str, status: str
) -> None:
    root, views = make_views(tmp_path)
    file = views / "page"
    file.write_text(source)
    original = template_viewer.read_template_source
    reads: list[tuple[Path, str]] = []

    def read(root: Path, path: str) -> TemplateSource:
        reads.append((root, path))
        return original(root, path)

    monkeypatch.setattr(template_viewer, "read_template_source", read)
    assert len(create_tool_registry().list()) == 5
    history = tmp_path / "xdg/recent.json"
    with running(RecentProjects(history)) as app:
        call(app, "/inspector", method="POST", value=str(root))
        before = (
            file.read_bytes(),
            file.stat().st_mtime_ns,
            history.read_bytes(),
            history.stat().st_mtime_ns,
        )
        code, html, headers = call(app, "/templates/view?path=page")
        assert code == 200 and status in html
        assert headers["Cache-Control"] == "no-store"
        assert reads == [(root, "page")]
        assert "Structure détectée" in html
        document = SvgDocument()
        document.feed(html)
        assert source in document.text
        assert not any(tag in {"script", "img"} for tag, _ in document.tags)
        assert not any(
            (a.get("href") or "").startswith("/templates/view?")
            for _, a in document.tags
            if a.get("href")
        )
        assert "Template valide" not in html
        if "selected" in source:
            assert "Référence dynamique" in html and "from-import" in html
            assert "content — ligne 1" in html and "section — ligne 1" in html
        if "{% if" in source or "unknown" in source:
            assert "Analyse partielle" in html and "template.syntax_invalid" in html
        if len(source) > 10000:
            assert "template.structure_truncated" in html
        assert before == (
            file.read_bytes(),
            file.stat().st_mtime_ns,
            history.read_bytes(),
            history.stat().st_mtime_ns,
        )
        file.write_text('{% include "new" %}{% block updated %}<article>{% endblock %}')
        code, html, _ = call(app, "/templates/view?path=page")
        assert (
            code == 200 and "updated — ligne 1" in html and "article — ligne 1" in html
        )
        assert len(reads) == 2
        file.unlink()
        assert call(app, "/templates/view?path=page")[0] == 404


def test_structure_values_escaped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Défense du template Web, même si un futur parser élargit les noms admis.
    from forge_design.forge.template_structure import (
        HtmlElement,
        TemplateBlock,
        TemplateReference,
        TemplateStructure,
        TemplateStructureIssue,
        TemplateSyntaxInfo,
    )

    hostile = '<img src=x onerror="alert(1)">'
    result = TemplateStructure(
        TemplateSyntaxInfo("invalid", 1, hostile),
        (TemplateReference("include", hostile, False, 1),),
        (TemplateBlock(hostile, 1),),
        (HtmlElement(hostile, 1, 0),),
        (TemplateStructureIssue("template.syntax_invalid", hostile),),
        partial=True,
    )

    def analyze(source: str) -> TemplateStructure:
        return result

    monkeypatch.setattr(template_viewer, "analyze_template_structure", analyze)
    root, views = make_views(tmp_path)
    (views / "page").write_text("text")
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        code, html, _ = call(app, "/templates/view?path=page")
        document = SvgDocument()
        document.feed(html)
        assert code == 200 and hostile in "".join(document.text)
        assert not any(tag == "img" for tag, _ in document.tags)
