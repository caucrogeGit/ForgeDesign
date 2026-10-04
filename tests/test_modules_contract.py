"""Contrat des modules spécialisés : descripteur, activation explicite, frontières.

Le module témoin (FakeSpecializedModule) n'existe que dans ces tests ; il est
fourni par un importeur injecté, sans toucher sys.path ni installer de paquet.
"""

import ast
import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from specialized_support import (
    WITNESS_PATH,
    WITNESS_PREFIX,
    WitnessCodec,
    WitnessDocument,
    make_project,
    witness_tool,
    witness_type,
)

from forge_design.app import create_tool_registry
from forge_design.modules import (
    ASSET_MEDIA_TYPES,
    DESCRIPTOR_ATTRIBUTE,
    MODULE_API_VERSION,
    ModuleAsset,
    ModuleDescriptor,
    ResourceBinding,
    activate_modules,
)
from forge_design.specialized import (
    OptionalDependency,
    SpecializedCapability,
    read_specialized_resource,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "forge_design"
SIMULATE = SpecializedCapability.tool("simulate")


def scene_of(document: WitnessDocument) -> dict[str, Any]:
    return {
        "width": 200,
        "height": 80,
        "nodes": [
            {
                "id": "title",
                "label": document.title,
                "rect": {"x": 0, "y": 0, "width": 200, "height": 80},
            }
        ],
        "edges": [],
    }


def descriptor(**changes: Any) -> ModuleDescriptor:
    values: dict[str, Any] = {
        "definition": witness_tool(),
        "version": "0.1.0",
        "api_version": MODULE_API_VERSION,
        "bindings": (ResourceBinding("document", WitnessCodec(), scene_of),),
        "asset_package": "fake_specialized_module.static",
        "assets": (
            ModuleAsset("viewer.js", "viewer.js"),
            ModuleAsset("viewer.css", "css/viewer.css"),
        ),
    }
    values.update(changes)
    return ModuleDescriptor(**values)


class FakeImporter:
    """Importeur injecté : paquets connus, absents ou en échec, appels comptés."""

    def __init__(self, **modules: object) -> None:
        self.modules = modules
        self.calls: list[str] = []

    def __call__(self, name: str) -> object:
        self.calls.append(name)
        module = self.modules.get(name)
        if module is None:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        if isinstance(module, Exception):
            raise module
        return module


def fake_module(value: object) -> SimpleNamespace:
    return SimpleNamespace(**{DESCRIPTOR_ATTRIBUTE: value})


def test_descriptor_is_frozen_and_routes_are_namespaced() -> None:
    item = descriptor()
    assert item.id == "witness"
    assert item.base_url == "/modules/witness/"
    assert item.asset_url("viewer.js") == "/modules/witness/assets/viewer.js"
    assert [a.media_type for a in item.assets] == [
        ASSET_MEDIA_TYPES["js"],
        ASSET_MEDIA_TYPES["css"],
    ]
    assert item.binding("document").scene is scene_of
    with pytest.raises(KeyError):
        item.asset_url("other.js")
    with pytest.raises(FrozenInstanceError):
        item.version = "9"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        item.assets[0].name = "x.js"  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"version": ""}, "Version"),
        ({"version": "1.0 beta"}, "Version"),
        ({"api_version": "1"}, "api_version"),
        ({"api_version": True}, "api_version"),
        ({"definition": "witness"}, "SpecializedToolDefinition"),
        ({"bindings": ()}, "exactement un codec"),
        (
            {
                "bindings": (
                    ResourceBinding("document", WitnessCodec()),
                    ResourceBinding("document", WitnessCodec()),
                )
            },
            "exactement un codec",
        ),
        ({"bindings": (ResourceBinding("other", WitnessCodec()),)}, "exactement"),
        ({"bindings": [ResourceBinding("document", WitnessCodec())]}, "tuple"),
        (
            {"assets": (ModuleAsset("a.js", "a.js"), ModuleAsset("a.js", "b.js"))},
            "dupliqué",
        ),
        ({"assets": tuple(ModuleAsset(f"a{i}.js", "a.js") for i in range(33))}, "32"),
        ({"asset_package": None}, "paquet"),
        ({"asset_package": "../static"}, "paquet"),
        ({"dependency_probe": "yes"}, "sonde"),
    ],
)
def test_descriptor_refuses(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        descriptor(**changes)


def test_module_id_is_bounded_kebab_case() -> None:
    with pytest.raises(ValueError):
        witness_tool(id="Circuit")
    with pytest.raises(ValueError, match="trop long"):
        descriptor(definition=witness_tool(id="a" * 33))


@pytest.mark.parametrize(
    "name,source",
    [
        ("Viewer.js", "viewer.js"),
        ("viewer.html", "viewer.html"),
        ("viewer.js.map", "viewer.js"),
        ("../x.js", "x.js"),
        ("x.js", "/abs/x.js"),
        ("x.js", "../x.js"),
        ("x.js", "a/../x.js"),
        ("x.js", "./x.js"),
        ("x.js", "a//x.js"),
        ("x.js", ".hidden/x.js"),
        ("x.js", "a\\x.js"),
        ("x.js", "a/x.js\x00"),
        ("x.js", ""),
    ],
)
def test_assets_are_a_closed_relative_list(name: str, source: str) -> None:
    with pytest.raises(ValueError):
        ModuleAsset(name, source)


def test_codec_must_be_complete() -> None:
    class Partial:
        def decode(self, data: bytes) -> object:
            return data

    with pytest.raises(ValueError, match="detect_version, encode, validate"):
        ResourceBinding("document", Partial())
    with pytest.raises(ValueError, match="appelable"):
        ResourceBinding("document", WitnessCodec(), "scene")  # type: ignore[arg-type]


def test_explicit_activation_in_configured_order() -> None:
    other = descriptor(
        definition=witness_tool(
            id="other",
            resource_types=(witness_type(source_prefix="mvc/resources/other"),),
        )
    )
    importer = FakeImporter(
        first_pkg=fake_module(descriptor()), second_pkg=fake_module(other)
    )
    result = activate_modules(("second_pkg", "first_pkg"), importer)
    assert importer.calls == ["second_pkg", "first_pkg"]
    assert [m.descriptor.id for m in result.modules] == ["other", "witness"]
    assert result.diagnostics == ()
    assert result.module("witness").package == "first_pkg"
    assert activate_modules((), importer).modules == ()


def test_nothing_is_imported_unless_configured() -> None:
    importer = FakeImporter(fake_pkg=fake_module(descriptor()))
    assert activate_modules((), importer).modules == ()
    assert importer.calls == []


@pytest.mark.parametrize(
    "packages",
    [
        "fake_pkg",
        ("fake_pkg", "fake_pkg"),
        ("../fake",),
        ("fake-pkg",),
        ("",),
        ("fake pkg",),
    ],
)
def test_malformed_configuration_fails_fast(packages: Any) -> None:
    importer = FakeImporter(fake_pkg=fake_module(descriptor()))
    with pytest.raises(ValueError, match="Configuration des modules"):
        activate_modules(packages, importer)
    assert importer.calls == []


def test_failures_are_isolated_with_diagnostics() -> None:
    incompatible = replace(descriptor(), api_version=2)
    duplicate = descriptor()
    same_resources = descriptor(definition=witness_tool(id="copycat"))
    importer = FakeImporter(
        good=fake_module(descriptor()),
        broken=RuntimeError("boom"),
        bare=SimpleNamespace(),
        wrong=fake_module({"id": "x"}),
        future=fake_module(incompatible),
        twin=fake_module(duplicate),
        copycat=fake_module(same_resources),
    )
    result = activate_modules(
        ("good", "absent", "broken", "bare", "wrong", "future", "twin", "copycat"),
        importer,
    )
    assert [m.package for m in result.modules] == ["good"]
    assert [(d.package, d.code) for d in result.diagnostics] == [
        ("absent", "module-missing"),
        ("broken", "module-import-failed"),
        ("bare", "descriptor-missing"),
        ("wrong", "descriptor-invalid"),
        ("future", "api-incompatible"),
        ("twin", "duplicate-module"),
        ("copycat", "duplicate-resource-type"),
    ]
    messages = {d.code: d.message for d in result.diagnostics}
    assert messages["module-import-failed"] == "RuntimeError"
    assert "API 2 non supportée" in messages["api-incompatible"]
    assert WITNESS_PREFIX in messages["duplicate-resource-type"]


def test_missing_inner_dependency_is_an_import_failure() -> None:
    """Un module installé dont une dépendance manque n'est pas « non installé »."""
    inner = ModuleNotFoundError("No module named 'numpy'", name="numpy")
    result = activate_modules(("needs_dep",), FakeImporter(needs_dep=inner))
    assert [(d.code, d.message) for d in result.diagnostics] == [
        ("module-import-failed", "ModuleNotFoundError: numpy")
    ]
    # importlib signale le parent absent : c'est bien le paquet configuré qui manque.
    absent_parent = ModuleNotFoundError("No module named 'vendor'", name="vendor")
    parent = activate_modules(
        ("vendor.sub",), FakeImporter(**{"vendor.sub": absent_parent})
    )
    assert [d.code for d in parent.diagnostics] == ["module-missing"]


def _with_simulation(probe: Any) -> ModuleDescriptor:
    capabilities = (*witness_tool().capabilities, SIMULATE)
    definition = witness_tool(
        capabilities=capabilities,
        optional_dependencies=(
            OptionalDependency("spice", "Moteur de simulation", (SIMULATE,)),
        ),
    )
    return descriptor(definition=definition, dependency_probe=probe)


def test_optional_dependency_disables_only_its_capabilities() -> None:
    def absent() -> dict[str, bool]:
        return {"spice": False}

    def failing() -> dict[str, bool]:
        raise OSError("sonde")

    def present() -> dict[str, bool]:
        return {"spice": True}

    for probe, diagnostics in ((absent, []), (failing, ["dependency-probe-failed"])):
        result = activate_modules(
            ("sim",), FakeImporter(sim=fake_module(_with_simulation(probe)))
        )
        module = result.module("witness")
        assert "simulate" not in module.available_capabilities
        assert {"open", "validate", "save"} <= module.available_capabilities
        assert dict(module.unavailable_dependencies) == {
            "spice": "Moteur de simulation"
        }
        assert [d.code for d in result.diagnostics] == diagnostics
    result = activate_modules(
        ("sim",), FakeImporter(sim=fake_module(_with_simulation(present)))
    )
    assert "simulate" in result.module("witness").available_capabilities
    assert dict(result.module("witness").unavailable_dependencies) == {}


def test_activated_module_reads_through_the_host_only(tmp_path: Path) -> None:
    """Le module fournit le codec ; l'hôte lit le fichier et contrôle tout."""
    root = make_project(tmp_path / "project")
    path = root / WITNESS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"format_version": "0.1", "title": "T", "content": "C"}))
    module = activate_modules(
        ("fake_pkg",), FakeImporter(fake_pkg=fake_module(descriptor()))
    ).module("witness")
    binding = module.descriptor.binding("document")
    definition = module.descriptor.definition
    result = read_specialized_resource(
        root,
        definition,
        definition.resource_type("document"),
        WITNESS_PATH,
        binding.codec,
    )
    assert result.resource == WitnessDocument("T", "C")
    assert binding.scene is not None
    assert binding.scene(result.resource)["nodes"][0]["label"] == "T"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_core_never_imports_circuit() -> None:
    """Direction des dépendances : seul forge_design/circuit (à migrer) s'importe."""
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.is_relative_to(PACKAGE / "circuit"):
            continue
        for name in _imports(path):
            assert not name.startswith("forge_design.circuit"), path
            assert not name.startswith("forge_design_circuit"), path


