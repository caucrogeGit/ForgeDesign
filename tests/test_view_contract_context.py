"""Racine Forge vérifiée une fois pour l'analyse des contrats de vue (FD-PERF-001) :
mêmes résultats qu'avant, une seule détection, garde racine ↔ contexte et
protections de chaque fichier conservées."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from route_linkage_support import chain_project
from test_project_health import healthy

import forge_design.contracts.linkage as linkage
import forge_design.contracts.reader as reader
import forge_design.forge.checked_root as checked_module
import forge_design.forge.templates as templates_module
from forge_design.app import create_tool_registry
from forge_design.contracts import analyze_view_contract_links
from forge_design.forge.checked_root import CheckedForgeRoot, check_forge_root
from forge_design.forge.project_root import ProjectRootNotFoundError
from forge_design.forge.project_version import NotForgeProjectError
from forge_design.forge.routes import read_routes
from forge_design.forge.templates import read_templates
from forge_design.tools.project_health import summarize_project_health
from forge_design.tools.route_diagnostics import build_route_diagnostics
from forge_design.tools.route_linkage import build_route_linkage


def project(root: Path, contracts: int = 0) -> Path:
    """Projet Forge avec ``contracts`` paires template + contrat valides, plus un
    contrat JSON invalide, un contrat de schéma invalide, un template sans contrat
    et un template visé par deux contrats."""
    root.mkdir(parents=True)
    for name in ("app.py", "bootstrap.py", "config.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "mvc/routes").mkdir(parents=True)
    views = root / "mvc/views"
    views.mkdir()

    def contract(path: str, target: str, name: str) -> None:
        (views / path).write_text(
            json.dumps({"name": name, "template": f"mvc/views/{target}", "context": {}})
        )

    for index in range(contracts):
        (views / f"t{index}.html").write_text(f"<p>{index}</p>")
        contract(f"t{index}.view.json", f"t{index}.html", f"t{index}")
    (views / "broken.view.json").write_text("{")
    (views / "schema.view.json").write_text(json.dumps({"name": 3}))
    (views / "orphan.html").write_text("<p>sans contrat</p>")
    (views / "shared.html").write_text("<p>partagé</p>")
    contract("shared-a.view.json", "shared.html", "shared-a")
    contract("shared-b.view.json", "shared.html", "shared-b")
    return root.resolve()


@pytest.fixture
def detections(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Toutes les détections de racine passent par checked_root."""
    calls: list[Path] = []
    original = checked_module.detect_forge_project

    def counted(root: Any) -> Any:
        calls.append(Path(root))
        return original(root)

    monkeypatch.setattr(checked_module, "detect_forge_project", counted)
    return calls


