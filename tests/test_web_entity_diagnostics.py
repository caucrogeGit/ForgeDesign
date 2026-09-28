"""Diagnostics rendus par HTTP, échappement et conservation des données."""

from pathlib import Path

import pytest
from test_entity_graph import entity, relation
from test_web_entity_graph import SvgDocument
from test_web_recent_projects import call, project, running

from forge_design.forge.entities import EntitiesResult, EntityIssue
from forge_design.forge.source import SourceLocation
from forge_design.recent_projects import RecentProjects
from forge_design.tools.entity_explorer import EntityExplorerTool


@pytest.mark.parametrize("errors,warnings", [(0, 0), (1, 0), (0, 1), (3, 2)])
def test_http_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, errors: int, warnings: int
) -> None:
    root = project(tmp_path / "project")
    issues = (
        EntityIssue(
            "entity.json_invalid",
            '<script>message</script>"&',
            SourceLocation('mvc/entities/<script>source</script>"&'),
        ),
        EntityIssue(
            "relation.entity_missing",
            "Cible absente",
            SourceLocation("mvc/entities/relations.json"),
            0,
        ),
        EntityIssue(
            "relation.structure_invalid", "Relation incorrecte", source_index=2
        ),
        EntityIssue(
            "entity.unreadable", "Illisible", SourceLocation("mvc/entities/a/a.json")
        ),
        EntityIssue(
            "relation.type_unsupported",
            "Type inconnu",
            SourceLocation("mvc/entities/relations.json"),
            3,
        ),
    )
    result = EntitiesResult(
        (entity("Article"), entity("Tag")),
        errors=issues[:errors],
        warnings=issues[errors : errors + warnings],
        relations=(relation("Article", "Tag"), relation("Article", "Missing")),
    )
    calls: list[Path] = []

    def run(self: EntityExplorerTool, project_root: Path) -> EntitiesResult:
        calls.append(project_root)
        return result

    monkeypatch.setattr(EntityExplorerTool, "run", run)
    with running(RecentProjects(tmp_path / "config/recent.json")) as app:
        html = call(app, "/entities")[1]
        assert "Aucun projet ouvert." in html and 'id="entity-diagnostics"' not in html
        assert calls == []
        call(app, "/inspector", method="POST", value=str(root))
        status, html, headers = call(app, "/entities")
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert calls == [root]
        assert (
            f"{errors} erreur(s) — {warnings} avertissement(s) — 0 information(s)"
            in html
        )
        document = SvgDocument()
        document.feed(html)
        rows = [
            attrs
            for tag, attrs in document.tags
            if tag == "li" and "data-diagnostic-code" in attrs
        ]
        selected = result.errors + result.warnings
        assert [r["data-diagnostic-code"] for r in rows] == [i.code for i in selected]
        assert [r["data-diagnostic-severity"] for r in rows] == ["error"] * errors + [
            "warning"
        ] * warnings
        text = "".join(document.text)
        for i, (issue, row) in enumerate(zip(selected, rows)):
            assert issue.code in text and issue.message in text
            assert ("Erreur" if i < errors else "Avertissement") in text
            if issue.source:
                assert issue.source.path in text
            if issue.source_index is not None:
                assert row["data-diagnostic-relation-index"] == str(issue.source_index)
                assert f"relations[{issue.source_index}]" in text
        assert ("Aucun diagnostic dans les informations disponibles." in html) == (
            not selected
        )
        section = next(
            a
            for _, a in document.tags
            if a.get("aria-labelledby") == "entity-diagnostics"
        )
        assert "aria-live" not in section
        assert "/source?path=" in html and "<script>message" not in html
        assert "<script>source" not in html
        assert [a.get("src") for tag, a in document.tags if tag == "script"] == [
            "/entity-graph.js"
        ]
        assert '<svg class="entity-graph"' in html and html.count("<table>") >= 4
        assert "Missing" in html and "Relations" in text and "Timestamps" in text
