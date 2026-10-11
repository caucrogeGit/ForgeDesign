"""Chaîne statique d'une route (FD-ROUTES-021) : route → handler → contrôleur et
méthode → template(s) → contrat(s) de vue → diagnostics avec origine."""

import re
from dataclasses import FrozenInstanceError
from html import unescape
from pathlib import Path
from typing import Any

import pytest
from route_linkage_support import (
    ABSENT,
    DYN,
    DYNAMIC,
    EDIT,
    FN,
    GONE,
    HOSTILE,
    JSON,
    MIXED,
    NOMETHOD,
    ORPHAN,
    SHOW,
    UNRESOLVED,
    chain_project,
)
from test_project_health import snapshot
from test_web_modules import serving
from test_web_recent_projects import call

from forge_design.app import create_tool_registry
from forge_design.contracts import analyze_view_contract_links
from forge_design.forge.routes import TemplateCandidate, read_routes
from forge_design.forge.templates import read_templates
from forge_design.tools.route_diagnostics import build_route_diagnostics
from forge_design.tools.route_linkage import (
    ORIGINS,
    RouteLinkageReport,
    build_route_linkage,
    origin_of,
)


def report(root: Path, *, contracts: bool = True) -> RouteLinkageReport:
    result = read_routes(root)
    links = (
        analyze_view_contract_links(root, read_templates(root)) if contracts else None
    )
    return build_route_linkage(
        result, build_route_diagnostics(result), links, contracts_reason="raison"
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return chain_project(tmp_path / "projet")


# --- Candidats conservés par le lecteur de routes -------------------------------------


def test_reader_keeps_literal_candidates_in_source_order(project: Path) -> None:
    routes = read_routes(project).routes
    edit = routes[EDIT].handler
    assert edit is not None and edit.template.status == "ambiguous"
    assert edit.template.path is None
    assert edit.template.candidates == (
        TemplateCandidate(
            "users/edit.html", "present", edit.template.candidates[0].source
        ),
        TemplateCandidate(
            "users/error.html", "present", edit.template.candidates[1].source
        ),
    )
    assert [c.source.path for c in edit.template.candidates if c.source] == [
        "mvc/views/users/edit.html",
        "mvc/views/users/error.html",
    ]
    mixed = routes[MIXED].handler
    assert mixed is not None and mixed.template.status == "dynamic"
    # Présence vérifiée pour chaque candidat, pas seulement pour un template exact.
    assert [(c.path, c.presence) for c in mixed.template.candidates] == [
        ("users/show.html", "present"),
        ("users/ghost.html", "missing"),
    ]
    dyn = routes[DYN].handler
    assert dyn is not None and dyn.template.candidates == ()
    show = routes[SHOW].handler
    assert show is not None and show.template.status == "found"
    assert [(c.path, c.presence) for c in show.template.candidates] == [
        ("users/show.html", "present")
    ]
    gone = routes[GONE].handler
    assert gone is not None
    assert [(c.path, c.presence) for c in gone.template.candidates] == [
        ("users/missing.html", "missing")
    ]


def test_duplicate_literals_are_one_candidate(tmp_path: Path) -> None:
    root = chain_project(tmp_path / "projet")
    controller = root / "mvc/controllers/users.py"
    controller.write_text(
        controller.read_text().replace(
            'return BaseController.render("users/error.html")',
            'return BaseController.render("users/edit.html")',
        )
    )
    template = read_routes(root).routes[EDIT].handler.template  # type: ignore[union-attr]
    # Deux appels au même littéral : un seul template, statut exact inchangé.
    assert template.status == "found" and template.path == "users/edit.html"
    assert [c.path for c in template.candidates] == ["users/edit.html"]


# --- Liaison --------------------------------------------------------------------------


def test_complete_chain_with_valid_contract(project: Path) -> None:
    chain = report(project).routes[SHOW]
    assert (chain.handler_kind, chain.controller_state, chain.confidence) == (
        "controller-method",
        "resolved",
        "exact",
    )
    assert chain.state == "complete" and chain.diagnostics == ()
    (template,) = chain.templates
    assert (template.path, template.presence, template.contract_state) == (
        "users/show.html",
        "present",
        "linked",
    )
    assert template.contracts == ("users/show.view.json",)
    assert chain.route.name == HOSTILE


@pytest.mark.parametrize(
    ("index", "kind", "controller", "confidence", "state"),
    [
        (EDIT, "controller-method", "resolved", "multiple", "partial"),
        (DYN, "controller-method", "resolved", "unknown", "partial"),
        (MIXED, "controller-method", "resolved", "partial", "partial"),
        (JSON, "controller-method", "resolved", "none", "partial"),
        (GONE, "controller-method", "resolved", "exact", "problematic"),
        (
            NOMETHOD,
            "controller-method",
            "method-missing",
            "not-applicable",
            "problematic",
        ),
        (ABSENT, "controller-method", "file-missing", "not-applicable", "problematic"),
        (FN, "function", "not-applicable", "not-applicable", "partial"),
        (UNRESOLVED, "unresolved", "not-applicable", "not-applicable", "partial"),
        (DYNAMIC, "dynamic", "not-applicable", "not-applicable", "partial"),
        (ORPHAN, "controller-method", "resolved", "exact", "complete"),
    ],
)
def test_chain_states(
    project: Path, index: int, kind: str, controller: str, confidence: str, state: str
) -> None:
    chain = report(project).routes[index]
    assert (
        chain.handler_kind,
        chain.controller_state,
        chain.confidence,
        chain.state,
    ) == (
        kind,
        controller,
        confidence,
        state,
    )


def test_exact_template_must_be_present_to_complete() -> None:
    from forge_design.forge.routes import (
        HandlerInfo,
        RouteInfo,
        RoutesResult,
        TemplateResolution,
    )

    def chain(presence: Any) -> Any:
        template = TemplateResolution("found", "a.html", presence)
        handler = HandlerInfo(
            "Home.index", "mvc/controllers/home.py", "found", template
        )
        result = RoutesResult((RouteInfo("GET", "/", None, True, handler),), ())
        return build_route_linkage(
            result, build_route_diagnostics(result), None
        ).routes[0]

    assert chain("present").state == "complete"
    # Présence non vérifiable : avertissement, chaîne seulement partielle.
    unreadable = chain("unreadable")
    assert unreadable.state == "partial"
    assert [(i.severity, i.code) for i in unreadable.diagnostics] == [
        ("warning", "template.unreadable")
    ]
    assert chain("not-applicable").state == "partial"


def test_multiple_templates_each_with_its_contract(project: Path) -> None:
    chain = report(project).routes[EDIT]
    assert [(t.path, t.contract_state, t.contracts) for t in chain.templates] == [
        (
            "users/edit.html",
            "ambiguous",
            ("users/edit-bis.view.json", "users/edit.view.json"),
        ),
        ("users/error.html", "without-contract", ()),
    ]
    # Incertitudes : avertissements, jamais des erreurs.
    assert {item.severity for item in chain.diagnostics} == {"warning"}
    assert [(item.origin, item.code) for item in chain.diagnostics] == [
        ("template", "template.ambiguous"),
        ("contract", "contract.link.multiple-contracts"),
        ("contract", "contract.link.multiple-contracts"),
    ]
    assert {item.subject for item in chain.diagnostics[1:]} == {
        "users/edit.view.json",
        "users/edit-bis.view.json",
    }


def test_dynamic_template_is_undeterminable_not_absent(project: Path) -> None:
    chain = report(project).routes[DYN]
    assert chain.templates == ()
    assert [(i.origin, i.severity, i.code) for i in chain.diagnostics] == [
        ("template", "warning", "template.dynamic")
    ]
    partial = report(project).routes[MIXED]
    assert [(t.path, t.presence, t.contract_state) for t in partial.templates] == [
        ("users/show.html", "present", "linked"),
        ("users/ghost.html", "missing", "not-applicable"),
    ]
    # Un candidat absent n'est pas une erreur démontrée : la branche peut ne pas
    # être exécutée ; la chaîne reste partielle.
    assert partial.state == "partial"


def test_errors_keep_their_origin(project: Path) -> None:
    routes = report(project).routes
    assert [(i.origin, i.severity, i.code) for i in routes[GONE].diagnostics] == [
        ("template", "error", "template.missing")
    ]
    assert routes[GONE].templates[0].contract_state == "not-applicable"
    assert [(i.origin, i.code) for i in routes[NOMETHOD].diagnostics] == [
        ("controller", "controller.method_missing")
    ]
    assert "Méthode absente : Users.nope" in routes[NOMETHOD].diagnostics[0].message
    assert [(i.origin, i.code) for i in routes[ABSENT].diagnostics] == [
        ("controller", "controller.missing")
    ]
    assert [(i.origin, i.code) for i in routes[DYNAMIC].diagnostics] == [
        ("handler", "handler.dynamic")
    ]


def test_invalid_contracts_stay_global(project: Path) -> None:
    value = report(project)
    overview = value.contracts
    assert overview.available and overview.total == 4 and overview.invalid == 1
    assert [
        (i.origin, i.severity, i.code, i.subject) for i in overview.diagnostics
    ] == [("contract", "warning", "contract.json_invalid", "users/broken.view.json")]
    assert overview.diagnostics[0].source is not None
    assert overview.diagnostics[0].source.path == "mvc/views/users/broken.view.json"
    # Jamais rattaché à une route, même sans contrat.
    for chain in value.routes:
        assert all(i.code != "contract.json_invalid" for i in chain.diagnostics)


def test_contracts_unavailable(project: Path) -> None:
    value = report(project, contracts=False)
    assert not value.contracts.available and value.contracts.reason == "raison"
    assert value.routes[SHOW].templates[0].contract_state == "unknown"
    assert value.routes[SHOW].state == "complete"


def test_origins_follow_the_chain_order() -> None:
    assert ORIGINS == (
        "route",
        "handler",
        "controller",
        "template",
        "dependency",
        "contract",
    )
    assert origin_of("route.partial") == "route"
    assert origin_of("handler.dynamic") == "handler"
    assert origin_of("controller.missing") == "controller"
    assert origin_of("template.missing") == "template"
    assert origin_of("template.dependency_missing") == "dependency"
    assert origin_of("contract.link.multiple-contracts") == "contract"
    with pytest.raises(ValueError, match="Origine inconnue"):
        origin_of("autre.code")


def test_select_follows_the_filtered_routes(project: Path) -> None:
    value = report(project)
    routes = read_routes(project).routes
    assert value.select(()) == ()
    assert value.select(value.routes[i].route for i in (GONE, SHOW)) == (
        value.routes[SHOW],
        value.routes[GONE],
    )
    # Mêmes valeurs mais autres objets : rien n'est choisi par ressemblance.
    assert value.select(routes[:1]) == ()


def test_report_is_immutable(project: Path) -> None:
    chain = report(project).routes[SHOW]
    with pytest.raises(FrozenInstanceError):
        chain.state = "problematic"  # pyright: ignore[reportAttributeAccessIssue]


# --- Page Route Explorer --------------------------------------------------------------


def page(
    tmp_path: Path, root: Path, url: str = "/routes"
) -> tuple[int, str, dict[str, str]]:
    with serving(tmp_path, None) as app:
        assert call(app, "/inspector", method="POST", value=str(root))[0] == 200
        return call(app, url)


def chain_item(html: str, index: int) -> str:
    match = re.search(rf'<li id="route-chain-{index}".*?</details></li>', html, re.S)
    assert match is not None, index
    return match.group(0)


def summary_of(item: str) -> str:
    match = re.search(r"<summary>(.*?)</summary>", item, re.S)
    assert match is not None
    return text(match.group(1))


def text(fragment: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def test_page_shows_compact_chains_and_details(tmp_path: Path, project: Path) -> None:
    status, html, headers = page(tmp_path, project)
    assert status == 200 and headers["Cache-Control"] == "no-store"
    show = chain_item(html, SHOW)
    assert 'data-chain-state="complete"' in show
    summary = summary_of(show)
    assert summary == (
        "GET /users/{id} → Users.show → users/show.html → users/show.view.json"
        " — ✓ Complète"
    )
    assert (
        '<a href="/templates/view?path=users%2Fshow.html">users/show.html</a>' in show
    )
    assert (
        '<a href="/source?path=mvc%2Fviews%2Fusers%2Fshow.view.json">'
        "users/show.view.json</a>" in show
    )
    assert '<a href="/source?path=mvc%2Fcontrollers%2Fusers.py">' in show
    edit = summary_of(chain_item(html, EDIT))
    assert edit == (
        "GET /users/{id}/edit → Users.edit → users/edit.html | users/error.html → "
        "users/edit-bis.view.json, users/edit.view.json | sans contrat — ◐ Partielle"
    )
    assert "template non déterminable" in text(chain_item(html, DYN))
    assert "Non déterminable statiquement" in text(chain_item(html, DYN))
    assert "users/show.html | users/ghost.html | ?" in text(chain_item(html, MIXED))
    assert "users/ghost.html — Absent" in text(chain_item(html, MIXED))
    assert "aucun rendu détecté" in text(chain_item(html, JSON))
    gone = chain_item(html, GONE)
    assert 'data-chain-state="problematic"' in gone and "✕ Problématique" in gone
    assert '<li data-origin="template" data-diagnostic-code="template.missing"' in gone
    assert "Méthode absente : Users.nope" in text(chain_item(html, NOMETHOD))
    assert "Fonction (non analysée) : home" in text(chain_item(html, FN))
    # Contrat invalide : section globale seulement, mention sans attribution.
    contracts = html.split('<h2 id="route-contracts-title">')[1].split("</section>")[0]
    assert "4 contrat(s) de vue, dont 1 invalide(s)." in contracts
    assert 'data-diagnostic-code="contract.json_invalid"' in contracts
    orphan = chain_item(html, ORPHAN)
    assert "des contrats invalides non associables existent" in orphan
    assert "contract.json_invalid" not in orphan
    # Tableau, filtres et graphe existants conservés.
    assert "<table>" in html and 'action="/routes"' in html


def test_hostile_values_are_escaped(tmp_path: Path, project: Path) -> None:
    _, html, _ = page(tmp_path, project)
    show = chain_item(html, SHOW)
    assert (
        "<script>"
        not in html.split("<main")[1]
        .split("</main>")[0]
        .replace('<script type="application/json" data-graphic-scene>', "")
        .split('<script type="module"')[0]
    )
    assert "&lt;script&gt;" in show and HOSTILE in text(show)


def test_filters_apply_to_chains(tmp_path: Path, project: Path) -> None:
    _, html, _ = page(tmp_path, project, "/routes?q=gone")
    assert re.findall(r'<li id="route-chain-(\d+)"', html) == [str(GONE)]
    _, html, _ = page(
        tmp_path / "b", project, "/routes?severity=error&diagnostics=only"
    )
    assert re.findall(r'<li id="route-chain-(\d+)"', html) == [
        str(GONE),
        str(NOMETHOD),
        str(ABSENT),
    ]


def test_one_inventory_and_one_link_analysis_per_display(
    tmp_path: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import forge_design.contracts.linkage as linkage
    import forge_design.tools.template_viewer as viewer
    import forge_design.web.routes as routes_page

    counts: dict[str, int] = {"read_templates": 0, "analyze": 0}
    original_read = viewer.read_templates
    original_analyze = routes_page.analyze_view_contract_links

    def read(root: Path) -> Any:
        counts["read_templates"] += 1
        return original_read(root)

    def analyze(root: Path, templates: Any = None) -> Any:
        counts["analyze"] += 1
        assert templates is not None, "inventaire non transmis"
        return original_analyze(root, templates)

    def rescan(*args: object) -> None:
        raise AssertionError("mvc/views rebalayé")

    with serving(tmp_path, None) as app:
        assert call(app, "/inspector", method="POST", value=str(project))[0] == 200
        monkeypatch.setattr(viewer, "read_templates", read)
        monkeypatch.setattr(routes_page, "analyze_view_contract_links", analyze)
        monkeypatch.setattr(linkage, "read_templates", rescan)
        assert call(app, "/routes")[0] == 200
    # 12 routes : un seul inventaire, une seule analyse des liens.
    assert counts == {"read_templates": 1, "analyze": 1}


def test_unavailable_contracts_keep_the_routes(
    tmp_path: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from forge_design.forge.project_version import NotForgeProjectError
    from forge_design.tools.template_viewer import TemplateViewerTool

    def refused(self: TemplateViewerTool, root: Path) -> None:
        raise NotForgeProjectError("inventaire refusé")

    with serving(tmp_path, None) as app:
        assert call(app, "/inspector", method="POST", value=str(project))[0] == 200
        monkeypatch.setattr(TemplateViewerTool, "run", refused)
        status, html, _ = call(app, "/routes")
    assert status == 200
    assert "Analyse des contrats de vue indisponible : inventaire refusé" in html
    assert len(re.findall(r'<li id="route-chain-', html)) == 12
    assert "Liaison inconnue" in chain_item(html, SHOW)


def test_page_is_read_only(tmp_path: Path, project: Path) -> None:
    before = snapshot(project)
    page(tmp_path, project)
    assert snapshot(project) == before and not (project / ".forge-design").exists()


def test_project_without_routes(tmp_path: Path) -> None:
    root = chain_project(tmp_path / "projet")
    (root / "mvc/routes/__init__.py").write_text("router = Router()\n")
    _, html, _ = page(tmp_path, root)
    assert "Aucune route à afficher." in html


def test_tool_registry_unchanged() -> None:
    assert [tool.id for tool in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]
