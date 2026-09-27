"""Contrat SVG réellement rendu, sans JavaScript ni nouvelle lecture."""

from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_entity_graph import entity, relation
from test_web_recent_projects import call, project, running

from forge_design.forge.entities import EntitiesResult, EntityIssue
from forge_design.recent_projects import RecentProjects
from forge_design.tools.entity_explorer import EntityExplorerTool


class SvgDocument(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.text.append(data)


@pytest.mark.parametrize("count", [0, 1, 2, 3, 30])
def test_http_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    root = project(tmp_path / "project")
    (root / "mvc/routes/__init__.py").write_text(
        "def register_routes(router):\n    pass\n"
    )
    names = [f'Entity{i}<script>"\\' for i in range(count)]
    relations = tuple(
        relation(names[i], names[(i + 1) % count], many=many)
        for i in range(count)
        for many in (False, True)
    )
    if count == 2:
        relations = ()  # Entités isolées également affichées.
    relations = tuple(replace(r, name="<script>relation</script>") for r in relations)
    edge_count = len(relations) // 2 * 3
    node_count = count + len(relations) // 2
    result = EntitiesResult(
        tuple(entity(name) for name in names),
        errors=(EntityIssue("relation.entity_missing", "Cible <script> absente"),),
        relations=relations,
    )
    calls: list[Path] = []

    def run(self: EntityExplorerTool, project_root: Path) -> EntitiesResult:
        calls.append(project_root)
        return result

    monkeypatch.setattr(EntityExplorerTool, "run", run)
    with running(RecentProjects(tmp_path / "config/recent.json")) as app:
        html = call(app, "/entities")[1]
        assert "<svg" not in html and calls == []
        call(app, "/inspector", method="POST", value=str(root))
        status, html, headers = call(app, "/entities")
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert calls == [root]
        assert "relation.entity_missing" in html and "&lt;script&gt;" in html
        document = SvgDocument()
        document.feed(html)
        assert not any(tag == "script" for tag, _ in document.tags)
        svgs = [attrs for tag, attrs in document.tags if tag == "svg"]
        if not count:
            assert svgs == []
        else:
            assert len(svgs) == 1 and svgs[0]["role"] == "img"
            assert (
                svgs[0]["aria-labelledby"]
                == "entity-graph-title entity-graph-description"
            )
            assert sum(tag == "marker" for tag, _ in document.tags) == 1
            assert (
                sum(attrs.get("class") == "entity-edge" for _, attrs in document.tags)
                == edge_count
            )
            nodes = [
                attrs
                for _, attrs in document.tags
                if str(attrs.get("id", "")).startswith("entity-node-")
            ]
            assert len(nodes) == node_count
            assert all(
                "tabindex" not in node and "onclick" not in node for node in nodes
            )
            assert [n["id"] for n in nodes] == [
                f"entity-node-{i}" for i in range(node_count)
            ]
            assert (
                sum(
                    tag == "path" and "marker-end" in attrs
                    for tag, attrs in document.tags
                )
                == edge_count
            )
            assert "<table>" in html and "<details>" in html
            assert any(names[0] in text for text in document.text)
            if relations:
                assert "Pivot" in html and "shared_pivot" in html
                assert "&lt;script&gt;relation&lt;/script&gt;" in html
                assert any("<script>relation</script>" in t for t in document.text)
            else:
                assert "Aucune relation interprétable." in html
        assert call(app, "/routes")[0] == 200
        # Nouveau GET : une seule exécution du Tool, pas de cache du graphe.
        call(app, "/entities")
        assert calls == [root, root]
