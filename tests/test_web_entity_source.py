"""Liens Entity Explorer et retours déduits de la politique source validée."""

from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from test_entities import contract, entity
from test_entity_graph import entity as info
from test_entity_graph import relation
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.forge.entities import EntitiesResult, EntityIssue
from forge_design.forge.source import SourceLocation
from forge_design.recent_projects import RecentProjects
from forge_design.tools.entity_explorer import EntityExplorerTool


@pytest.mark.parametrize(
    "path,content,expected",
    [
        ("mvc/entities/contact/contact.json", '{\n"name": "Contact"\n}', 200),
        ("mvc/entities/relations.json", '{"relations": []}', 200),
        ("mvc/entities/broken/broken.json", "{\n<script>text</script>", 200),
        ("mvc/entities/missing/missing.json", None, 404),
        ("mvc/entities/contact/user.json", "secret", 400),
        ("mvc/entities/contact/../relations.json", None, 400),
        ("mvc/entities/contact//contact.json", None, 400),
        ("mvc\\entities\\contact\\contact.json", None, 400),
        ("mvc/entities/C:/C:.json", None, 400),
        ("mvc/entities/%2e%2e/config.py", None, 400),
        ("mvc/routes/a.py", "value = 1\n", 200),
        ("mvc/controllers/a.py", "value = 1\n", 200),
        ("mvc/views/a.html", "<p>test</p>", 200),
    ],
)
def test_source_http(
    tmp_path: Path, path: str, content: str | None, expected: int
) -> None:
    root = project(tmp_path / "project")
    if content is not None:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def snapshot() -> dict[str, tuple[bytes, int, int]]:
        return {
            str(p): (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns)
            for p in root.rglob("*")
            if p.is_file()
        }

    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        before = snapshot()
        status, html, headers = call(
            app,
            "/source?" + urlencode({"path": path, "return_to": "https://evil.example"}),
        )
        assert status == expected and headers["Cache-Control"] == "no-store"
        assert snapshot() == before
        assert "evil.example" not in html and "<script>text" not in html
        if expected == 400:
            assert 'aria-current="page"' not in html
            assert "Retour à" not in html and "secret" not in html
        else:
            kind = "entities" if path.startswith("mvc/entities/") else "routes"
            label = "Entity" if kind == "entities" else "Route"
            assert f"Retour à {label} Explorer" in html
            assert f'<a href="/{kind}" aria-current="page">' in html
            if content is not None:
                assert 'id="line-1"' in html
                dom = SvgDocument()
                dom.feed(html)
                for line in content.splitlines():
                    assert any(line in text for text in dom.text)
                assert (
                    "La ligne demandée n’est plus disponible."
                    in call(app, "/source?" + urlencode({"path": path, "line": 999}))[1]
                )
        assert call(app, "/source", method="POST")[0] == 405


def test_links_and_broken_refresh(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    target = entity(root, "contact", contract())
    relations = root / "mvc/entities/relations.json"
    relations.write_text(
        '{"schema_version":"1.0","relations":[{"type":"many_to_one","from":"Contact","to":"Missing","name":"missing","foreign_key":"missing_id","on_delete":"restrict"}]}'
    )
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        for broken in (False, True):
            if broken:
                target.write_text("{")
            html = call(app, "/entities?q=contact")[1]
            assert "relations[0]" in html
            if broken:
                assert "entity.json_invalid" in html
            dom = SvgDocument()
            dom.feed(html)
            hrefs = [
                a["href"]
                for tag, a in dom.tags
                if tag == "a" and (a.get("href") or "").startswith("/source?")
            ]
            paths: list[str] = []
            for href in hrefs:
                assert href is not None
                params = parse_qs(urlsplit(href).query)
                assert set(params) == {"path"}
                paths.extend(params["path"])
                assert call(app, href)[0] == 200
            assert "mvc/entities/contact/contact.json" in paths
            assert "mvc/entities/relations.json" in paths


def test_synthetic_sources_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    hostile = '/tmp/"><script>source</script>'
    good = "mvc/entities/contact/contact.json"
    result = EntitiesResult(
        (
            replace(info("Contact"), source=SourceLocation(good, 42)),
            replace(info("Hostile"), source=SourceLocation(hostile)),
        ),
        errors=(
            EntityIssue("entity.json_invalid", "broken", SourceLocation(good, 9)),
            EntityIssue("entity.structure_invalid", "hostile", SourceLocation(hostile)),
            EntityIssue(
                "entity.source_missing", "directory", SourceLocation("mvc/entities")
            ),
            EntityIssue("entity.unreadable", "no source"),
        ),
        relations=(replace(relation("Contact", "Contact"), source_index=3),),
    )

    def run(self: EntityExplorerTool, project_root: Path) -> EntitiesResult:
        return result

    monkeypatch.setattr(EntityExplorerTool, "run", run)
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        html = call(app, "/entities")[1]
        dom = SvgDocument()
        dom.feed(html)
        hrefs = [a.get("href", "") or "" for tag, a in dom.tags if tag == "a"]
        assert sum(h.startswith("/source?") for h in hrefs) == 3
        assert all("line=" not in h and "/tmp" not in h for h in hrefs)
        assert hostile in "".join(dom.text) and "<script>source" not in html
        assert "relations[3]" in html and "no source" in html
