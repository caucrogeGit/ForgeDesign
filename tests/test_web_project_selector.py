"""Les deux entrées Web passent par le même service de sélection."""

from pathlib import Path

import pytest
from test_web_recent_projects import call, project, running

from forge_design.current_project import CurrentProjectContext
from forge_design.project_selector import ProjectSelectionResult, ProjectSelector
from forge_design.recent_projects import RecentProjects
from forge_design.web import recent_projects as recent_web


def test_handlers_delegate_without_parallel_mutations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "project")
    store = RecentProjects(tmp_path / "config/recent.json")
    store.add(root)
    calls: list[tuple[ProjectSelector, Path]] = []

    def select(self: ProjectSelector, path: Path) -> ProjectSelectionResult:
        calls.append((self, path))
        return ProjectSelectionResult("selected", recent_warning="<private> warning")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Mutation or inspection outside selector")

    # L'inspection d'affichage FD004 est indépendante de la sélection.
    def no_states(*args: object) -> tuple[()]:
        return ()

    monkeypatch.setattr(recent_web, "inspect_recent_projects", no_states)
    monkeypatch.setattr(ProjectSelector, "open", select)
    monkeypatch.setattr(CurrentProjectContext, "set_project", forbidden)
    monkeypatch.setattr(RecentProjects, "add", forbidden)
    from forge_design.platform.tool_registry import ToolRegistry

    monkeypatch.setattr(ToolRegistry, "get", forbidden)
    with running(store) as app, running(store) as other:
        assert call(app, "/inspector", method="POST", value=str(root))[0] == 200
        status, html, headers = call(
            app, "/project/open-recent", method="POST", value=str(root)
        )
        assert status == 200 and "Projet ouvert." in html and "Projets récents" in html
        assert "&lt;private&gt; warning" in html and "<private>" not in html
        assert headers["Cache-Control"] == "no-store"
        assert calls[0][0] is calls[1][0]
        for url in ("/", "/inspector", "/project/open-recent"):
            call(app, url)
        assert len(calls) == 2
        assert call(app, "/project/open-recent", method="POST", value="/fake")[0] == 400
        for origin, site in (
            ("https://evil.example", "same-origin"),
            ("local", "cross-site"),
        ):
            assert (
                call(
                    app,
                    "/project/open-recent",
                    method="POST",
                    value=str(root),
                    origin=origin,
                    site=site,
                )[0]
                == 403
            )
        assert len(calls) == 2
        call(other, "/inspector", method="POST", value=str(root))
        assert calls[-1][0] is not calls[0][0]
