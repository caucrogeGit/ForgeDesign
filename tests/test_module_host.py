"""Hôte des modules : exposition, assets, inventaire, lecture et projection isolées."""

import json
from pathlib import Path
from typing import Any

import pytest
from module_support import (
    ASSET_PACKAGE,
    ASSET_SOURCE,
    RecordingCodec,
    activation,
    prefix,
    witness_module,
    write_resource,
)
from specialized_support import make_project

from forge_design.forge.project_version import NotForgeProjectError
from forge_design.modules import ModuleAsset
from forge_design.modules.host import MAX_MODULE_SCENE_BYTES, ModuleHost

HOSTILE = "</script><svg onload=alert(1)>"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return make_project(tmp_path / "projet", witness_dir=False)


def host_of(*packages: tuple[str, object]) -> ModuleHost:
    return ModuleHost(activation(*packages))


def test_exposure_navigation_order_and_assets() -> None:
    host = host_of(
        ("pkg_b", witness_module("witness-b", label="Témoin B")),
        ("pkg_absent", None),
        ("pkg_a", witness_module("witness-a", label="Témoin A")),
        ("pkg_hidden", witness_module("headless", label=None)),
    )
    assert [m.descriptor.id for m in host.modules()] == [
        "witness-b",
        "witness-a",
        "headless",
    ]
    assert [(e.module_id, e.label, e.url) for e in host.navigation()] == [
        ("witness-b", "Témoin B", "/modules/witness-b/"),
        ("witness-a", "Témoin A", "/modules/witness-a/"),
    ]
    assert [(d.package, d.code) for d in host.diagnostics()] == [
        ("pkg_absent", "module-missing")
    ]
    from importlib.resources import files

    expected = files(ASSET_PACKAGE).joinpath(ASSET_SOURCE).read_bytes()
    assert host.asset("witness-a", "witness-a.css") == (
        expected,
        "text/css; charset=utf-8",
    )
    with pytest.raises(KeyError):
        host.asset("witness-a", "witness-b.css")
    with pytest.raises(KeyError):
        host.module("inconnu")


def test_missing_asset_hides_the_module_with_a_diagnostic() -> None:
    broken = witness_module("broken", assets=(ModuleAsset("x.js", "static/absent.js"),))
    host = host_of(("pkg_broken", broken), ("pkg_ok", witness_module()))
    assert [m.descriptor.id for m in host.modules()] == ["witness"]
    assert [(d.package, d.code) for d in host.diagnostics()] == [
        ("pkg_broken", "asset-missing")
    ]
    assert "x.js" in host.diagnostics()[0].message


def test_listing_through_the_host(root: Path) -> None:
    host = host_of(("pkg", witness_module()))
    write_resource(root, "witness", "b")
    write_resource(root, "witness", "a/c")
    ((resource_type, listing),) = host.list_resources("witness", root)
    assert resource_type.id == "document"
    assert listing.paths == (
        f"{prefix('witness')}/a/c.witness.json",
        f"{prefix('witness')}/b.witness.json",
    )


def test_read_and_project_with_module_code_seeing_only_bytes(root: Path) -> None:
    codec = RecordingCodec()
    received: list[str] = []

    def scene(document: Any) -> dict[str, Any]:
        received.append(type(document).__name__)
        from module_support import witness_scene

        return witness_scene(document)

    host = host_of(("pkg", witness_module(codec=codec, scene=scene)))
    path = write_resource(root, "witness", "demo", title=HOSTILE)
    view = host.read_resource("witness", "document", root, path)
    assert view.read is not None and view.read.error is None
    assert view.read.ref is not None and view.read.ref.format_version == "0.1"
    assert view.scene is not None and view.scene["nodes"][0]["label"] == HOSTILE
    assert view.scene_error is None and view.runtime_error is None
    # Le module ne reçoit que des octets puis son propre document : jamais un chemin.
    assert set(codec.received) == {bytes}
    assert received == ["WitnessDocument"]


