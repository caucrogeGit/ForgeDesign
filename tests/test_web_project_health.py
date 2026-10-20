"""Synthèse de santé sur la page Project Inspector (FD-PROJECT-006) : HTTP réel,
sans JavaScript, sans cache, lecture seule, isolation et liens vers les outils."""

import re
import shutil
from html import unescape
from pathlib import Path

import pytest
from module_support import activation, witness_module
from test_project_health import healthy, journal, snapshot
from test_web_modules import serving
from test_web_recent_projects import call

from forge_design.tools.entity_explorer import EntityExplorerTool
from forge_design.web.server import ForgeDesignServer

SECTIONS = [
    "project",
    "forge",
    "structure",
    "routes",
    "entities",
    "templates",
    "migrations",
    "diagnostics",
    "contracts",
]


def open_project(app: ForgeDesignServer, root: Path) -> str:
    status, html, _ = call(app, "/inspector", method="POST", value=str(root))
    assert status == 200
    return html


def health(html: str) -> str:
    match = re.search(r'<section class="health-summary".*?\n    </section>', html, re.S)
    assert match is not None
    return match.group(0)


def section(html: str, key: str) -> str:
    match = re.search(
        rf'<section class="health-section"[^>]*data-health-section="{key}"'
        r".*?</section>",
        html,
        re.S,
    )
    assert match is not None, key
    return match.group(0)


def test_without_project_nothing_is_analysed(tmp_path: Path) -> None:
    with serving(tmp_path, None) as app:
        status, html, headers = call(app, "/inspector")
    assert status == 200 and headers["Cache-Control"] == "no-store"
    assert "Aucun projet sélectionné\u00a0: aucune analyse." in html
    assert '<a href="/">ouvrez un projet récent depuis l’accueil</a>' in html
    assert "health-summary" not in html and "data-health-section" not in html


def test_refused_opening_analyses_nothing(tmp_path: Path) -> None:
    other = tmp_path / "pas-forge"
    other.mkdir()
    with serving(tmp_path, None) as app:
        status, html, _ = call(app, "/inspector", method="POST", value=str(other))
    assert status == 200 and "Projet Forge non reconnu" in html
    assert "health-summary" not in html
    assert "Aucun projet sélectionné\u00a0: aucune analyse." in html