def historical(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chemin d'avant FD-PERF-001 : chaque lecteur revérifie sa racine."""
    for name, function in (
        ("read_templates", templates_module.read_templates),
        ("read_view_contracts", reader.read_view_contracts),
        ("read_view_contract", reader.read_view_contract),
    ):

        def without_context(*args: Any, _function: Any = function, **_: Any) -> Any:
            return _function(*args)

        monkeypatch.setattr(linkage, name, without_context)


# --- Racine vérifiée ----------------------------------------------------------------


def test_check_forge_root_is_canonical_and_frozen(tmp_path: Path) -> None:
    root = project(tmp_path / "projet")
    checked = check_forge_root(tmp_path / "projet" / "mvc" / "..")
    assert checked == CheckedForgeRoot(root)
    assert checked.require(root) == root
    with pytest.raises(FrozenInstanceError):
        checked.root = tmp_path  # pyright: ignore[reportAttributeAccessIssue]


def test_same_errors_as_the_readers(tmp_path: Path) -> None:
    with pytest.raises(ProjectRootNotFoundError) as expected:
        reader.read_view_contracts(tmp_path / "absent")
    with pytest.raises(ProjectRootNotFoundError) as shared:
        check_forge_root(tmp_path / "absent")
    assert str(shared.value) == str(expected.value)
    with pytest.raises(NotForgeProjectError) as expected_forge:
        reader.read_view_contracts(tmp_path)
    with pytest.raises(NotForgeProjectError) as shared_forge:
        analyze_view_contract_links(tmp_path)
    assert str(shared_forge.value) == str(expected_forge.value)
    with pytest.raises(ProjectRootNotFoundError):
        analyze_view_contract_links(tmp_path / "absent")


def test_context_of_another_root_is_refused(tmp_path: Path) -> None:
    first = project(tmp_path / "a")
    second = project(tmp_path / "b")
    checked = check_forge_root(first)
    for call in (
        lambda: reader.read_view_contracts(second, checked=checked),
        lambda: reader.read_view_contract(second, "orphan.view.json", checked=checked),
        lambda: read_templates(second, checked=checked),
        # Même projet sous une forme non canonique : refusé, jamais re-résolu.
        lambda: reader.read_view_contracts(first / "mvc" / "..", checked=checked),
    ):
        with pytest.raises(ValueError, match="autre racine"):
            call()


# --- Mêmes résultats, avec ou sans contexte -----------------------------------------


def test_readers_give_identical_results(tmp_path: Path) -> None:
    root = project(tmp_path / "projet", contracts=3)
    checked = check_forge_root(root)
    assert reader.read_view_contracts(root, checked=checked) == (
        reader.read_view_contracts(root)
    )
    assert read_templates(root, checked=checked) == read_templates(root)
    for path in (
        "t0.view.json",
        "broken.view.json",
        "schema.view.json",
        "shared-a.view.json",
    ):
        alone = reader.read_view_contract(root, path)
        assert reader.read_view_contract(root, path, checked=checked) == alone
    codes = {
        path: [issue.code for issue in reader.read_view_contract(root, path).issues]
        for path in ("t0.view.json", "broken.view.json", "schema.view.json")
    }
    assert codes == {
        "t0.view.json": [],
        "broken.view.json": ["contract.json_invalid"],
        "schema.view.json": ["contract.validation_error"] * 3,
    }


@pytest.mark.parametrize("with_inventory", [True, False])
def test_analysis_identical_to_the_historical_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, with_inventory: bool
) -> None:
    root = project(tmp_path / "projet", contracts=5)
    inventory = read_templates(root) if with_inventory else None
    shared = analyze_view_contract_links(root, inventory)
    historical(monkeypatch)
    before = analyze_view_contract_links(root, inventory)
    assert shared == before
    statuses = {item.template_path: item.status for item in shared.templates}
    assert statuses["t0.html"] == "linked"
    assert statuses["orphan.html"] == "without-contract"
    assert statuses["shared.html"] == "ambiguous"
    assert [c.status for c in shared.contracts].count("contract-invalid") == 2
    assert [i.code for i in shared.contract_issues] == [
        "contract.json_invalid",
        "contract.validation_error",
        "contract.validation_error",
        "contract.validation_error",
    ]
    # Ordre absolu, celui du lecteur appelé seul (et non d'un autre chemin partagé).
    alone = reader.read_view_contract(root, "schema.view.json").issues
    assert [i for i in shared.contract_issues if i.path == "schema.view.json"] == list(
        alone
    )
    assert len({i.location for i in alone}) == 3


def test_route_linkage_and_cockpit_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = chain_project(tmp_path / "routes")
    cockpit = healthy(tmp_path / "cockpit")

    def snapshot() -> tuple[Any, Any]:
        result = read_routes(root)
        links = analyze_view_contract_links(root, read_templates(root))
        chains = build_route_linkage(result, build_route_diagnostics(result), links)
        contracts = summarize_project_health(cockpit, create_tool_registry()).section(
            "contracts"
        )
        return chains, contracts

    shared = snapshot()
    historical(monkeypatch)
    assert snapshot() == shared


# --- Une seule détection --------------------------------------------------------------


def test_one_detection_for_250_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, detections: list[Path]
) -> None:
    root = project(tmp_path / "projet", contracts=250)
    inventory = read_templates(root)
    detections.clear()
    result = analyze_view_contract_links(root, inventory)
    assert len(result.contracts) == 254
    assert detections == [root]
    detections.clear()
    analyze_view_contract_links(root)
    assert detections == [root], "inventaire lu avec la même racine vérifiée"
    # Lecteurs sans contexte (chemin historique) : une détection par contrat et une
    # pour l'inventaire, en plus de la vérification d'entrée de l'analyse.
    historical(monkeypatch)
    detections.clear()
    analyze_view_contract_links(root, inventory)
    assert len(detections) == 1 + 1 + 254


def test_each_file_is_still_opened_securely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path / "projet", contracts=2)
    outside = tmp_path / "outside.view.json"
    outside.write_text(json.dumps({"name": "x", "template": "mvc/views/t0.html"}))
    (root / "mvc/views/link.view.json").symlink_to(outside)
    opened: list[str] = []
    original = reader.read_project_source_details

    def counted(canonical: Path, path: str) -> Any:
        opened.append(path)
        return original(canonical, path)

    monkeypatch.setattr(reader, "read_project_source_details", counted)
    result = analyze_view_contract_links(root)
    # Chaque contrat inventorié est lu par l'ouverture confinée ; le lien n'est
    # pas inventorié comme fichier ordinaire, sa lecture directe reste refusée.
    assert sorted(opened) == sorted(
        f"mvc/views/{info.contract_path}" for info in result.contracts
    )
    assert "link.view.json" not in {info.contract_path for info in result.contracts}
    checked = check_forge_root(root)
    alone = reader.read_view_contract(root, "link.view.json")
    with_context = reader.read_view_contract(root, "link.view.json", checked=checked)
    assert with_context == alone
    assert [i.code for i in with_context.issues] == ["contract.unreadable"]
