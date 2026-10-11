"""Synthèse de santé de Project Inspector (FD-PROJECT-006) : sections, sévérités,
agrégation, résultats partiels, isolation, réutilisation des analyses existantes
et lecture seule."""

import json
import shutil
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest

from forge_design.app import create_tool_registry
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.limits import MAX_HEALTH_VISIBLE_DIAGNOSTICS
from forge_design.platform.tool_registry import ToolRegistry
from forge_design.tools.entity_explorer import EntityExplorerTool
from forge_design.tools.project_health import (
    SECTION_KEYS,
    HealthAction,
    HealthSection,
    ProjectHealthSummary,
    aggregate_status,
    summarize_project_health,
)
from forge_design.tools.project_inspector import inspect_project

CONTACT_ENTITY = {
    "schema_version": "1.0",
    "name": "Contact",
    "table": "contact",
    "fields": [
        {"name": "title", "type": "string", "max_length": 255, "required": True}
    ],
    "options": {"timestamps": False, "soft_delete": False},
}


def minimal(root: Path) -> Path:
    """Squelette requis seulement : trois fichiers d'entrée, mvc/ et mvc/routes/."""
    root.mkdir(parents=True)
    for name in ("app.py", "bootstrap.py", "config.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "mvc/routes").mkdir(parents=True)
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    return root.resolve()


def healthy(root: Path) -> Path:
    """Projet sain : une route, une entité, un template, un contrat, une migration."""
    minimal(root)
    for name in (
        "controllers",
        "entities",
        "forms",
        "helpers",
        "models",
        "validators",
        "views",
    ):
        (root / "mvc" / name).mkdir(exist_ok=True)
    (root / "mvc/controllers/home.py").write_text(
        'class Home:\n    def index(self): return BaseController.render("home.html")\n'
    )
    (root / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import Home\nrouter = Router()\n"
        'router.add("GET", "/", Home.index, public=True)\n'
    )
    (root / "mvc/views/home.html").write_text("<p>Bonjour</p>")
    (root / "mvc/views/home.view.json").write_text(
        json.dumps({"name": "home", "template": "mvc/views/home.html", "context": {}})
    )
    entity(root, "contact", CONTACT_ENTITY)
    (root / "mvc/migrations").mkdir()
    (root / "mvc/migrations/20260101120000_init.sql").write_text(
        "CREATE TABLE x (id INT);"
    )
    return root.resolve()


def entity(root: Path, folder: str, data: object) -> None:
    directory = root / "mvc/entities" / folder
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{folder}.json").write_text(json.dumps(data))


def journal(root: Path, *levels: str) -> None:
    path = root / "storage/logs/errors.dev.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    events = [
        dict(
            schema_version="1.0",
            id=f"e{index}",
            timestamp=f"2026-09-2{index}T10:00:00+00:00",
            environment="dev",
            level=level,
            category="runtime",
            exception_type="RuntimeError",
            message=f"boom {index}",
            safe_for_display=False,
        )
        for index, level in enumerate(levels)
    ]
    path.write_text("".join(json.dumps(event) + "\n" for event in events))


def summary(root: Path, registry: ToolRegistry | None = None) -> ProjectHealthSummary:
    return summarize_project_health(root, registry or create_tool_registry())


def statuses(value: ProjectHealthSummary) -> dict[str, str]:
    return {section.key: section.status for section in value.sections}


