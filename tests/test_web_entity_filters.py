"""Contrat HTTP des filtres, sans persistance ni deuxième appel Tool."""

import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlencode

import pytest
from test_entity_filters import inventory as inventory
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.forge.entities import EntitiesResult, EntityIssue
from forge_design.forge.source import SourceLocation
from forge_design.recent_projects import RecentProjects
from forge_design.tools.entity_explorer import EntityExplorerTool


@pytest.mark.parametrize(
    "query,entities,relations,nodes,edges,errors",
    [
        ("", 5, 3, 6, 4, 1),
        ("q=", 5, 3, 6, 4, 1),
        ("q=Article", 1, 2, 4, 3, 1),
        ("type=entity", 5, 0, 5, 0, 1),
        ("type=relation", 0, 3, 5, 4, 1),
        ("relation=many_to_one", 5, 2, 5, 2, 1),
        ("relation=many_to_many", 5, 1, 6, 2, 1),
        ("severity=error", 5, 3, 6, 4, 1),
        ("severity=warning", 5, 3, 6, 4, 0),
        ("severity=info", 5, 3, 6, 4, 0),
        ("diagnostics=only", 1, 1, 3, 2, 1),
        ("severity=error&diagnostics=only", 0, 1, 3, 2, 1),
        ("severity=info&diagnostics=only", 0, 0, 0, 0, 0),
        (
            "q=article&relation=many_to_many&severity=error&diagnostics=only",
            0,
            1,
            3,
            2,
            1,
        ),
        ("q=no_match", 0, 0, 0, 0, 1),
    ],
)
def test_http_filters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: EntitiesResult,
    query: str,
    entities: int,
    relations: int,
    nodes: int,
    edges: int,
    errors: int,
) -> None:
    root = project(tmp_path / "project")
    result = replace(
        inventory,
        errors=(EntityIssue("relation.entity_missing", "Absent", source_index=2),),
        warnings=(
            EntityIssue(
                "entity.unreadable", "Illisible", SourceLocation("Article.json")
            ),
        ),
    )
    calls: list[Path] = []

    def run(self: EntityExplorerTool, project_root: Path) -> EntitiesResult:
        calls.append(project_root)
        return result

    monkeypatch.setattr(EntityExplorerTool, "run", run)
    store = RecentProjects(tmp_path / "config/recent.json")
    with running(store) as app:
        call(app, "/inspector", method="POST", value=str(root))
        before = store.path.read_bytes(), store.path.stat().st_mtime_ns
        status, html, headers = call(app, "/entities?" + query)
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert calls == [root]
        assert before == (store.path.read_bytes(), store.path.stat().st_mtime_ns)
        assert f"{entities} entités affichées sur 5" in html
        assert f"{relations} relations affichées sur 3" in html
        assert f"{errors} erreur(s)" in html
        dom = SvgDocument()
        dom.feed(html)
        assert any(
            tag == "form"
            and a.get("method") == "get"
            and a.get("action") == "/entities"
            for tag, a in dom.tags
        )
        assert any(tag == "a" and a.get("href") == "/entities" for tag, a in dom.tags)
        assert "Réinitialiser" in html
        # Repli statique : un groupe par nœud ; même nombre dans la scène JSON.
        fallback = [
            a for _, a in dom.tags if str(a.get("id", "")).startswith("entity-node-")
        ]
        assert len(fallback) == nodes
        assert sum(tag == "path" and "marker-end" in a for tag, a in dom.tags) == edges
        assert [a.get("src") for tag, a in dom.tags if tag == "script"] == (
            [None, "/entity-graph.js"] if nodes else []
        )
        if nodes:
            payload = html.split("data-graphic-scene>", 1)[1].split("</script>", 1)[0]
            scene = json.loads(payload)
            assert (len(scene["nodes"]), len(scene["edges"])) == (nodes, edges)
        assert ("<th>Entité</th>" in html) == bool(entities)
        assert ("<th>Relation</th>" in html) == bool(relations)
        if not nodes:
            assert "<svg" not in html
            assert "Aucune entité ne correspond aux filtres." in html
            assert "Aucune relation ne correspond aux filtres." in html
        if "diagnostics=only" in query:
            assert any(
                a.get("name") == "diagnostics" and "checked" in a for _, a in dom.tags
            )
        for value in (
            "entity",
            "relation",
            "many_to_one",
            "many_to_many",
            "error",
            "warning",
            "info",
        ):
            if "=" + value in query:
                assert any(
                    tag == "option" and a.get("value") == value and "selected" in a
                    for tag, a in dom.tags
                )
        if "q=Article" in query or "q=article" in query:
            assert any(
                a.get("name") == "q" and a.get("value") == "article"
                for _, a in dom.tags
            )
        # Le GET suivant revient à la vue complète, aucune sélection persistante.
        assert "5 entités affichées sur 5" in call(app, "/entities")[1]
        assert calls == [root, root]
        assert call(app, "/entities", method="POST")[0] == 405
        assert call(app, "/routes")[0] == 200


@pytest.mark.parametrize(
    "query",
    [
        "type=invalid",
        "relation=one_to_one",
        "severity=critical",
        "diagnostics=yes",
        "q=" + "a" * 257,
        "unknown=x",
        *[
            f"{key}=all&{key}=all"
            for key in ("q", "type", "relation", "severity", "diagnostics")
        ],
    ],
)
def test_http_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Tool appelé pour filtre invalide")

    monkeypatch.setattr(EntityExplorerTool, "run", forbidden)
    root = project(tmp_path / "project")
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        call(app, "/inspector", method="POST", value=str(root))
        status, html, headers = call(app, "/entities?" + query)
        assert status == 400 and headers["Cache-Control"] == "no-store"
        assert 'role="alert"' in html


def test_xss_blanks_and_limit(tmp_path: Path) -> None:
    with running(RecentProjects(tmp_path / "recent.json")) as app:
        value = '"><script>alert(1)</script>'
        status, html, _ = call(app, "/entities?" + urlencode({"q": value}))
        assert status == 200 and "<script>alert" not in html
        dom = SvgDocument()
        dom.feed(html)
        assert any(
            a.get("name") == "q" and a.get("value") == value for _, a in dom.tags
        )
        assert "Aucun projet ouvert." in html
        for query in ("q=&q=Article", "q=&q=", "type=&type=entity", "q=" + "a" * 256):
            assert call(app, "/entities?" + query)[0] == 200
