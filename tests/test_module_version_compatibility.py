"""Compatibilité déclarée entre Forge Design et ses modules (FD-RELEASE-001).

Trois notions séparées : version de distribution du cœur
(``forge_design.__version__``), version du contrat (``MODULE_API_VERSION``,
inchangée à 1), versions du cœur acceptées par un module
(``requires_forge_design``, spécificateur PEP 440). Les modules témoins restent
autonomes : aucun test ne dépend du dépôt Circuit.
"""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from flow_witness import flow_bytes, flow_module
from test_web_module_actions import opened, post
from test_web_modules import navigation, serving
from test_web_recent_projects import call, project

import forge_design
from forge_design.modules import (
    DESCRIPTOR_ATTRIBUTE,
    MODULE_API_VERSION,
    ModuleActivation,
    ModuleDescriptor,
    activate_modules,
)
from forge_design.modules.host import ModuleHost


def importer_of(**packages: object):
    def load(name: str) -> object:
        value = packages.get(name)
        if value is None:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(**{DESCRIPTOR_ATTRIBUTE: value})

    return load


def activate(*modules: tuple[str, object], core: str | None = None) -> ModuleActivation:
    return activate_modules(
        tuple(name for name, _ in modules),
        importer_of(**dict(modules)),
        core_version=core,
    )


def flow(module_id: str = "flow", requires: str | None = None) -> ModuleDescriptor:
    return flow_module(module_id, requires=requires)


# Contrat du descripteur (premier niveau : forme seulement).


def test_requirement_is_optional_and_api_stays_1() -> None:
    descriptor = flow()
    assert descriptor.requires_forge_design is None
    assert descriptor.api_version == MODULE_API_VERSION == 1
    assert flow(requires=">=0.2.0,<1").requires_forge_design == ">=0.2.0,<1"


@pytest.mark.parametrize(
    "value", ["", "   ", "x" * 201, ">=0.2\n", 2, b">=0.2", (">=0.2",)]
)
def test_descriptor_refuses_unsound_requirement_shapes(value: object) -> None:
    with pytest.raises(ValueError, match="requires_forge_design"):
        replace(flow(), requires_forge_design=value)  # type: ignore[arg-type]


def test_descriptor_accepts_any_bounded_text_activation_interprets_it() -> None:
    # Un spécificateur syntaxiquement faux passe le descripteur ; l'activation
    # le refuse avec un diagnostic explicite (deuxième niveau).
    descriptor = flow(requires=">=deux")
    result = activate(("pkg_flow", descriptor), core="0.2.0")
    assert result.modules == ()
    [diagnostic] = result.diagnostics
    assert (diagnostic.package, diagnostic.code) == ("pkg_flow", "descriptor-invalid")
    assert diagnostic.message == (
        "requires_forge_design invalide : '>=deux' (spécificateur PEP 440 attendu)."
    )


# Comparaison PEP 440 (préversions acceptées dans l'intervalle).


@pytest.mark.parametrize(
    "core,requires,compatible",
    [
        ("0.2.0", None, True),
        ("0.1.0.dev0", None, True),
        ("0.2.0", ">=0.2.0", True),
        ("0.2.0", "==0.2.0", True),
        ("0.1.0.dev0", ">=0.2.0", False),
        # Préversions : 0.2.0.dev0 précède 0.2.0 ; 0.3.0.dev0 la suit.
        ("0.2.0.dev0", ">=0.2.0", False),
        ("0.3.0.dev0", ">=0.2.0", True),
        ("0.2.0rc1", ">=0.2.0", False),
        ("0.2.0", ">=0.2.0,<1", True),
        ("0.9.4", ">=0.2.0,<1", True),
        ("1.0.0", ">=0.2.0,<1", False),
        ("1.0.0.dev0", ">=0.2.0,<1", False),
        ("0.3.9", ">=0.2,<0.4", True),
        ("0.4.0", ">=0.2,<0.4", False),
        ("0.2.5", "~=0.2.0", True),
        ("0.3.0", "~=0.2.0", False),
        ("0.3.0", "~=0.3", True),
        ("0.2.7", "==0.2.*", True),
        ("0.3.0", "==0.2.*", False),
    ],
)
def test_core_version_matrix(core: str, requires: str | None, compatible: bool) -> None:
    result = activate(("pkg_flow", flow(requires=requires)), core=core)
    assert bool(result.modules) is compatible, result.diagnostics
    if compatible:
        assert result.diagnostics == ()
    else:
        [diagnostic] = result.diagnostics
        assert diagnostic.code == "core-version-incompatible"
        assert diagnostic.message == (
            f"Le module « flow » nécessite forge-design {requires}, "
            f"version installée : {core}."
        )


