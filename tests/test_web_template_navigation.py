"""Liens locaux communs aux deux vues, états texte et absence de transitivité."""

from pathlib import Path

import pytest
from test_templates import make_views
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, running

from forge_design.forge.template_structure import (
    TemplateReference,
    TemplateStructure,
    TemplateSyntaxInfo,
)
from forge_design.forge.templates import TemplateSource
from forge_design.recent_projects import RecentProjects
from forge_design.tools import template_navigation
from forge_design.web import template_viewer


@pytest.mark.parametrize("page", ["view", "tree"])
def test_states_links_refresh_and_read_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, page: str
) -> None:
    root, views = make_views(tmp_path)
    target_name = 'é 😀 &+%2e%2e "<img>.html'
    target = views / target_name
    target.write_text('{% include "never-inspected" %}{% if')
    (views / "linked").symlink_to(root / "app.py")
    text = (
        '{% include ["placeholder", "placeholder"] %}\n'
        '{% include "missing" %}{% include chosen %}'
        '{% include "../secret" %}{% include "linked" %}'
    ).replace('"placeholder"', repr(target_name))
    (views / "page").write_text(text)
    read = template_viewer.read_template_source
    analyze = template_viewer.analyze_template_structure
    inspect = template_navigation.inspect_project_source
    reads: list[str] = []
    analyzed: list[str] = []
    inspected: list[str] = []

    def read_once(root: Path, path: str) -> TemplateSource:
        reads.append(path)
        return read(root, path)

    def analyze_once(source: str) -> TemplateStructure:
        analyzed.append(source)
        return analyze(source)

    def inspect_once(root: Path, path: str):
        inspected.append(path)
        return inspect(root, path)

    monkeypatch.setattr(template_viewer, "read_template_source", read_once)
    monkeypatch.setattr(template_viewer, "analyze_template_structure", analyze_once)
    monkeypatch.setattr(template_navigation, "inspect_project_source", inspect_once)
    history = tmp_path / "xdg/recent.json"
    with running(RecentProjects(history)) as app:
        call(app, "/inspector", method="POST", value=str(root))
        before = {
            p: (p.read_bytes(), p.stat().st_mtime_ns)
            for p in (views / "page", target, history)
        }
        url = f"/templates/{page}?path=page"
        status, html, headers = call(app, url)
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert reads == ["page"] and analyzed == [text]
        assert inspected == [
            "mvc/views/" + target_name,
            "mvc/views/missing",
            "mvc/views/linked",
        ]
        doc = SvgDocument()
        doc.feed(html)
        states = [
            a["data-navigation-status"]
            for _, a in doc.tags
            if "data-navigation-status" in a
        ]
        assert states == [
            "available",
            "available",
            "missing",
            "dynamic",
            "invalid-path",
            "unreadable",
        ]
        links = [a for tag, a in doc.tags if tag == "a" and "aria-label" in a]
        assert len(links) == 2
        assert all(
            a["href"] == template_viewer.template_url(target_name) for a in links
        )
        assert all(a["aria-label"] == "Voir le template " + target_name for a in links)
        assert not any(tag in {"img", "script"} for tag, _ in doc.tags)
        for label in (
            "Local",
            "Non disponible dans mvc/views/",
            "Non résolue statiquement",
            "Chemin refusé",
            "Source locale inaccessible",
        ):
            assert label in html
        assert "never-inspected" not in html
        assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}
        status, content, _ = call(app, template_viewer.template_url(target_name))
        assert status == 200 and "Syntaxe Jinja invalide" in content
        (views / "missing").touch()
        assert 'aria-label="Voir le template missing"' in call(app, url)[1]
        target.unlink()
        assert template_viewer.template_url(target_name) not in call(app, url)[1]
        assert call(app, template_viewer.template_url(target_name))[0] == 404
        target.symlink_to(root / "app.py")
        doc = SvgDocument()
        doc.feed(call(app, url)[1])
        assert [
            a["data-navigation-status"]
            for _, a in doc.tags
            if "data-navigation-status" in a
        ][:2] == ["unreadable"] * 2
        assert call(app, template_viewer.template_url(target_name))[0] == 409


@pytest.mark.parametrize("page", ["view", "tree"])
def test_synthetic_invalid_xss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, page: str
) -> None:
    hostile = '../"><script>alert(1)</script>'

    def analyze(source: str) -> TemplateStructure:
        return TemplateStructure(
            TemplateSyntaxInfo("valid"),
            (
                TemplateReference("include", hostile, False, 1),
                TemplateReference("include", hostile, True, 2),
            ),
        )

    monkeypatch.setattr(template_viewer, "analyze_template_structure", analyze)
    root, views = make_views(tmp_path)
    (views / "page").touch()
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        status, html, _ = call(app, f"/templates/{page}?path=page")
        doc = SvgDocument()
        doc.feed(html)
        assert status == 200 and hostile in "".join(doc.text)
        assert not any(tag in {"script", "img"} for tag, _ in doc.tags)
        assert not any("aria-label" in a for tag, a in doc.tags if tag == "a")