def test_module_contract_depends_only_on_the_specialized_contract() -> None:
    """Contrat et hôte : contrat spécialisé, erreurs de racine, stdlib ; jamais Web."""
    allowed = {
        "forge_design.specialized",
        "forge_design.modules",
        "forge_design.forge.project_root",
        "forge_design.forge.project_version",
    }
    stdlib = {
        "re",
        "json",
        "logging",
        "importlib",
        "importlib.resources",
        "collections.abc",
        "dataclasses",
        "pathlib",
        "types",
        "typing",
    }
    for path in sorted((PACKAGE / "modules").glob("*.py")):
        for name in _imports(path):
            if name.startswith("forge_design"):
                assert any(name.startswith(item) for item in allowed), (path, name)
            else:
                assert name in stdlib, (path, name)
        source = path.read_text(encoding="utf-8")
        for forbidden in ("entry_points", "pkgutil", "sys.path", "importlib.metadata"):
            assert forbidden not in source, (path, forbidden)


def test_graphics_and_tool_registry_know_no_module() -> None:
    for path in [
        *(PACKAGE / "graphics").rglob("*.py"),
        *(PACKAGE / "web/static/graphics").glob("*.js"),
    ]:
        text = path.read_text(encoding="utf-8").lower()
        assert "circuit" not in text, path
    assert sorted(tool.id for tool in create_tool_registry().list()) == [
        "debug-center",
        "entity-explorer",
        "project-inspector",
        "route-explorer",
        "template-viewer",
    ]