def test_summary_after_opening_and_on_reload(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    before = snapshot(root)
    with serving(tmp_path, None) as app:
        opened = health(open_project(app, root))
        status, html, headers = call(app, "/inspector")
    assert status == 200 and headers["Cache-Control"] == "no-store"
    summary = health(html)
    assert summary == opened
    assert 'data-health-status="ok"' in summary
    assert '<h2 id="health-title">Synthèse du projet projet</h2>' in summary
    assert re.findall(r'data-health-section="([a-z]+)"', summary) == SECTIONS
    # Chaque état est écrit et marqué, jamais transmis par la seule couleur.
    assert (
        summary.count('<span class="health-mark" aria-hidden="true">✓</span> OK') == 10
    )
    links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', summary)
    assert links == [
        ("/inspector#inspection-details", "Voir le détail de l’inspection"),
        ("/inspector#inspection-details", "Voir le détail de l’inspection"),
        ("/routes", "Voir les routes"),
        ("/entities", "Voir les entités"),
        ("/templates", "Voir les templates"),
        ("/debug", "Voir les diagnostics"),
        ("/templates", "Voir les templates et leurs contrats"),
    ]
    assert 'id="inspection-details"' in html
    # Hiérarchie : h1, puis h2 de synthèse, puis un h3 par section.
    headings = re.findall(r"<h([1-3])", html)
    assert headings[:3] == ["1", "2", "3"] and headings.count("3") >= len(SECTIONS)
    assert "<script" not in summary and "hx-" not in html
    assert snapshot(root) == before and not (root / ".forge-design").exists()


def test_bounded_diagnostics_and_attention(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    for index in range(8):
        (root / f"mvc/migrations/bad{index}.sql").write_text("x")
    journal(root, "ERROR")
    with serving(tmp_path, None) as app:
        html = open_project(app, root)
    summary = health(html)
    assert 'data-health-status="attention"' in summary
    migrations = section(summary, "migrations")
    assert "8 diagnostics, 5 premiers affichés." in migrations
    assert migrations.count("<li data-severity=") == 5
    diagnostics = section(summary, "diagnostics")
    assert (
        'data-status="attention"' in diagnostics
        and "ERROR · RuntimeError" in diagnostics
    )


def test_dashboard_tiles_priorities_and_commands(tmp_path: Path) -> None:
    """Tableau de bord (FD-UX-002) : résumé en titre de tuile, faits visibles,
    diagnostics repliables, priorités hors de la synthèse (erreurs d'abord, six
    au plus), commandes renvoyées vers les sections réelles de Debug Center."""
    root = healthy(tmp_path / "projet")
    for index in range(8):
        (root / f"mvc/migrations/bad{index}.sql").write_text("x")
    journal(root, "ERROR")
    with serving(tmp_path, None) as app:
        html = open_project(app, root)
        _, debug, _ = call(app, "/debug")
    migrations = section(health(html), "migrations")
    assert '<p class="health-headline">' in migrations
    assert "<summary>8 diagnostics</summary>" in migrations
    # Les faits clés restent visibles : une tuile en Attention montre sa raison.
    assert "<dl>" in migrations.split("<details", 1)[0]
    panels = html.split('<div class="inspector-panels">', 1)[1]
    priorities, commands = panels.split('<section class="inspector-commands"', 1)
    severities = re.findall(r'<li data-severity="([a-z]+)">', priorities)
    assert 0 < len(severities) <= 6
    assert severities == sorted(severities, key=lambda severity: severity != "error")
    assert "ERROR · RuntimeError" in priorities
    anchors = re.findall(r'href="/debug#([a-z-]+)"', commands)
    assert anchors == [
        "forge-audit-title",
        "forge-diagnostic-title",
        "forge-check-title",
    ]
    for anchor in anchors:
        assert f'id="{anchor}"' in debug


def test_dashboard_without_priorities(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    with serving(tmp_path, None) as app:
        html = open_project(app, root)
    priorities = html.split('<section class="inspector-priorities"', 1)[1]
    priorities = priorities.split("</section>", 1)[0]
    assert "Aucune erreur ni aucun avertissement dans la synthèse." in priorities
    assert "<li" not in priorities


def test_inaccessible_project_is_a_controlled_diagnostic(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    with serving(tmp_path, None) as app:
        open_project(app, root)
        shutil.rmtree(root)
        status, html, _ = call(app, "/inspector")
    assert status == 200 and "Traceback" not in html
    summary = health(html)
    assert 'data-health-status="indisponible"' in summary
    assert "Projet inaccessible\u00a0: " in summary
    # Le GET ne ferme pas le projet ; seule l'actualisation le fait.
    assert f"Projet\u00a0: {root}" in html


def test_secondary_section_failure_keeps_the_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.forge.project_version import NotForgeProjectError

    root = healthy(tmp_path / "projet")

    def refused(self: EntityExplorerTool, project_root: Path) -> None:
        raise NotForgeProjectError("lecture refusée")

    with serving(tmp_path, None) as app:
        open_project(app, root)
        monkeypatch.setattr(EntityExplorerTool, "run", refused)
        status, html, _ = call(app, "/inspector")
    assert status == 200
    summary = health(html)
    assert 'data-health-status="attention"' in summary
    assert 'data-status="indisponible"' in section(summary, "entities")
    assert 'data-status="ok"' in section(summary, "routes")


def test_internal_bug_is_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = healthy(tmp_path / "projet")

    def broken(self: EntityExplorerTool, project_root: Path) -> None:
        raise RuntimeError("bug interne")

    with serving(tmp_path, None) as app:
        open_project(app, root)
        monkeypatch.setattr(EntityExplorerTool, "run", broken)
        status, html, _ = call(app, "/inspector")
    assert status == 500 and "bug interne" not in unescape(html)


def test_summary_is_unchanged_with_modules(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    with serving(tmp_path / "a", None) as app:
        alone = health(open_project(app, root))
    modules = activation(("pkg_witness", witness_module()))
    with serving(tmp_path / "b", modules) as app:
        html = open_project(app, root)
    assert health(html) == alone
    assert 'aria-label="Modules"' in html