@pytest.mark.parametrize("core", ["", "pas-une-version", "0.2.0-beta-x"])
def test_unknown_core_version_fails_closed_only_for_constrained_modules(
    core: str,
) -> None:
    result = activate(
        ("pkg_free", flow("free")),
        ("pkg_bound", flow("bound", requires=">=0.2.0")),
        core=core,
    )
    assert [module.descriptor.id for module in result.modules] == ["free"]
    [diagnostic] = result.diagnostics
    assert (diagnostic.package, diagnostic.code) == (
        "pkg_bound",
        "core-version-unknown",
    )
    assert diagnostic.message == (
        "Le module « bound » nécessite forge-design >=0.2.0, "
        "version de Forge Design indéterminée."
    )


def test_production_version_is_the_authoritative_core_version() -> None:
    assert forge_design.__version__ == "0.4.5"
    result = activate(
        ("pkg_ok", flow("ok", requires=">=0.2.0,<1")),
        ("pkg_future", flow("future", requires=">=9999")),
    )
    assert [module.descriptor.id for module in result.modules] == ["ok"]
    assert result.diagnostics[0].message == (
        "Le module « future » nécessite forge-design >=9999, version installée : 0.4.5."
    )


# Diagnostics distincts et isolation.


def test_api_contract_and_core_version_are_separate_diagnostics() -> None:
    api_v2 = replace(flow("api", requires=">=9999"), api_version=2)
    result = activate(
        ("pkg_api", api_v2),
        ("pkg_core", flow("core", requires=">=9999")),
        (
            "pkg_import",
            ImportError("cannot import name 'NewFeature' from 'forge_design.modules'"),
        ),
        core="0.2.0",
    )
    assert [(d.package, d.code) for d in result.diagnostics] == [
        # Contrat majeur non supporté : vérifié avant la version du cœur.
        ("pkg_api", "api-incompatible"),
        # Contrat compris, implémentation du cœur hors intervalle.
        ("pkg_core", "core-version-incompatible"),
        # Le module n'a pas pu fournir son descripteur : limite du contrôle runtime.
        ("pkg_import", "module-import-failed"),
    ]
    assert result.diagnostics[2].message == "ImportError"


def test_incompatible_module_is_isolated_between_compatible_ones() -> None:
    result = activate(
        ("pkg_a", flow("flow-a", requires=">=0.2.0")),
        ("pkg_b", flow("flow-b", requires=">=9999")),
        ("pkg_c", flow("flow-c")),
        core="0.2.0",
    )
    assert [module.descriptor.id for module in result.modules] == ["flow-a", "flow-c"]
    assert [(d.package, d.code) for d in result.diagnostics] == [
        ("pkg_b", "core-version-incompatible")
    ]
    assert "« flow-b »" in result.diagnostics[0].message


def test_incompatible_module_exposes_nothing(tmp_path: Path) -> None:
    activation = activate(
        ("pkg_ok", flow("flow", requires=">=0.2.0,<1")),
        ("pkg_new", flow("flow-new", requires=">=9999")),
    )
    host = ModuleHost(activation)
    assert [module.descriptor.id for module in host.modules()] == ["flow"]
    assert [entry.module_id for entry in host.navigation()] == ["flow"]
    for probe in (
        lambda: host.module("flow-new"),
        lambda: host.asset("flow-new", "flow-editor.js"),
        lambda: host.actions("flow-new"),
        lambda: host.resource_type("flow-new", "flow"),
    ):
        with pytest.raises(KeyError):
            probe()
    root = project(tmp_path / "projet").resolve()
    for module_id in ("flow", "flow-new"):
        (root / f"mvc/{module_id}").mkdir(parents=True)
        (root / f"mvc/{module_id}/demo.{module_id}.json").write_bytes(flow_bytes())
    with serving(tmp_path, activation) as app:
        opened(app, root)
        status, html, _ = call(app, "/")
        assert status == 200
        workshop = call(app, "/inspector")[1]
        assert [href for href, _ in navigation(workshop)[1]] == ["/modules/flow/"]
        # Diagnostic visible avec les autres diagnostics d'activation.
        assert "Modules non chargés" in html
        assert "pkg_new" in html and "core-version-incompatible" in html
        assert "nécessite forge-design &gt;=9999" in html
        for url in (
            "/modules/flow-new/",
            "/modules/flow-new/resource?type=flow&path=mvc%2Fflow-new%2Fdemo.flow-new.json",
            "/modules/flow-new/assets/flow-editor.js",
        ):
            assert call(app, url)[0] == 404, url
        assert (
            post(app, "/modules/flow-new/actions/rename-step", [("type", "flow")])[0]
            == 404
        )
        # Le module compatible fonctionne.
        assert call(app, "/modules/flow/assets/flow-editor.js")[0] == 200
        assert call(app, "/modules/flow/")[0] == 200