def snapshot(root: Path) -> dict[str, tuple[int, bytes | None]]:
    return {
        str(path): (
            path.stat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in sorted(root.rglob("*"))
    }


# --- Cas de projet --------------------------------------------------------------------


def test_healthy_project_is_ok_in_every_section(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    value = summary(root)
    assert value.status == "ok"
    assert (
        [section.key for section in value.sections]
        == list(SECTION_KEYS)
        == [
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
    )
    assert set(statuses(value).values()) == {"ok"}
    assert value.root == root and value.name == "projet"
    assert value.inspection is not None and value.inspection.forge_version == "1.0.0rc9"
    facts = {section.key: dict(section.facts) for section in value.sections}
    assert facts["project"] == {"Nom": "projet", "Dossier": str(root)}
    assert facts["forge"]["Projet Forge reconnu"] == "oui"
    assert facts["forge"]["Version détectée"] == "1.0.0rc9"
    assert facts["forge"]["Compatibilité Forge Design"] == (
        "non évaluée (aucune règle de version définie)"
    )
    assert facts["structure"]["Éléments requis trouvés"] == "5 / 5"
    assert (
        facts["routes"]["Routes"] == "1" and facts["routes"]["Méthodes HTTP"] == "GET"
    )
    assert facts["routes"]["Routes sans diagnostic"] == "1"
    assert facts["entities"]["Entités"] == "1" and facts["entities"]["Relations"] == "0"
    assert facts["templates"]["Fichiers détectés"] == "2"
    assert facts["templates"]["Templates de vue"] == "1"
    assert facts["migrations"]["Migrations"] == "1"
    assert (
        facts["contracts"]["Contrats"] == "1" and facts["contracts"]["Valides"] == "1"
    )
    assert facts["contracts"]["Templates associés"] == "1"
    # Mise en garde permanente de lecture statique des routes : information seulement.
    routes = value.section("routes")
    assert [item.severity for item in routes.diagnostics] == ["info"]


def test_minimal_project(tmp_path: Path) -> None:
    root = minimal(tmp_path / "projet")
    value = summary(root)
    found = statuses(value)
    # Pas de mvc/routes/__init__.py : la lecture des routes est indisponible, comme
    # sur la page Route Explorer ; le reste est présenté.
    assert found["routes"] == "indisponible"
    assert value.section("routes").summary.startswith("Analyse indisponible : ")
    # Dossiers optionnels absents : simple information, jamais une anomalie.
    structure = value.section("structure")
    assert structure.status == "ok"
    assert {item.severity for item in structure.diagnostics} == {"info"}
    assert dict(structure.facts)["Éléments optionnels trouvés"] == "aucun"
    assert dict(structure.facts)["Anomalies"] == "0"
    for key in ("entities", "templates", "migrations", "diagnostics", "contracts"):
        assert found[key] == "ok", key
    assert value.section("entities").diagnostics[0].severity == "info"
    # Les avertissements de structure ne sont pas recopiés dans la section Forge.
    assert value.section("forge").diagnostics == ()
    assert value.status == "attention"


def test_undetermined_forge_version_is_attention(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    (root / "requirements.txt").unlink()
    value = summary(root)
    forge = value.section("forge")
    assert forge.status == "attention" and value.status == "attention"
    assert forge.summary == "Projet Forge reconnu ; version indéterminée."
    assert dict(forge.facts)["Version détectée"] == "indéterminée"
    assert [item.message for item in forge.diagnostics] == [
        "Version Forge absente ou indéterminable.",
        "requirements.txt absent.",
    ]


def test_routes_with_errors_and_warnings(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    (root / "mvc/controllers/home.py").write_text(
        "class Home:\n"
        '    def index(self): return BaseController.render("home.html")\n'
        '    def missing(self): return BaseController.render("absent.html")\n'
        "    def dynamic(self): return BaseController.render(name)\n"
    )
    (root / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import Home\nrouter = Router()\n"
        'router.add("GET", "/", Home.index, public=True)\n'
        'router.add("POST", "/missing", Home.missing)\n'
        'router.add("GET", "/dynamic", Home.dynamic)\n'
    )
    value = summary(root)
    routes = value.section("routes")
    facts = dict(routes.facts)
    assert routes.status == "erreur" and value.status == "erreur"
    assert facts["Routes"] == "3" and facts["Méthodes HTTP"] == "GET, POST"
    assert facts["Routes avec diagnostic"] == "2"
    assert facts["Routes sans diagnostic"] == "1"
    assert {item.severity for item in routes.diagnostics} >= {"error", "warning"}


def test_real_route_limits_stay_warnings(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    # Branchement déclaré mais introuvable : vraie limite de lecture, en plus de la
    # mise en garde permanente.
    (root / "mvc/routes/__init__.py").write_text(
        "from mvc.controllers.home import Home\n"
        "from mvc.routes.admin import register_admin_routes\nrouter = Router()\n"
        'router.add("GET", "/", Home.index, public=True)\n'
        "register_admin_routes(router)\n"
    )
    routes = summary(root).section("routes")
    assert routes.status == "attention"
    assert [(item.severity, item.subject) for item in routes.diagnostics] == [
        ("warning", "mvc/routes/__init__.py")
    ]


def test_entities_with_relations_and_errors(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    entity(root, "broken", {"name": "Broken"})
    value = summary(root)
    entities = value.section("entities")
    assert entities.status == "erreur"
    assert dict(entities.facts)["Erreurs"] != "0"
    assert entities.action == HealthAction("Voir les entités", "/entities")


def test_templates_and_contracts_anomalies_are_attention(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    (root / "mvc/views/broken.view.json").write_text("{")
    (root / "mvc/views/orphan.view.json").write_text(
        json.dumps({"name": "orphan", "template": "mvc/views/none.html", "context": {}})
    )
    value = summary(root)
    contracts = value.section("contracts")
    facts = dict(contracts.facts)
    assert contracts.status == "attention"
    assert (
        facts["Contrats"] == "3"
        and facts["Invalides"] == "1"
        and facts["Valides"] == "2"
    )
    assert {item.severity for item in contracts.diagnostics} == {"warning"}
    assert value.status == "attention"
    assert (
        dict(value.section("templates").facts)["Métadonnées (.view.json, .design.json)"]
        == "3"
    )


def test_migrations_section(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    migrations = root / "mvc/migrations"
    (migrations / "bad name.sql").write_text("x")
    (migrations / "20260102120000_empty.sql").touch()
    (migrations / "notes.txt").write_text("ignored")
    value = summary(root)
    section = value.section("migrations")
    assert section.status == "attention" and value.status == "attention"
    assert dict(section.facts)["Migrations"] == "3"
    assert [(item.severity, item.subject) for item in section.diagnostics] == [
        ("warning", "20260102120000_empty.sql"),
        ("warning", "bad name.sql"),
    ]
    assert section.action is None


def test_runtime_errors_are_attention_never_project_error(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    journal(root, "ERROR", "CRITICAL", "WARNING", "INFO")
    value = summary(root)
    diagnostics = value.section("diagnostics")
    assert diagnostics.status == "attention" and value.status == "attention"
    assert dict(diagnostics.facts) == {
        "Erreurs (ERROR, CRITICAL)": "2",
        "Avertissements": "1",
        "Informations": "1",
        "Anomalies de lecture du journal": "0",
    }
    # Ordre du Debug Center (filtre par défaut).
    assert diagnostics.diagnostics[0].severity in {"error", "warning", "info"}
    assert diagnostics.diagnostic_total == 4
    # Seuls des événements INFO : rien à signaler.
    journal(root, "INFO")
    assert summary(root).section("diagnostics").status == "ok"


def test_visible_diagnostics_are_bounded(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    for index in range(MAX_HEALTH_VISIBLE_DIAGNOSTICS + 3):
        (root / f"mvc/migrations/bad{index}.sql").write_text("x")
    section = summary(root).section("migrations")
    assert section.diagnostic_total == MAX_HEALTH_VISIBLE_DIAGNOSTICS + 3
    assert len(section.diagnostics) == MAX_HEALTH_VISIBLE_DIAGNOSTICS == 5


def test_optional_directory_invalid_is_attention(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    shutil.rmtree(root / "mvc/forms")
    (root / "mvc/forms").write_text("not a directory")
    structure = summary(root).section("structure")
    assert structure.status == "attention"
    assert [(i.severity, i.subject) for i in structure.diagnostics] == [
        ("warning", "mvc/forms")
    ]


# --- Projet devenu invalide ou inaccessible -------------------------------------------


def test_project_no_longer_recognised(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    (root / "app.py").unlink()
    value = summary(root)
    found = statuses(value)
    assert value.status == "erreur"
    assert found["structure"] == "erreur" and found["forge"] == "erreur"
    for key in SECTION_KEYS[3:]:
        assert found[key] == "indisponible", key


@pytest.mark.parametrize("change", ["removed", "file"])
def test_project_inaccessible(tmp_path: Path, change: str) -> None:
    root = healthy(tmp_path / "projet")
    shutil.rmtree(root)
    if change == "file":
        root.write_text("plus un dossier")
    value = summary(root)
    assert value.status == "indisponible"
    assert set(statuses(value).values()) == {"indisponible"}
    assert value.section("project").summary.startswith("Projet inaccessible : ")
    assert value.inspection is None and value.structure == ()


# --- Agrégation -----------------------------------------------------------------------


def section(status: Any) -> HealthSection:
    return HealthSection("routes", "Routes", status, "")


@pytest.mark.parametrize(
    ("values", "available", "expected"),
    [
        (("ok", "ok"), True, "ok"),
        (("ok", "attention"), True, "attention"),
        (("ok", "indisponible"), True, "attention"),
        (("attention", "erreur", "indisponible"), True, "erreur"),
        (("indisponible", "indisponible"), False, "indisponible"),
        (("erreur", "indisponible"), False, "erreur"),
        ((), True, "ok"),
    ],
)
def test_aggregation(values: tuple[str, ...], available: bool, expected: str) -> None:
    assert (
        aggregate_status(
            (section(value) for value in values), project_available=available
        )
        == expected
    )


# --- Isolation des sections -----------------------------------------------------------


def test_one_failing_section_does_not_fail_the_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = healthy(tmp_path / "projet")

    def refused(self: EntityExplorerTool, project_root: Path) -> None:
        raise NotForgeProjectError("lecture refusée pour le test")

    monkeypatch.setattr(EntityExplorerTool, "run", refused)
    value = summary(root)
    found = statuses(value)
    assert found["entities"] == "indisponible"
    assert value.section("entities").summary == (
        "Analyse indisponible : lecture refusée pour le test"
    )
    assert {key: status for key, status in found.items() if key != "entities"} == {
        key: "ok" for key in SECTION_KEYS if key != "entities"
    }
    # Section secondaire indisponible : attention, jamais « indisponible » global.
    assert value.status == "attention"


def test_unexpected_errors_are_bugs_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = healthy(tmp_path / "projet")

    def broken(self: EntityExplorerTool, project_root: Path) -> None:
        raise RuntimeError("bug interne")

    monkeypatch.setattr(EntityExplorerTool, "run", broken)
    with pytest.raises(RuntimeError, match="bug interne"):
        summary(root)


def test_wrong_tool_result_is_a_type_error(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")

    class Wrong:
        id = "route-explorer"
        name = "Faux"
        description = "Faux"

        def run(self, project_root: Path) -> object:
            return object()

    registry = create_tool_registry()
    registry._tools["route-explorer"] = Wrong()  # pyright: ignore[reportPrivateUsage, reportArgumentType]
    with pytest.raises(TypeError, match="route-explorer doit retourner RoutesResult"):
        summary(root, registry)


# --- Réutilisation des analyses existantes --------------------------------------------


class SpyRegistry(ToolRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []
        for tool in create_tool_registry().list():
            self.register(tool)

    def get(self, tool_id: str) -> Any:
        self.calls.append(tool_id)
        return super().get(tool_id)


def test_each_existing_analysis_runs_once_through_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import forge_design.contracts.linkage as linkage
    import forge_design.tools.project_health as health

    root = healthy(tmp_path / "projet")
    registry = SpyRegistry()
    migrations: list[Path] = []
    original = health.read_migrations

    def counted(project_root: Path) -> Any:
        migrations.append(project_root)
        return original(project_root)

    def rescan(*args: object) -> None:
        raise AssertionError("mvc/views rebalayé par l'analyse des contrats")

    monkeypatch.setattr(health, "read_migrations", counted)
    monkeypatch.setattr(linkage, "read_templates", rescan)
    value = summarize_project_health(root, registry)
    assert value.status == "ok"
    assert sorted(registry.calls) == sorted(
        [
            "project-inspector",
            "template-viewer",
            "route-explorer",
            "entity-explorer",
            "debug-center",
        ]
    )
    assert migrations == [root]


def test_fresh_inspection_is_reused(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    registry = SpyRegistry()
    inspection = inspect_project(root)
    value = summarize_project_health(root, registry, inspection=inspection)
    assert "project-inspector" not in registry.calls
    assert value.inspection is inspection
    # Inspection d'une autre racine : jamais reprise.
    other = replace(inspection, root=tmp_path)
    summarize_project_health(root, registry, inspection=other)
    assert registry.calls.count("project-inspector") == 1


# --- Navigation, frontières, lecture seule --------------------------------------------


def test_navigation_targets_existing_tools(tmp_path: Path) -> None:
    value = summary(healthy(tmp_path / "projet"))
    actions = {
        section.key: (section.action.label, section.action.url)
        if section.action
        else None
        for section in value.sections
    }
    assert actions == {
        "project": None,
        "forge": ("Voir le détail de l’inspection", "/inspector#inspection-details"),
        "structure": (
            "Voir le détail de l’inspection",
            "/inspector#inspection-details",
        ),
        "routes": ("Voir les routes", "/routes"),
        "entities": ("Voir les entités", "/entities"),
        "templates": ("Voir les templates", "/templates"),
        "migrations": None,
        "diagnostics": ("Voir les diagnostics", "/debug"),
        "contracts": ("Voir les templates et leurs contrats", "/templates"),
    }


def test_tool_registry_keeps_exactly_five_tools() -> None:
    assert [tool.id for tool in create_tool_registry().list()] == [
        "project-inspector",
        "route-explorer",
        "entity-explorer",
        "debug-center",
        "template-viewer",
    ]


def test_summary_is_read_only_and_immutable(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    journal(root, "ERROR")
    before = snapshot(root)
    value = summary(root)
    assert snapshot(root) == before
    assert not (root / ".forge-design").exists()
    with pytest.raises(FrozenInstanceError):
        value.status = "ok"  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(FrozenInstanceError):
        value.sections[0].status = "erreur"  # pyright: ignore[reportAttributeAccessIssue]


def test_summary_is_recomputed_not_cached(tmp_path: Path) -> None:
    root = healthy(tmp_path / "projet")
    registry = create_tool_registry()
    assert summarize_project_health(root, registry).status == "ok"
    (root / "mvc/migrations/oops.sql").write_text("x")
    assert summarize_project_health(root, registry).status == "attention"