def test_read_failures_are_reported_not_raised(root: Path) -> None:
    host = host_of(("pkg", witness_module()))
    invalid = write_resource(root, "witness", "invalid", raw=b"{not json")
    future = write_resource(root, "witness", "future", version="9.9")
    for path, category in (
        (invalid, "invalid-resource"),
        (future, "unsupported-version"),
        (f"{prefix('witness')}/absent.witness.json", "resource-not-found"),
        ("../../etc/passwd", "resource-refused"),
        (f"{prefix('witness')}/../../config.witness.json", "resource-refused"),
    ):
        view = host.read_resource("witness", "document", root, path)
        assert view.read is not None and view.read.error == category, path
        assert view.scene is None
        assert all(str(root) not in issue.message for issue in view.read.issues)


def test_unknown_module_type_and_project(root: Path, tmp_path: Path) -> None:
    host = host_of(("pkg", witness_module()))
    with pytest.raises(KeyError):
        host.read_resource("inconnu", "document", root, "x")
    with pytest.raises(KeyError):
        host.resource_type("witness", "autre")
    with pytest.raises(KeyError):
        host.resource_type("witness", "../document")
    (tmp_path / "pas-forge").mkdir()
    with pytest.raises(NotForgeProjectError):
        host.read_resource(
            "witness",
            "document",
            tmp_path / "pas-forge",
            write_resource(root, "witness", "a"),
        )
    with pytest.raises(NotForgeProjectError):
        host.list_resources("witness", tmp_path / "pas-forge")


def _crashing(document: object) -> object:
    return 1 / 0


def _not_an_object(document: object) -> object:
    return ["pas", "un", "objet"]


def _nan(document: object) -> object:
    return {"x": float("nan")}


def _opaque(document: object) -> object:
    return {"x": object()}


def _oversized(document: object) -> object:
    return {"x": "y" * (MAX_MODULE_SCENE_BYTES + 1)}


@pytest.mark.parametrize(
    "scene,expected",
    [
        (_crashing, "Projection graphique du module en échec (ZeroDivisionError)."),
        (_not_an_object, "ne rend pas un objet"),
        (_nan, "n'est pas du JSON"),
        (_opaque, "n'est pas du JSON"),
        (_oversized, "trop volumineuse"),
    ],
)
def test_projection_failures_are_isolated(
    root: Path, scene: Any, expected: str
) -> None:
    host = host_of(("pkg", witness_module(scene=scene)))
    path = write_resource(root, "witness", "demo")
    view = host.read_resource("witness", "document", root, path)
    assert view.read is not None and view.read.resource is not None
    assert view.scene is None
    assert view.scene_error is not None and expected in view.scene_error
    assert "Traceback" not in view.scene_error


def test_projection_is_detached_json(root: Path) -> None:
    produced: dict[str, Any] = {}

    def scene(document: Any) -> dict[str, Any]:
        from module_support import witness_scene

        produced.update(witness_scene(document))
        return produced

    host = host_of(("pkg", witness_module(scene=scene)))
    view = host.read_resource(
        "witness", "document", root, write_resource(root, "witness", "d")
    )
    produced["nodes"] = []
    assert view.scene is not None and len(view.scene["nodes"]) == 3
    json.dumps(view.scene)


def test_codec_crash_is_a_runtime_error(root: Path) -> None:
    class Crashing(RecordingCodec):
        def decode(self, data: bytes) -> Any:
            raise RuntimeError("bug du module")

    host = host_of(("pkg", witness_module(codec=Crashing())))
    view = host.read_resource(
        "witness", "document", root, write_resource(root, "witness", "d")
    )
    assert view.read is None and view.scene is None
    assert view.runtime_error == "Décodage du module en échec (RuntimeError)."


def test_optional_dependency_state_is_exposed() -> None:
    host = host_of(("pkg", witness_module(probe=lambda: {"spice": False})))
    module = host.module("witness")
    assert "simulate" not in module.available_capabilities
    assert dict(module.unavailable_dependencies) == {"spice": "Moteur de simulation"}
